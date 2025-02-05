#!/usr/bin/env python3

#
# Merge the domain branches that have new patches into the release branches
# for LTS releases. This code also maintains a staging shadow for each
# of the release branches. Conflicts are resolved first in the shadow
# branches, and the results are used to resolve any merge conflicts in
# the non-staging branches.
#

import os
import sys
import sh
import argparse
import textwrap
import traceback
import re
import shutil

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.template import Template, Context

from framework.models import *

import lib.utils
from lib.dry_run import dryrunnable, dryrunnable_method, traceable, traceable_method
import lib.jenkins
from lib.pushd import pushd


from lib.colortext import ANSIColor

from datetime import datetime
_datetime = datetime.utcnow()
_datetime_string = _datetime.strftime("%y%m%dT%H%M%SZ")

_git = sh.Command("/usr/bin/git")
_rsync = sh.Command("/usr/bin/rsync")

def __init_kernel_Reposet(kobj):
	'''
	Clone the projects needed for this kernel.
	Do a git-fetch for both remotes.
	'''

	rows = KernelRepoSet.objects.filter(kernel = kobj)

	for row in rows:
		row.init_kernels()
	return rows

def __assert_kernel_consistency(version):
	raise Exception("This function has not yet been ported from BASH")

#FIXME deprecate this in favor of an upcoming wrapper in lib.dry_run
@dryrunnable()
def _dryrunnable_git(*args):
	_git(args)

@traceable()
def _traceable_git(*args):
	_git(args)


# FIXME - maybe move this function to lib/utils.py
def is_a_patch_file(filename):

	'''
	Scan a file, look for tags that are found in a patch file.
	If all tags are found, return True
	'''
	patch_file_tags = {
		'^From [0-9a-f]+ ' : False,
		'^From: ' : False,
		'^Date: ' : False,
		'^Subject: ' : False,
	}
	with open(filename, "r") as fh:
		for line in fh.readlines():
			klist = list(patch_file_tags.keys())
			for k in klist:
				if re.search(k, line):
					del patch_file_tags[k]
					if not patch_file_tags:
						return True
	return False


def _ref_exists_in_remote(ref):
	branch_check = _git("ls-remote", "--heads", "origin", ref)
	if branch_check.strip():
		return True  # The branch exists
	# Check if the name exists as a tag in the 'origin' remote
	tag_check = _git("ls-remote", "--tags", "origin", ref)
	if tag_check.strip():
		return True  # The tag exists
	return False  # Neither a branch nor a tag exists with the given name



def _copy_cve_patches_to_quilt(self, release, base_tag, cve_tag):

	self.cve_patch_dir = os.path.join(self.cve_worktree, release, "patches")
	print(ANSIColor("yellow", f"------- Adding CVE patches from {self.cve_patch_dir} to quilt... -------"))
	with pushd(self.cve_worktree, _verbose=True):
		_traceable_git('checkout', 'origin/'+self.kernel.base_kernel)

	with pushd(self.quilt_worktree, _verbose=True):
		_dryrunnable_git('reset', '--hard', base_tag)
		files = os.listdir(self.cve_patch_dir)
		for f in files:
			cvepatch = os.path.join(self.cve_patch_dir, f)
			if is_a_patch_file(cvepatch):
				dryrunnable_method(shutil.copy, cvepatch, self.quilt_patch_dir)
		files.remove('series') # don't copy 'series' filename to series file
		seriespath = os.path.join(self.quilt_patch_dir, 'series')
		print(ANSIColor("yellow", f"Updating Series file path : {seriespath}"))
		with open(seriespath, 'a') as seriesfile:
			for f in files:
				seriesfile.write(f)
				seriesfile.write("\n")
		_dryrunnable_git("add", ".")
		msg = f"Add CVE patches for Quilt {_datetime_string}"
		_dryrunnable_git("commit", "-sm", msg)
		_dryrunnable_git("tag", "-a", cve_tag, "HEAD", "-m", msg)
		_dryrunnable_git("push", "origin", cve_tag)
	print(ANSIColor("yellow", f"------- CVE patches added to quilt... -------"))


