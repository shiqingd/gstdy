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
from lib.dry_run import dryrunnable, dryrunnable_method, traceable
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
def __dryrunnable_git(*args):
	_git(args)

@traceable()
def __traceable_git(*args):
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

def __init_cve_repo(kernel):

	'''
	Clone the CVE repository for kernel project
	'''

	CVERepo = KernelRepoSet.objects.get(repo__repotype__repotype = 'cve', kernel = kernel)
	CVEProject = CVERepo.repo.project
	with pushd(os.path.join(os.environ["WORKSPACE"], CVEProject), _verbose=True):
		#TODO : update database table for staging_cve template
		template = BranchTemplate.objects.get(name = 'staging_cve', kernel = kernel, release = None)
		t = Template(template.template.template)
		c = Context( { "kernel" : kernel } )
		staging_cve = t.render (c)
		local_cve_branch=kernel.base_kernel+"/lts-cve"
		lib.utils.checkout(staging_cve, local_cve_branch)

def __apply_cve_patches(kr):

	'''
	Apply CVE patchset
	'''
	CVERepo = KernelRepoSet.objects.get(repo__repotype__repotype = 'cve', kernel = kr.kernel)
	CVEProject = CVERepo.repo.project

	# if CVE patch folder name different different from release name, transform it per database entry
	# otherwise, use the release name
	if kr.cve_xform is not None:
		cve_name = kr.cve_xform.name
		print(ANSIColor("yellow", "NOTICE: CVE patches for release {} found in {}/patches".format(kr.release.name, kr.cve_xform.name)))
	else:
		cve_name = kr.release.name

	CVEPatchfolder = os.path.join(os.environ["WORKSPACE"], CVEProject, cve_name, 'patches')
	files = os.listdir(CVEPatchfolder)
	if not os.path.exists('patches'):
		dryrunnable_method(os.mkdir,'patches')
	for f in files:
		dryrunnable_method(shutil.copy,os.path.join(CVEPatchfolder,f),os.path.join(os.getcwd(),'patches'))
	try:
		print("CWD:", os.getcwd())
		print("CURRENT BRANCH:", _git("rev-parse", "--abbrev-ref", "HEAD").strip('\n'))
		__dryrunnable_git("quiltimport")
	except Exception as e:
		print("failed to apply CVE patches: ", str(e))
		sys.exit(1)

def __add_pkt_timestamp_to_config(kernel):
	'''
	Add PKT timestamp to config files

	'''
	#update CONFIG_LOCALVERSION string in config_file
	for dirs in ConfigPath.objects.filter(build__kernel = kernel):
		config_file="{}/{}/{}".format(os.getcwd(), dirs.config_dir, dirs.build.cpu.config_file)
		with open(config_file, "r") as f:
			lines = f.readlines()
			with open(config_file, "w") as f:
				for line in lines:
					if line.startswith('CONFIG_LOCALVERSION='):
						line = re.sub("CONFIG_LOCALVERSION=.*","CONFIG_LOCALVERSION=\"-{}\"".format(_datetime_string), line)
						f.write(line)

def __init_config_repo(kernel):
	'''
	Clone the config repository for kernel project
	Update timestamp with PKT timestamp in config file
	'''

	ConfigRepo = KernelRepoSet.objects.get(repo__repotype__repotype = 'config', repo__external = False, kernel = kernel)
	ConfigProject = ConfigRepo.repo.project
	with pushd(os.path.join(os.environ["WORKSPACE"], ConfigProject)):
		template = BranchTemplate.objects.get(name = 'staging_config', kernel = kernel, release = None)
		t = Template(template.template.template)
		c = Context( { "kernel" : kernel } )
		staging_config = t.render (c)
		# add origin to config branch name
		staging_config='origin/'+staging_config
#		local_config_branch="{}/config".format(kernel.base_kernel)
		local_config_branch=staging_config
		# checkout config branch for non cve
		lib.utils.checkout(staging_config, local_config_branch)

		__add_pkt_timestamp_to_config(kernel)

