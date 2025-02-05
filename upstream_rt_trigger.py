#!/usr/bin/env python3
import sys
import os
import argparse
import re
import logging
import shutil
import json
from pathlib import Path
from jenkinsapi.jenkins import Jenkins
from jenkinsapi.utils.crumb_requester import CrumbRequester

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from django.core.exceptions import ObjectDoesNotExist

from framework.models import *

from lib.download import HttpDownloader
from lib.jenkins import (
    get_artifact_list,
    get_lastpassed_build_number
)
from lib.pushd import pushd
from lib.utils import (
    get_sha_last_commit,
    checkout,
    is_branch,
    cmd,
    cal_cpu_num,
    get_kernel_baseline,
    make_tarfile,
    cmd_pipe
   )
_git = sh.Command("/usr/bin/git")

logger = logging.getLogger(__name__)

Jenkins_USER="sys_oak"
Jenkins_PASSWORD=os.environ.get('SYS_OAK_CRED_JENKINS_API')


JENKINS_INFO = {
    'url': 'https://oak-jenkins.ostc.intel.com',
    'user': Jenkins_USER,
    'password': Jenkins_PASSWORD,
}

def trigger_jenkins_job(job_name, job_params):
    crumb = CrumbRequester(username=JENKINS_INFO['user'], password=JENKINS_INFO['password'], baseurl=JENKINS_INFO['url'], ssl_verify=False )
    jenkins_server = Jenkins(JENKINS_INFO['url'], username=JENKINS_INFO['user'],
                             password=JENKINS_INFO['password'], requester=crumb, ssl_verify=False)
    res = jenkins_server.build_job(job_name, {'branch': job_params})
    if res:
        logger.info('Trigger job successful!')



class KernelBuild:
    def __init__(self, **kwargs):
        # variables passed from cmdline or build env.
        self.kernel = kwargs.get('kernel')
        self.staging_revision = kwargs.get('staging_revision').lstrip(r'origin/')

        self.workspace = kwargs.get('workspace')
        self.cpu_num = kwargs.get('cpu_num')

        self.top_build_dir = os.path.join(self.workspace, 'kernel_build'+self.kernel.name)
        self.build_timestamp = self.staging_revision.split('-')[-1]
        self.out_dir = os.path.join(self.top_build_dir, 'out')
        print(self.kernel.id)
        self.krepo = KernelRepoSet.objects.get(kernel_id=self.kernel.id)
        #self.krepo = KernelRepoSet.objects.get(repo__repotype__repotype='src',
        #                                       repo__external=False,
        #                                       kernel_id=self.kernel.id)
        self.repo_url = self.krepo.repo.url()


    def prepare_repo_check(self):
        # initialize the kernel repo.
        logger.info("Initialize or sync kernel repo: %s" % self.repo_url)
        self.krepo.repo.initialize(scmdir=self.top_build_dir)
        rmt_ref = self.staging_revision
        loc_ref = None
        print(self.kernel)
        if is_branch(self.repo_url, self.staging_revision):
            # for branch
            rmt_ref = 'origin/' + rmt_ref
            loc_ref = self.staging_revision
        else:
            # for tag
            loc_ref = rmt_ref + '_local'
        with pushd(self.top_build_dir):
            # checkout kernel repo to the specified branch/tag
            #logger.info("Checkout to the staging revision")
            checkout(rmt_ref, loc_ref)
            # get sha1 of the specified staging_revision
            #self.kernel_sha1 = get_sha_last_commit('.')
            #print(self.kernel_sha1)
            #cmd= "git tag --contains HEAD"
            cmd= "git describe --tags --abbrev=0"
            (rc, out, err) = cmd_pipe(cmd)
            if rc != 0:
                raise ShCmdError("get kernel baseline failed: %s\n%s" % (ref, err))
            else:
                new_tags = out.strip().split()[0]
            tested_tag = self.kernel.current_baseline
            if tested_tag != new_tags:
                print("differ")
                self.kernel.current_baseline = new_tags
                #trigger a new testing
                if 'mainline' in self.kernel.name:
                    trigger_jenkins_job("mtl-rt", new_tags)
                else:
                    trigger_jenkins_job("upstream-rt-stable", new_tags)
                self.kernel.save()
                return (True, new_tags)
            else:
                print("no new version")
                return (False, None)





def handle_args(args):
    parser = argparse.ArgumentParser(prog = sys.argv[0], epilog = """\
The osit_staging script will build the kernel from the branch/tag
named on the commandline.""")
    parser.add_argument(
        '--kernel', '-k', dest='kernel_name', required=False, type=str,
        help='Which kernel is going to built')
    parser.add_argument(
        '--staging-revision', '-r', dest='staging_revision', required=False,
        type=str, help='The branch/tag of staging build')
    parser.add_argument(
        '--log-verbose', '-v', action='store_true', help='Log in verbose mode')
    return parser.parse_args()

if __name__ == '__main__':
    assert("WORKSPACE" in os.environ)
    args = handle_args(sys.argv[0])

    loglevel = 'DEBUG' if args.log_verbose else 'INFO'
    logging.basicConfig(level=loglevel, format='%(levelname)-5s: %(message)s')
    print(args.kernel_name)
    tracker_kernel=args.kernel_name.split(',')
    for kernel_name in tracker_kernel:
        print(kernel_name)
        kernel = Kernel.objects.get(name=kernel_name)
        # calculate the number of parallel jobs per available cpu and mem
        cpu_num = cal_cpu_num()

         # get settings from cmdline/env arguments
        kwargs_dict = {
            'kernel': kernel,
            'staging_revision': kernel.base_kernel,
            'workspace': os.environ['WORKSPACE'],
            'cpu_num': cpu_num,
        }

        kb = KernelBuild(**kwargs_dict)
        (trigger, tag) =  kb.prepare_repo_check()