class Workspace(object):

	def __init__(self, args, kernel, kr):
		# pushed tag list
		self.tags = []

		self.root = os.environ["WORKSPACE"]

		self.kernel = kernel
		self.kr = kr
		self.staging_number = _datetime_string

		Kernel_Repo = KernelRepoSet.objects.get(repo__repotype__repotype = 'src', repo__external = False, kernel = self.kernel).repo
		Kernel_Project = Kernel_Repo.project
		self.kernel_worktree = os.path.join(os.environ["WORKSPACE"], Kernel_Project)
		Kernel_Repo.initialize(scmdir=self.kernel_worktree)
		Quilt_Repo = KernelRepoSet.objects.get(repo__repotype__repotype = 'quilt', repo__external = False, kernel = kernel).repo
		Quilt_Project = Quilt_Repo.project
		self.quilt_worktree = os.path.join(os.environ["WORKSPACE"], Quilt_Project)
		Quilt_Repo.initialize(scmdir=self.quilt_worktree)
		CVE_Repo = KernelRepoSet.objects.get(repo__repotype__repotype = 'cve', repo__external = False, kernel = kernel).repo
		CVE_Project = CVE_Repo.project
		self.cve_worktree = os.path.join(os.environ["WORKSPACE"], CVE_Project)
		CVE_Repo.initialize(scmdir=self.cve_worktree)
		self.quilt_patch_dir = os.path.join(self.quilt_worktree, "patches")

		# create all needed branch and tag names

		self.is_pre_prod = not args.no_pre_prod

		self.local_config_branch=f"{self.kernel.base_kernel}/config"
		self.local_quilt_branch=f"{self.kernel.base_kernel}/quilt"
		if args.quilt_branch:
			self.remote_quilt_branch = args.quilt_branch
		else:
			template = BranchTemplate.objects.get(name = 'release_quilt_external', kernel=kernel, release = None)
			t = Template (template.template.template)
			c = Context( { "kernel" : self.kernel, "release" : self.kr.release } )
			self.remote_quilt_branch = f"origin/{t.render (c)}"

		# initialize CVE repository
		template = BranchTemplate.objects.get(name = 'staging_cve', kernel = self.kernel, release = None)
		t = Template(template.template.template)
		c = Context( { "kernel" : self.kernel } )
		self.staging_cve = t.render (c)
		self.local_cve_branch=f"{self.kernel.base_kernel}/lts-cve"

		# initialize kernel source projects
		self.date_string, self.release_string = lib.utils.get_ww_string(_datetime_string)
		self.email_txt="Hi All,\n\nStaging.Please test.\n\nPlease email your results to \
nex.linux.kernel.integration@intel.com; iotg.linux.kernel.testing@intel.com; nex.sw.linux.kernel@intel.com\n\n \
Images (when done)\n"

		# get tag template from database
		self.tag_template = TagTemplate.objects.get(kernel = self.kernel).template.template

	def generate_quilt_patchset(self):

		# if branch_quilt is not provided we need to generate quilt patchset from last release
		# we maintain a copt of last release branch in staging repo. Fetch that branch name from database
		template = BranchTemplate.objects.get(name = 'release_copy_src', kernel = self.kernel, release = None)
		t = Template (template.template.template)
		c = Context( { "kernel" : self.kernel, "remote_name" : "origin", "release" : self.kr.release} )
		# last base release branch
		self.base_release_branch = t.render (c)

		# generate quilt patchset from staging branch to last base release branch
		_traceable_git("format-patch",
				f"origin/{self.kernel.base_kernel}/release/{self.kr.release}..HEAD",
				f"--suffix=.{_datetime_string}")

		with pushd(self.quilt_worktree, _verbose=True):
			lib.utils.checkout(self.remote_quilt_branch,self.local_quilt_branch)

		# copy the new set of patches to kernel-dev-quilt folder
		files = [f for f in os.listdir('.') \
				if os.path.isfile(f) and f.endswith(_datetime_string)]
		for f in files:
			traceable_method(_rsync, "-av", f, os.path.join(self.quilt_worktree, "patches"))
			with open(os.path.join(self.quilt_worktree, "patches/series"), "a") as seriesfile:
				seriesfile.write(f)
				seriesfile.write("\n")
		with pushd(self.quilt_worktree, _verbose=True):
			_dryrunnable_git("add", "patches/series", f"patches/*.{_datetime_string}")
			_dryrunnable_git("commit", "-sm", f"Kernel update {_datetime_string}")

	def generate_tag(self, sandbox, cve):
		t = Template(self.tag_template)
		c = Context ( { "is_sandbox" : sandbox and 'sandbox-' or '', "is_cve" : cve and 'cve-' or '' ,
			"is_pre_prod" :  self.is_pre_prod and 'pre-prod-' or '',
			"kernel" : self.kernel, "release" : self.kr.release, "staging_number" : _datetime_string} )
		return t.render (c)

	def staging_tag_create(self, sandbox=False):

		self.sandbox = sandbox

		with pushd(self.kernel_worktree, _verbose=True):
			# FIXME - this monkey patch needs to be replaced by a DB-driven method
			# FIXME - The template needs to be changed to get rid of kernel.rt_baseline
			self.kernel.rt_baseline = self.kernel.current_baseline
			# FIXME - this monkey-patched attribute should only be seen by RT templates in the DB

			print(f"RELEASE VARIANT: {self.kr.release.name}")
			template = BranchTemplate.objects.get(name = 'staging', kernel = self.kernel, release = None)
			t = Template (template.template.template)
			release = Release.objects.get(name = self.kr.release)
			c = Context( { "kernel" : self.kernel, "release" : self.kr.release, "staging_number" : _datetime_string } )
			self.staging_branch = t.render (c)
			print(f"{ANSIColor('green', 'STAGING_BRANCH:')} {self.staging_branch}")

			# If an alternate branch is provided,  set up to use it
			if args.src_branch:
				self.staging_branch = args.src_branch

			# add origin to staging branch
			if not 'origin/' in self.staging_branch:
				self.staging_branch = f"origin/{self.staging_branch}"

 
			c = Context( { "kernel" : self.kernel, "release" : self.kr.release , "staging_number" : _datetime_string } )
			self.staging_local = t.render (c)

			lib.utils.checkout(self.staging_branch, self.staging_local)

			# update config would go here if needed

			if args.quilt_branch:
				print(f"Quilt Branch {args.quilt_branch} provided")
			else:
				print("No quilt branch provided, Creating quilts...")
				self.generate_quilt_patchset()

			with pushd(self.quilt_worktree, _verbose=True):
				lib.utils.checkout(self.remote_quilt_branch,self.local_quilt_branch)
				# git add new patches generated from this staging (if any)
				for file in os.listdir("./patches"):
					if file.endswith(_datetime_string):
						_dryrunnable_git("add","./patches/"+file)

				commit_msg=f"Staging quilt for: staging/{self.kernel.base_kernel}/lts/base-{_datetime_string}"
				lib.utils.commit_local(commit_msg)

				tag_to_push = self.generate_tag(sandbox=sandbox, cve=False)
				msg = "In quilt repo creating tag for " + tag_to_push
				print (ANSIColor("green", "dev quilt tag_name ", tag_to_push))
				_dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
				_dryrunnable_git("push", "origin", tag_to_push)
				self.tags.append("%s:2:1" % tag_to_push)


			tag_to_push = self.generate_tag(sandbox=sandbox, cve=False)
			print (ANSIColor("green", "tag_name ", tag_to_push))

			msg = f"Creating tag for {tag_to_push}"
			_dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
			self.email_txt+='\n tag_name: ' + tag_to_push

			# Create prop files for Jenkins jobs
			with open("{}/{}_build.prop".format(os.environ["WORKSPACE"], self.kr.release.name), "w") as f:
				f.write("STAGING_REV={}\n".format(tag_to_push))

			with open("{}/upstream_kernel_version.prop".format(os.environ["WORKSPACE"]), "w") as f:
				f.write(f"KERNEL_VERSION={self.kernel.current_baseline}\n")
				f.write(f"KERNEL={self.kernel.name}\n")

			# Push staging branch/tag
			_dryrunnable_git("push", "origin", tag_to_push)
			# tag data schema: <tag>:<repousage>:<repotype>
			# repousage: 1 default, 2 quilt, 3 cve, 4 overlay
			# repotype:  1 staging, 2 internal release, 3 external release
			self.tags.append("%s:1:1" % tag_to_push)

	def cve_tag_create(self, sandbox=False):

		self.sandbox = sandbox

		with pushd(self.kernel_worktree, _verbose=True):
			# FIXME - fail if non-CVE tag hasn't yet been pushed
			non_cve_tag = self.generate_tag(sandbox=sandbox, cve=False)
			if not _ref_exists_in_remote(non_cve_tag):
				raise ValueError(f"Tag {non_cve_tag} was not found in the remote, cannot continue")

			with pushd(self.cve_worktree, _verbose=True):
				lib.utils.checkout(self.staging_cve, self.local_cve_branch)
				if self.kr.cve_xform is not None:
					cve_name = self.kr.cve_xform.name
					print(ANSIColor(f"yellow", f"NOTICE: CVE patches for release {self.kr.release.name} found in {self.kr.cve_xform.name}/patches"))
				else:
					cve_name = self.kr.release.name

			CVEPatchfolder = os.path.join(self.cve_worktree, cve_name, 'patches')
			files = os.listdir(CVEPatchfolder)
			if not os.path.exists('patches'):
				dryrunnable_method(os.mkdir,'patches')
			for f in files:
				dryrunnable_method(shutil.copy,os.path.join(CVEPatchfolder,f),os.path.join(os.getcwd(),'patches'))
			try:
				print("CWD:", os.getcwd())
				print("CURRENT BRANCH:", _git("rev-parse", "--abbrev-ref", "HEAD").strip('\n'))
				_dryrunnable_git("quiltimport")
			except Exception as e:
				print("failed to apply CVE patches: ", str(e))
				sys.exit(1)

			tag_to_push = self.generate_tag(sandbox=sandbox, cve=True)
			print (ANSIColor("green", "tag_name ", tag_to_push))
			msg = "CVE: Creating tag for " + tag_to_push
			_dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
			self.email_txt+='\n CVE tag_name: ' + tag_to_push

			# Create prop files for CVE Jenkins jobs
			with open("{}/{}_cve_build.prop".format(os.environ["WORKSPACE"], self.kr.release.name), "w") as f:
				f.write("STAGING_REV={}\n".format(tag_to_push))

			# Push staging branch/tag
			_dryrunnable_git("push", "origin", tag_to_push)
			self.tags.append("%s:3:1" % tag_to_push)

		with pushd(self.cve_worktree, _verbose=True):
			msg = 'Fix for CVE issue'
			base_tag = self.generate_tag(sandbox=self.sandbox, cve=False)
			cve_tag = self.generate_tag(sandbox=self.sandbox, cve=True)
			print(ANSIColor("green", "cve repo tag_name ", cve_tag))
			if self.kernel.flags & Kernel.ADD_CVE_PATCHES_TO_QUILT:
				_copy_cve_patches_to_quilt(self, self.kr.release.name, base_tag, cve_tag)
			_dryrunnable_git("tag", "-a", cve_tag, "HEAD", "-m", msg)
			# this tag would be ignored by job data collection tool, because
			# it's an additional tag only used for creating release tag
			_dryrunnable_git("push", "origin", cve_tag)


