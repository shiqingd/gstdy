#!/usr/bin/env python3
import os
import sys
import sh
import argparse

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from framework.models import *
from lib.pushd import pushd
import lib.utils
import lib.dry_run
from lib.dry_run import dryrunnable, traceable, dryrunnable_method
from django.template import Template, Context
import requests
import filecmp

_git = sh.Command("/usr/bin/git")

@dryrunnable()
def __dryrunnable_git(*args):
	_git(args)

@traceable()
def __traceable_git(*args):
	_git(args)

def __init_kernels(kobj):
	'''
	Clone the projects needed for this kernel.
	Do a git-fetch for both remotes.
	'''

	rows = KernelRepoSet.objects.filter(kernel = kobj)
	for row in rows:
			row.init_kernels()
	return rows

def __main(args):
	kobj = Kernel.objects.get(name = args.kernel)

	# FIXME Backward compatibility move until we move to better version of this script
	if args.baseline:
		kobj.current_baseline = args.baseline

	# FIXME - this monkey patch needs to be replaced by a DB-driven method
	# IDEA: add a preprocess and postpocess plugin capability to the Kernel model
	# FIXME - The template needs to be changed to get rid of kernel.rt_baseline
	kobj.rt_baseline = kobj.current_baseline
	# FIXME - this monkey-patched attribute should only be seen by RT templates in the DB

	tags = []
	reposets = __init_kernels(kobj)
	release = KernelRelease.objects.get(kernel=kobj, release__name = args.release).release
	print(f"RELEASE {release.name} ==============================================================================================")
	for _set in reposets:
		print(f"REPO: {_set.repo.project} ==============================================================================================")
		with pushd(os.path.join(os.environ["WORKSPACE"],_set.repo.project), _verbose=True):
			all_remotes = Remote.objects.filter(kernelrelease__kernel = kobj, local_repo = _set.repo).order_by('id')
			print(f"Order of remote push operations for REPO {_set.repo.project}:")
			for remote in all_remotes:
				print('+++++', remote.id, remote.remote_name)
				if remote.remote_name != 'origin':
					remote.remote_repo.git_remote_add_and_fetch(remote.remote_name)
