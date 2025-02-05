#!/usr/bin/env python3
import os
import sys
import sh
import argparse
import re

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
import lib.jenkins
import lib.utils
from lib.pushd import pushd

def __main(args):
	date_string, release_string = lib.utils.get_ww_string(args.staging_number)
	email_txt="Hi All,\n\nStaging.Please test.\n\nPlease email your results to \
kernel@eclists.intel.com; pk.sdk.cw@intel.com;otc.production.kernel@intel.com\n\n"

	kobj = Kernel.objects.get(name = args.kernel)
	jobs = JenkinsJob.objects.filter(host__name = "OTC PKT", kernel = kobj).exclude(jobname__icontains='ltpddt')
	krs = list(KernelRelease.objects.filter(kernel = kobj))
	kernel_version=args.upstream_kernel_version
	with open("{}/kernel_version.prop".format(os.environ["WORKSPACE"]), "w") as f:
		f.write("KERNEL_VERSION={}\n".format(kernel_version))
	print(len(jobs))
	staging_branch = {}
	for kr in krs:
		template = BranchTemplate.objects.get(name = 'staging', kernel = kobj)
		t = Template (template.template)
		release = Release.objects.get (name = kr.release)
		c = Context ( {"kernel" : kobj, "release" : release, "staging_number" : args.staging_number } )
		staging_branch = t.render (c)
		# Remove origin/ from the staging_branch string.
		staging_branch = staging_branch[7:]
		with open("{}/{}_build.prop".format(os.environ["WORKSPACE"], release.name), "w") as f:
			f.write("{}_BRANCH={}\n".format(release.name.upper(), staging_branch))

	new_build_num = 0
	for job in jobs:
		num = lib.jenkins.get_latest_build_number(job.host.url, job.jobname)
		if num > new_build_num:
			new_build_num = num
	new_build_num += 1
	for job in jobs:
		lib.jenkins.set_next_build_number(job.host.url, job.host.jenkins_user, job.host.jenkins_token, job.jobname, new_build_num)

	with open("{}/subject.txt".format(os.environ["WORKSPACE"]), "w") as f:
		f.write("[Staging][{}][LTS]{}".format(kernel_version,release_string))

	email_txt+="Images:(when done)\n"
	for job in jobs:
		 email_txt+='{}/job/{}/{}\n'.format(job.host.url,job.jobname,new_build_num)

	with open("{}/message.txt".format(os.environ["WORKSPACE"]), "w") as f:
		f.write(email_txt)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--kernel', '-p', required=True, type=Kernel.validate, default='devbkc', help=Kernel.list())
	parser.add_argument('--upstream_kernel_version', '-u', required=True, type=str, default='', help="upstream kernel version")
	parser.add_argument('staging_number', help="Staging Number")
	parser.add_argument('--dry_run', dest='lib.dry_run.dry_run', action='store_true', help="Do not actually do anything; just print what would happen")
	args = parser.parse_args()
	assert("WORKSPACE" in os.environ)
	__main(args)