def __init_quilt_repo(kernel, releases):
	'''
	Clone the Quilt repository for kernel project to Quilt folder
	'''

	QuiltRepo = KernelRepoSet.objects.get(repo__repotype__repotype = 'quilt', repo__external = False, kernel = kernel)
	QuiltProject = QuiltRepo.repo.project
	with pushd(os.path.join(os.environ["WORKSPACE"],QuiltProject), _verbose=True):
		# generate quilt patchset
		local_quilt_branch="{}/quilt".format(kernel.base_kernel)
		if args.stable_quilt_branch != 'none':
			print("args.stable_quilt_branch is not none")
			remote_quilt_branch = args.stable_quilt_branch
			lib.utils.checkout(remote_quilt_branch,local_quilt_branch)
		else:
			template = BranchTemplate.objects.get(name = 'release_quilt_external', kernel=kernel, release = None)
			t = Template (template.template.template)
			for kr in releases:
				c = Context( { "kernel" : kernel, "release" : kr.release } )
				remote_quilt_branch = t.render (c)

				# add origin to remote quilt branch name
				remote_quilt_branch='origin/'+remote_quilt_branch
				print("remote_quilt_branch")
				print(remote_quilt_branch)
				print("local_quilt_branch")
				print(local_quilt_branch)
				lib.utils.checkout(remote_quilt_branch,local_quilt_branch)


def __copy_cve_patches_to_quilt(kernel, release, base_tag, cve_tag):

	Quilt_Project = KernelRepoSet.objects.get(repo__repotype__repotype = 'quilt', repo__external = False, kernel = kernel).repo.project
	CVE_Project = KernelRepoSet.objects.get(repo__repotype__repotype = 'cve', repo__external = False, kernel = kernel).repo.project
	quilt_worktree = os.path.join(os.environ["WORKSPACE"], Quilt_Project)
	cve_worktree = os.path.join(os.environ["WORKSPACE"], CVE_Project)
	quilt_patch_dir = os.path.join(quilt_worktree, "patches")
	cve_patch_dir = os.path.join(cve_worktree, release, "patches")

	print(ANSIColor("yellow", f"------- Adding CVE patches from {cve_patch_dir} to quilt... -------"))
	with pushd(cve_worktree, _verbose=True):
		__traceable_git('checkout', 'origin/'+kernel.base_kernel)

	with pushd(quilt_worktree, _verbose=True):
		__dryrunnable_git('reset', '--hard', base_tag)
		files = os.listdir(cve_patch_dir)
		for f in files:
			cvepatch = os.path.join(cve_patch_dir, f)
			if is_a_patch_file(cvepatch):
				dryrunnable_method(shutil.copy, cvepatch, quilt_patch_dir)
		files.remove('series') # don't copy 'series' filename to series file
		seriespath = os.path.join(quilt_patch_dir, 'series')
		print(ANSIColor("yellow", f"Updating Series file path : {seriespath}"))
		with open(seriespath, 'a') as seriesfile:
			for f in files:
				seriesfile.write(f)
				seriesfile.write("\n")
		__dryrunnable_git("add", ".")
		msg = f"Add CVE patches for Quilt {_datetime_string}"
		__dryrunnable_git("commit", "-sm", msg)
		__dryrunnable_git("tag", "-a", cve_tag, "HEAD", "-m", msg)
		__dryrunnable_git("push", "origin", cve_tag)
	print(ANSIColor("yellow", f"------- CVE patches added to quilt... -------"))


def __generate_quilt_patchset(kernel, releases):

	'''
	Generate Quilt patchset for new base release
	Copy the generated patches to Kernel Quilt folder
	'''

	# if stable_branch_quilt is not provided we need to generate
	# quilt patchset from last release
	# we maintain a copt of last release branch in staging repo. Fetch that branch name from database
	Quilt_Project = KernelRepoSet.objects.get(repo__repotype__repotype = 'quilt', repo__external = False, kernel = kernel).repo.project
	template = BranchTemplate.objects.get(name = 'release_copy_src', kernel = kernel, release = None)
	t = Template (template.template.template)
	for kr in releases:
		c = Context( { "kernel" : kernel, "remote_name" : "origin", "release" : kr.release} )

		# last base release branch
		base_release_branch = t.render (c)

		# generate quilt patchset from staging branch to last base release branch
		__dryrunnable_git("format-patch", "origin/{}/release/{}..HEAD".format(kernel.base_kernel, kr.release),
				 "--suffix=.{}".format(_datetime_string))

		# copy the new set of patches to kernel-dev-quilt folder
		files = [f for f in os.listdir('.') \
				if os.path.isfile(f) and f.endswith(_datetime_string)]
		for f in files:
			_rsync("-av", f, os.path.join(os.environ["WORKSPACE"], Quilt_Project,
					"patches"))
			with open(os.path.join(os.environ["WORKSPACE"], Quilt_Project,
				"patches/series"), "a") as seriesfile:
				seriesfile.write(f)
				seriesfile.write("\n")
	with pushd(os.path.join(os.environ["WORKSPACE"],Quilt_Project)):
		__dryrunnable_git("add", "patches/series", "patches/*.{}".format(_datetime_string))
		__dryrunnable_git("commit", "-sm", "Kernel update {}".format(_datetime_string))