#			for row in releases:
			Tag_template = TagTemplate.objects.get(kernel= kobj).template.template
			t = Template(Tag_template)
			c = Context ( { "is_sandbox" : '' , "is_cve" : str(_set.repo.repotype) == 'cve' and 'cve-' or '' ,
				"is_pre_prod" : args.no_pre_prod and "" or "pre-prod-",
				"kernel" : kobj, "release" : release, "staging_number" : args.staging_number} )
			Tag = t.render (c)

			try:
				__traceable_git("checkout" , Tag)
			except Exception as e:
				print("unable to checkout", Tag, str(e).splitlines()[-1], ", SKIP tag")
				continue
			if not all_remotes:
				print("NOTICE: No remotes to push for", _set.repo.project)
				continue

			with open("{}/ds_release.prop".format(os.environ["WORKSPACE"]), "w") as f:
				f.write("KERNEL_TAG={}\n".format(Tag))
				f.write("KERNEL={}\n".format(args.kernel))
				f.write("STAGING_NUMBER={}\n".format(args.staging_number))

			for remote in all_remotes:
				print("REMOTE: id {} {}".format(str(remote.id),remote.remote_name))
				if remote.kernelrelease.release == release:
					push_branch_template = remote.push_template.template.template
					t = Template(push_branch_template)
					c = Context( { "kernel" : kobj, "release" : release, "staging_number" : args.staging_number} )
					push_branch = t.render (c)
					f_push_method = getattr(lib.utils, remote.push_method)

											# default: 1
					repousage = 1
					if 'quilt' in remote.remote_name:
						repousage = 2
					elif 'cve' in remote.remote_name:
						repousage = 3
						tags.append("%s:3:2" % Tag)
					elif 'overlay' in remote.remote_name:
						repousage = 4
					# make internal release
					if ( not remote.remote_repo.external ) and args.internal_release :
						f_push_method(remote.remote_name, "HEAD", push_branch)
						if not (remote.remote_repo.repotype.repotype == 'config' and kobj.category == 'rt' ):
							try:
								__dryrunnable_git("push", remote.remote_name, Tag)
								tags.append("%s:%i:2" % (Tag, repousage))
							except Exception as e:
								print(e)
								print("Could not push Tag")

					# make external release
					if ( remote.remote_repo.external ) and args.external_release:
						if 'cve' not in remote.remote_name:
							f_push_method(remote.remote_name, "HEAD", push_branch)
							__dryrunnable_git("tag", "-d", Tag)
							__dryrunnable_git("tag", "--sign", Tag, "-m", "")
							__dryrunnable_git("push", remote.remote_name, Tag)
							tags.append("%s:%i:3" % (Tag, repousage))
						else:
							print("TAG TEMPLATE:", Tag_template)
							t = Template(Tag_template)
							c = Context({"is_sandbox": '', "is_cve": 'cve-',
										"is_pre_prod" : args.no_pre_prod and "" or "pre-prod-",
										"kernel": kobj, "release": release,
										"staging_number": args.staging_number})
							cve_tag = t.render(c)
							print('cve_tag is ', cve_tag)
							__traceable_git("fetch", "origin", "--tags", "--force", "--prune")
							__traceable_git("checkout", Tag)
							__traceable_git("clean", "-xdff")
							local_repo_path = os.path.join(os.environ["WORKSPACE"], remote.local_repo.project)
							remote_repo_path = os.path.join(os.environ["WORKSPACE"], remote.remote_repo.project)
							assert(os.path.isdir(local_repo_path))
							if not os.path.exists(remote_repo_path):
								remote.remote_repo.initialize(scmdir=remote_repo_path, branch=push_branch)  # initialize github repo
							with pushd(remote_repo_path, _verbose=True):
								try:
									__traceable_git("fetch", "--all", "--tags", "--force", "--prune")
									__traceable_git("checkout", push_branch)
									__traceable_git("reset", "--hard", "origin/"+push_branch)
									__traceable_git("clean","-xdff")
									bt = BranchTemplate.objects.get(kernel = kobj, name = 'quilt_patches')
									local_patch_path =  Template(bt.template.template).render(Context({ "repo_path" : local_repo_path , "release" : release }))
									remote_patch_path = Template(bt.template.template).render(Context({ "repo_path" : remote_repo_path , "release" : release }))
									print(f"filecmp.dircmp({local_patch_path} {remote_patch_path})")
									diff = filecmp.dircmp(local_patch_path, remote_patch_path)
									if diff == 0:
										__dryrunnable_git("tag", "--sign", cve_tag, "-m", "")
										__dryrunnable_git("push", 'origin', cve_tag)
									else:
										dryrunnable_method(shutil.rmtree, remote_patch_path, ignore_errors=True)
										dryrunnable_method(shutil.copytree, local_patch_path, remote_patch_path)
										__dryrunnable_git("add", remote_patch_path)
										try:
											__dryrunnable_git("commit", "-s", "-m", "Update CVE patches")
										except Exception as e:
											print(e)
											pass
										__dryrunnable_git("push", 'origin', push_branch)
										__dryrunnable_git("tag", "--sign", cve_tag, "-m", "")
										__dryrunnable_git("push", 'origin', cve_tag)
										tags.append("%s:%i:3" % (cve_tag, repousage))
								except Exception as e:
									print("ERROR: Could not push CVE Tag", cve_tag)
									print(e)
									sys.exit(1)

							'''
							with pushd(remote_repo_path, _verbose=True):
								try:
									__traceable_git("fetch", "--all", "--tags", "--force", "--prune")
									__traceable_git("checkout", push_branch)
									__traceable_git("reset", "--hard", "origin/"+push_branch)
									__traceable_git("clean","-xdff")
									bt = BranchTemplate.objects.get(kernel = kobj, name = 'quilt_patches')
									local_patch_path =  Template(bt.template.template).render(Context({ "repo_path" : local_repo_path , "release" : release }))
									remote_patch_path = Template(bt.template.template).render(Context({ "repo_path" : remote_repo_path , "release" : release }))
									print(f"filecmp.dircmp({local_patch_path} {remote_patch_path})")
									diff = filecmp.dircmp(local_patch_path, remote_patch_path)
									if diff == 0:
										__dryrunnable_git("tag", "--sign", cve_tag, "-m", "")
										__dryrunnable_git("push", 'origin', cve_tag)
									else:
										dryrunnable_method(shutil.rmtree, remote_patch_path, ignore_errors=True)
										dryrunnable_method(shutil.copytree, local_patch_path, remote_patch_path)
										__dryrunnable_git("add", remote_patch_path)
										try:
											__dryrunnable_git("commit", "-s", "-m", "Update CVE patches")
										except Exception as e:
											print(e)
											pass
										__dryrunnable_git("push", 'origin', push_branch)
										__dryrunnable_git("tag", "--sign", cve_tag, "-m", "")
										__dryrunnable_git("push", 'origin', cve_tag)
										tags.append("%s:%i:3" % (cve_tag, repousage))
									except Exception as e:
										print("ERROR: Could not push CVE Tag", cve_tag)
										print(e)
										sys.exit(1)
								'''


	for tag in tags:
		print("EXTRA_DATA_TAG=%s" % tag)

@dryrunnable()
def __trigger_quiltdiff(Tag):
	#trigger quiltdiff
	print("Tag is %s" % (Tag))
	print("https://oak-jenkins.ostc.intel.com/job/quiltdiff-for-bug-tracking/ is triggered with target_release: %s" % (Tag))
	username = 'sys_oak'
	credential = Credential.objects.get(username = username, app__name = 'ikt_jenkins')
	os.system('curl -k -X POST https://oak-jenkins.ostc.intel.com/job/quiltdiff-for-bug-tracking/buildWithParameters --user {}:{} -d kernel="" -d previous_release="" -d target_release={}'.format(username, credential.credential, Tag))


if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
	parser.add_argument('--release', '-r', required=True, type=Release.validate, help='Release Line supported by the kernel product, one of '+Release.list())
	parser.add_argument('--baseline', '-u', type=str, default=None, help="Upstream baseline kernel version - default : Kernel.current_baseline in DB")
	parser.add_argument('--external_release', '-e', action='store_true', default=False, help="Push the staging branches to external github branch")
	parser.add_argument('--internal_release', '-i', action='store_true', default=False, help="Push the staging branches to internal release branch")
	parser.add_argument('--staging_number', '-s', required=True, type=str)
	parser.add_argument('--no-pre-prod', action='store_true', default=False, help="Do not include the 'pre-prod' text to staging tag")
	parser.add_argument('--dry_run', action='store_true', help="Do not actually do anything; just print what would happen")
	args = parser.parse_args()
	print(args)
	lib.dry_run.set(args.dry_run)
	assert("WORKSPACE" in os.environ)
	__main(args)