def __main(args):
	# kernel already validated in argparse

		try:
			kernel = Kernel.objects.get(name = args.kernel)
			release = Release.objects.get(name = args.release)
			kr = KernelRelease.objects.get(kernel = kernel, release = release)
		except Exception as e:
			print(traceback.format_exc())
			return 1

		# FIXME Backward compatibility move until we move to better version of this script
		if args.baseline:
			kernel.current_baseline = args.baseline
			kernel.save() # Store specified baseline in Database

		wks = Workspace(args, kernel, kr)

		if args.src_branch and not args.staging_number:
			print(f"STABLE UPDATE: creating sandbox tag")
			wks.staging_tag_create(sandbox=True)

		elif args.src_branch and args.staging_number:
			print(f"STABLE UPDATE: creating cve tag")
			wks.cve_tag_create(sandbox=True)

		elif not args.src_branch and args.staging_number:
			with pushd(wks.kernel_worktree, _verbose=True):
				non_cve_tag = wks.generate_tag(sandbox=False, cve=False)
				staging_exists = _ref_exists_in_remote(non_cve_tag)
			if staging_exists and not args.stable_test:
				print(f"DOMAIN UPDATE: {non_cve_tag} is pushed, creating cve tag")
				wks.cve_tag_create()
			else:
				print(f"STABLE UPDATE: creating staging tag")
				wks.staging_tag_create()

		elif not args.src_branch and not args.staging_number:
			print(f"DOMAIN UPDATE: creating tag")
			wks.staging_tag_create()

		with open(f"{wks.root}/staging_number.prop", "w") as f:
			f.write(f"STAGING_NUMBER={wks.staging_number}\n")

		with open(f"{wks.root}/subject.txt", "w") as f:
			f.write(f"[{wks.sandbox and 'Sandbox-' or ''}Staging][{wks.kernel.current_baseline}][LTS]{wks.release_string}")

		if wks.sandbox:
			wks.email_txt+='\n DO NOT RELEASE !'

		with open("{}/message.txt".format(os.environ["WORKSPACE"]), "w") as f:
			f.write(wks.email_txt)

		# print tag data into log so that the job collection tool can extract it
		for tag in wks.tags:
			print("EXTRA_DATA_TAG=%s" % tag)

	