def __main(args):
	# kernel already validated in argparse

	# pushed tag list
	tags = []

	try:
		kernel = Kernel.objects.get(name = args.kernel)
		print ("*** main *** kernel version ", kernel)
	except Exception as e:
		print(traceback.format_exc())
		return 1

	# FIXME Backward compatibility move until we move to better version of this script
	if args.baseline:
		kernel.current_baseline = args.baseline
		kernel.save() # Store specified baseline in Database

	sandbox_release = False
	# Get all release variants for this kernel type
	# KLUDGE - pjnozisk = skip  xenomai until we migrate to unified DB
	krs = list(KernelRelease.objects.filter(~Q(release__name = 'xenomai'), kernel = kernel))
#	krs = list(KernelRelease.objects.filter(kernel = kernel))
	print ("all release variants ", krs)

	print ("args.init ", args.init)
	if args.init:
		# See if a staging branch has been specified to override the
		# add the coe-tracker remote, and check-out local working instances
		# of the LTS branches.

		# Initialize the repos and working directories needed for this kernel
		reposets = __init_kernel_Reposet(kernel)
		for rs in reposets:
			print("REPOSET:", rs)
		print ("args.init cwd ", os.getcwd())

		# setup config folder
		if kernel.flags & Kernel.PUSH_CONFIGS_FOR_STAGING:
			print("args.kernel is", args.kernel)
			__init_config_repo(kernel)

		# setup Kernel quilt folder to maintain quilt patchset
		__init_quilt_repo(kernel, krs)

		# initialize CVE repository
		__init_cve_repo(kernel)

		# initialize kernel source projects
		Kernel_Repo = KernelRepoSet.objects.get(repo__repotype__repotype = 'src', repo__external = False, kernel = kernel)
		Kernel_Project = Kernel_Repo.repo.project
		if kernel.flags & Kernel.PUSH_CONFIGS_FOR_STAGING:
			Config_Project = KernelRepoSet.objects.get(repo__repotype__repotype = 'config', repo__external = False, kernel = kernel).repo.project
		Quilt_Project = KernelRepoSet.objects.get(repo__repotype__repotype = 'quilt', repo__external = False, kernel = kernel).repo.project
		if kernel.flags & Kernel.PUSH_CONFIGS_FOR_STAGING:
			local_config_branch="{}/config".format(kernel.base_kernel)
		local_quilt_branch="{}/quilt".format(kernel.base_kernel)
		date_string, release_string = lib.utils.get_ww_string(_datetime_string)
		jobs = JenkinsJob.objects.filter(host__name = "OTC PKT", kernel = kernel).exclude(jobname__icontains='ltpddt')
		email_txt="Hi All,\n\nStaging.Please test.\n\nPlease email your results to \
nex.linux.kernel.integration@intel.com; iotg.linux.kernel.testing@intel.com; nex.sw.linux.kernel@intel.com\n\n \
Images (when done)\n"

		# get tag template from database
		tag_template = TagTemplate.objects.get(kernel = kernel).template.template

		# TODO
		with pushd(os.path.join(os.environ["WORKSPACE"],Kernel_Project), _verbose=True):
			# FIXME - this monkey patch needs to be replaced by a DB-driven method
			# FIXME - The template needs to be changed to get rid of kernel.rt_baseline
			kernel.rt_baseline = kernel.current_baseline
			# FIXME - this monkey-patched attribute should only be seen by RT templates in the DB

			for kr in krs: # krs are release variants ex. android, base etc.
				print ("kr in krs ", kr)
				template = BranchTemplate.objects.get(name = 'staging', kernel = kernel, release = None)
				t = Template (template.template.template)
				release = Release.objects.get(name = kr.release)
				c = Context( { "kernel" : kernel, "release" : release, "staging_number" : _datetime_string } )
				staging_branch = t.render (c)

				# If an alternate (staging) ranch is provided,  set up to use it
				alt_branch_key = kr.cve_xform and kr.cve_xform.name or kr.release.name
				if alt_branch_key in args.alt_branch:
					staging_branch = args.alt_branch[alt_branch_key]
					print("Sandbox {} branch provided --> <{}>".format(kr.release.name, staging_branch))
					sandbox_release = True

				# add origin to staging branch
				if not 'origin/' in staging_branch:
					staging_branch = 'origin/'+staging_branch
				print ("+++ staging_branch +++ ", staging_branch)


				# FIXME no longer needed???
				local_template = BranchTemplate.objects.get(name = 'staging_local', kernel = kernel, release = None)
				c = Context( { "kernel" : kernel, "release" : kr.release , "staging_number" : _datetime_string } )
				staging_local = t.render (c)
				print ("+++ staging_local +++ ", staging_local)
				lib.utils.checkout(staging_branch, staging_local)

				# update config
				if kernel.flags & Kernel.PUSH_CONFIGS_FOR_STAGING:
					for dirs in ConfigPath.objects.filter(build__kernel=kernel, release=kr.release):
						print("+++++++++++++++++++++")
						print(kr.release.name)
						print(dirs.config_dir)
						dirs.update_config(Config_Project)
						print("+++++++++++++++++++++")

				if args.stable_quilt_branch != 'none':
					print("Skipping quilt creation")
				else:
					print("Creating quilts")
					# generate quilt patchset for all configured releases
					__generate_quilt_patchset(kernel, krs)

				#create tag from template
				t = Template(tag_template)
				c = Context ( { "is_sandbox" : sandbox_release and 'sandbox-' or '', "is_cve" : '' ,
					"kernel" : kernel, "release" : release, "staging_number" : _datetime_string} )
				tag_to_push = t.render (c)
				print (ANSIColor("green", "tag_name ", tag_to_push))

				msg = "Creating tag for " + tag_to_push
				__dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
				email_txt+='\n tag_name: ' + tag_to_push

				# Create prop files for Jenkins jobs
				with open("{}/{}_build.prop".format(os.environ["WORKSPACE"], kr.release.name), "w") as f:
					f.write("STAGING_REV={}\n".format(tag_to_push))

				with open("{}/upstream_kernel_version.prop".format(os.environ["WORKSPACE"]), "w") as f:
					f.write("KERNEL_VERSION={}\n".format(kernel.current_baseline))
					f.write("KERNEL={}\n".format(kernel.name)) #KERNEL=5.15lts or KERNEL=5.15bp

				# Push staging branch/tag
				if args.push:
					__dryrunnable_git("push", "origin", tag_to_push)
					# tag data schema: <tag>:<repousage>:<repotype>
					# repousage: 1 default, 2 quilt, 3 cve, 4 overlay
					# repotype:  1 staging, 2 internal release, 3 external release
					tags.append("%s:1:1" % tag_to_push)
				else:
					print ("push is false")

				if args.create_cve_staging_branch:
					__apply_cve_patches(kr)
					#create tag from template
					t = Template(tag_template)
					c = Context ( { "is_sandbox" : sandbox_release and 'sandbox-' or '', "is_cve" : 'cve-' ,
						"kernel" : kernel, "release" : release, "staging_number" : _datetime_string} )
					tag_to_push = t.render (c)
					print (ANSIColor("green", "tag_name ", tag_to_push))
					msg = "CVE: Creating tag for " + tag_to_push
					__dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
					email_txt+='\n CVE tag_name: ' + tag_to_push

					# Create prop files for CVE Jenkins jobs
					with open("{}/{}_cve_build.prop".format(os.environ["WORKSPACE"], kr.release.name), "w") as f:
						f.write("STAGING_REV={}\n".format(tag_to_push))

					# Push staging branch/tag
					if args.push:
						__dryrunnable_git("push", "origin", tag_to_push)
						tags.append("%s:3:1" % tag_to_push)
					else:
						print ("push is false")

		# push config branch
		if kernel.flags & Kernel.PUSH_CONFIGS_FOR_STAGING:
			with pushd(os.path.join(os.environ["WORKSPACE"],Config_Project), _verbose=True):
				commit_msg="x86: config: update for kernel change {}".format(_datetime_string)
				lib.utils.commit_local(commit_msg)
				for kr in krs:
					t = Template(tag_template)
					c = Context ( { "is_sandbox" : sandbox_release and 'sandbox-' or '', "is_cve" : '' ,
						"kernel" : kernel, "release" : release, "staging_number" : _datetime_string} )
					tag_to_push = t.render (c)

					msg = "Creating config tag for " + tag_to_push
					print (ANSIColor("green", "tag_name ", tag_to_push))
					if kernel.category != 'rt':
						__dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
						if args.push:
							__dryrunnable_git("push", "origin", tag_to_push)
						else:
							print ("push is false")
					if args.create_cve_staging_branch:
						c = Context ( { "is_sandbox" : sandbox_release and 'sandbox-' or '', "is_cve" : 'cve-' ,
							"kernel" : kernel, "release" : release, "staging_number" : _datetime_string} )
						tag_to_push = t.render (c)
						msg = "CVE: Creating config tag for " + tag_to_push
						print (ANSIColor("green", "tag_name ", tag_to_push))
						if kernel.category != 'rt':
							__dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)

							if args.push:
								__dryrunnable_git("push", "origin", tag_to_push)
							else:
								print ("push is false")

		with pushd(os.path.join(os.environ["WORKSPACE"],Quilt_Project), _verbose=True):
			# git add new patches generated from this staging (if any)
			for file in os.listdir("./patches"):
				if file.endswith(_datetime_string):
					__dryrunnable_git("add","./patches/"+file)

			commit_msg="Staging quilt for: staging/{}/lts/base-{}".format(kernel.base_kernel,_datetime_string)
			lib.utils.commit_local(commit_msg)

			# create tag for each configured release for this kernel
			for kr in krs:
				t = Template(tag_template)
				c = Context ( { "is_sandbox" : sandbox_release and 'sandbox-' or '', "is_cve" : '' ,
					"kernel" : kernel, "release" : release, "staging_number" : _datetime_string} )
				tag_to_push = t.render (c)
				msg = "In quilt repo creating tag for " + tag_to_push
				print (ANSIColor("green", "dev quilt tag_name ", tag_to_push))
				__dryrunnable_git("tag", "-a", tag_to_push, "HEAD", "-m", msg)
				if args.push:
					__dryrunnable_git("push", "origin", tag_to_push)
					tags.append("%s:2:1" % tag_to_push)
				else:
					print ("push is false")

		# create and push tag for cve repo
		if not kernel.flags & Kernel.NO_CVE_PATCHES:
			CVE_Project = KernelRepoSet.objects.get(repo__repotype__repotype='cve', repo__external=False, kernel=kernel).repo.project
			with pushd(os.path.join(os.environ["WORKSPACE"], CVE_Project), _verbose=True):
				msg = 'Fix for CVE issue'
				for kr in krs:
					t = Template(tag_template)
					context_dict = {"is_sandbox": sandbox_release and 'sandbox-' or '', "is_cve": '',
								 "kernel": kernel, "release": release, "staging_number": _datetime_string}
					base_tag = t.render(Context(context_dict))
					# Create CVE tag by updating context
					context_dict["is_cve"] = 'cve-'
					cve_tag = t.render(Context(context_dict))
					print(ANSIColor("green", "cve repo tag_name ", cve_tag))
					if kernel.flags & Kernel.ADD_CVE_PATCHES_TO_QUILT:
						__copy_cve_patches_to_quilt(kernel, kr.release.name, base_tag, cve_tag)
					__dryrunnable_git("tag", "-a", cve_tag, "HEAD", "-m", msg)
					# this tag would be ignored by job data collection tool, because
					# it's an additional tag only used for creating release tag
					if args.push:
						__dryrunnable_git("push", "origin", cve_tag)
					else:
						print("push is false")

		with open("{}/staging_number.prop".format(os.environ["WORKSPACE"]), "w") as f:
			f.write("STAGING_NUMBER={}\n".format(_datetime_string))


		'''
		# set build number for downstream jobs. Set all build to highest number
		new_build_num = 0
		for job in jobs:
			num = lib.jenkins.get_latest_build_number(job.host.url, job.jobname)
			if num > new_build_num:
				new_build_num = num

		new_build_num += 1
		for job in jobs:
			lib.jenkins.set_next_build_number(job.host.url, job.host.jenkins_user, job.host.jenkins_token, job.jobname, new_build_num)
		'''

		with open("{}/subject.txt".format(os.environ["WORKSPACE"]), "w") as f:
			if sandbox_release == 'True':
				f.write("[Sandbox-Staging][{}][LTS]{}".format(kernel.current_baseline, release_string))
			else:
				f.write("[Staging][{}][LTS]{}".format(kernel.current_baseline,release_string))

		'''
		for job in jobs:
			email_txt+='{}/job/{}/{}\n'.format(job.host.url,job.jobname,new_build_num)
		'''

		if sandbox_release == 'True':
			email_txt+='\n DO NOT RELEASE !'

		with open("{}/message.txt".format(os.environ["WORKSPACE"]), "w") as f:
			f.write(email_txt)

		# print tag data into log so that the job collection tool can extract it
		for tag in tags:
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
	parser.add_argument('--baseline', '-u', type=str, default=None, help="Upstream baseline kernel version, default: kernel.current_baseline in DB")
	parser.add_argument('--init', '-i', action='store_true', default=True, help="Initialize the work space")
	parser.add_argument('--merge', '-m', action='store_true', default=True, help="Merge the domain branches")
	parser.add_argument('--push', '-p', action='store_true', default=False, help="Push the release candidates to staging branches")
	parser.add_argument('--compile', '-c', action='store_true', default=True, help="Perform a compile test release branch candidates")
	parser.add_argument('--dry_run', action='store_true', help="Do not actually do anything; just print what would happen")
	parser.add_argument('--create_cve_staging_branch', '-s', action='store_true', default=False, help="Merge CVE patchset and push CVE branch for testing")
	parser.add_argument('--alt_base_branch', '-abb', required =True, type=str, default='none', help="Specify alternative base branch for a sandbox staging")
	parser.add_argument('--alt_android_branch', '-aab', required =True, type=str, default='none', help="Specify alternative android branch for a sandbox staging")
	parser.add_argument('--alt_yocto_branch', '-ayb', required =True, type=str, default='none', help="Specify alternative yocto branch for a sandbox staging")
	parser.add_argument('--alt_branch', '-ab', type=str, help="String-serialized JSON dictionary indicating alternate branch(es) to use for sandbox staging")
	parser.add_argument('--stable_quilt_branch', '-sbbq', required =True, type=str, default='none', help="Specify quilt branch to use in case of sandbox staging")
	parser.add_argument('--staging_number', '-snum', required =True, type=str, default='none', help="Specify staging_number which can be used for release")
	args = parser.parse_args()
	print (args)
	if args.alt_branch is None:
		args.alt_branch = {}
		if args.alt_android_branch != 'none':
			args.alt_branch['android'] = args.alt_android_branch
		if args.alt_base_branch != 'none':
			args.alt_branch['base'] = args.alt_base_branch
		if args.alt_yocto_branch != 'none':
			args.alt_branch['yocto'] = args.alt_yocto_branch
			args.alt_branch['preempt-rt'] = args.alt_yocto_branch
			args.alt_branch['linux'] = args.alt_yocto_branch
	else:
		args.alt_branch = json.loads(args.alt_branch)

	print ('Alternate Branch(es):\n{}'.format(json.dumps(args.alt_branch)))
	lib.dry_run.set(args.dry_run)
	lib.dry_run.verbose(True)
	assert("WORKSPACE" in os.environ)

	if args.staging_number != 'none':
		_datetime_string=args.staging_number

	__main(args)

