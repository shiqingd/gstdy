#!/usr/bin/env python3

'''
Sample script to get upstream commit information (if available)
for a kernel patch in a staging branch
'''

import os
import sys
import argparse
import traceback
import json

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from framework.models import *

from lib.pushd import pushd
from lib.colortext import ANSIColor, RGBColor

def get_patch_upstream_info(revision, kernel):
	'''
	Sample function to Get Stored upstream information (if available) for a staging patch
	'''
	try:
		patch = Patch.objects.get(staging_commit = args.revision, kernel = kernel)
		jj = patch.to_dict()
		return jj
	except Exception as e:
		print(e)
		print("Database for staging kernel", kernel.name, "may need to be updated")
		return None


def __print_all_info_for_staging_kernel(kernel_name):
	'''
	Sample function to Get Stored upstream information (if available) for all patched in a staging kernel
	'''
	# Get Kernel object from DB
	kernel = Kernel.objects.get(name = kernel_name)

	# Find the correct repo(s) for this kernel
	krs = KernelRepoSet.objects.filter(kernel = kernel, repo__repotype__repotype = 'src')
	for kr in krs:
		__git = kr.repo.initialize(scmdir=os.path.join(os.environ["WORKSPACE"],kr.repo.project))	# returns a sh.Command() object
		# Compute using patch-id hash (more reliable)
		with pushd (kr.repo.scmdir):
		   # Use each tracking/staging branch configured for this kernel in each repo
			tbs = TrackerBranch.objects.filter(kernel = kernel, repo = kr.repo)
			for tb in tbs:
				try:
					__git("checkout" , tb.branch)
				except Exception as e:
					print("Cannot checkout {}: {}".format(e.args[0].strip().split('\n')[-1]))
					continue

				revlist = __git("rev-list", "--no-merges", "--reverse" , "{}..{}".format(kernel.current_baseline, tb.branch).strip())
				revlist = revlist.split()
				for rev in revlist:
					try:
						patch = Patch.objects.get(staging_commit = rev, kernel = kernel)
						jj = patch.to_dict()
						print(json.dumps(jj,indent=4))
					except Exception as e:
						print("Cannot find revision ", rev, ":", e)
						print("Database for staging kernel", kernel.name, "may need to be updated")


if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
	parser.add_argument('--revision', '-r', type=str, help="Staging Branch commit ID in IKT project for given staging kernel")
	parser.add_argument('--all', '-a', action='store_true', default=False, help="return all staging patches for this staging kernel")
	args = parser.parse_args()

	if not args.all:
		kernel = Kernel.objects.get(name = args.kernel)
		patch_json = get_patch_upstream_info(args.revision, kernel)
		if patch_json:
			print(json.dumps(patch_json, indent=4))
	else:
		# Get info for all patches in the staging kernel
		__print_all_info_for_staging_kernel(args.kernel)