if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0],
		description="Search the LTS domain branches, incorporate any new patches, and stage a new LTS release.",
		epilog=textwrap.dedent('''
	The optional TIMESTAMP parameter can be used to specify identify a
	prior staging branch on which the new release should be staged. This
	means that you can speculatively begin a new release on top of a
	staging release that is still in flight (unreleased).

	The -i, -m, and -c options are all turned on by default, and the -p
	option is turned off by default. If, however, you specify one or more
	of these options, then any of these options that are not specified
	will be turned off. This makes it possible to pick and choose which
	major portions of the script you want to run.
	'''))

	parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help='Specify the supported kernel product, one of '+Kernel.list())
	parser.add_argument('--release', '-r', required=True, type=Release.validate, help='Release Line supported by the kernel product, one of '+Release.list())
	parser.add_argument('--baseline', '-u', type=str, default=None, help="Upstream baseline kernel version, default: kernel.current_baseline in DB")
	parser.add_argument('--dry_run', action='store_true', default=False, help="Do not actually do anything; just print what would happen")
	parser.add_argument('--stable-test', action='store_true', default=False, help="Used only for stable-update dry run test")
	parser.add_argument('--no-pre-prod', action='store_true', default=False, help="Do not include the 'pre-prod' text to staging tag")
	parser.add_argument('--src_branch', '-s', type=str, default=None, help="Specify alternative base branch for staging")
	parser.add_argument('--quilt_branch', '-q', type=str, default=None, help="Specify quilt branch to used for staging")
	parser.add_argument('--staging_number', '-n', type=str, default=None, help="Specify staging_number to be used for domain update/release")
	args = parser.parse_args()
	print (args)
	lib.dry_run.set(args.dry_run)
	lib.dry_run.verbose(True)
	assert("WORKSPACE" in os.environ)

	if args.staging_number:
		_datetime_string=args.staging_number

	__main(args)

