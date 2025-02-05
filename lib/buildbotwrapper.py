#!/usr/bin/env python3

import re
import os
import sys
import json
import time
import socket
import logging
import argparse
from lib.utils import requests_get, requests_post
from lib.jobwrapper import JobWrapper
#import requests
#from requests.packages.urllib3.exceptions import InsecureRequestWarning
# disable requests output until it is CRITICAL
#logging.getLogger('requests').setLevel(logging.CRITICAL)
#requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


BUILDBOT_RETRY_EXCEPTIONS = {
    'ArtifactoryAuthError': [
        { 'msg': 'Artifactory authorization error',
          'rep': r'Authorization Required [^\r\n]* https:\/\/[^\r\n]*\.intel\.com\/artifactory',
        },
    ],
}


class BuildbotWrapper(JobWrapper):
    post_headers = {'Accept': 'application/json'}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # common member var.
        self.job_no = None
        self.job_type = kwargs.get('job_type')
        self.job_server_url = kwargs.get('job_server_url')
        self.job_name = kwargs.get('job_name')
        self.auth = kwargs.get('auth')
        self.param_file = kwargs.get('param_file', None)
        # buildbot common member variables
        self.job_step_no = 0
        self.query_job_url_base = None
        self.view_job_url_base = None
        self.trigger_job_url = None
        self.reason = time.asctime(time.localtime())
        self.job_data = kwargs.get('job_data', {})
        self.job_data['reason'] = self.reason


    def trigger_job(self):
        '''
           trigger job
           return True or False
        '''
        resp = requests_post(self.trigger_job_url,
                             data=self.job_data,
                             headers=self.post_headers,
                             auth=self.auth,
                             verify=False)
        #resp.raise_for_status()
        logger.debug(self.job_data)
        logger.debug(resp.reason)
        logger.debug(resp.text)
        if resp.status_code != 200:
            logger.error(resp.text)
            return False
        else:
            return True


    def get_last_step_info(self, job_info):
        # last step info
        ls_info = None
        # find the last step by key: 'isStarted'
        for s in job_info['steps']:
            if not s['isStarted']:
                break
            ls_info = s
        return ls_info


    def get_err_log(self, job_info):
        log = None
        while not log:
            has_subjob = False
            # get the last step info
            ls_info = self.get_last_step_info(job_info)
            if ls_info['urls']:
                subjob_url = list(ls_info['urls'].values())[0]
                if subjob_url.startswith(self.job_server_url):
                    has_subjob = True
                    subjob_url = subjob_url.replace('/builders/',
                                                    '/json/builders/')
                    job_info = json.loads(requests_get(subjob_url, auth=self.auth))
                    continue

            if not has_subjob:
                # get the last log in the logs list
                log_url = '/'.join((ls_info['logs'][-1][1], 'text',))
                log = requests_get(log_url, auth=self.auth)
                break
        return log


    def retry_check(self, job_info):
        err_log = self.get_err_log(job_info)
        JobWrapper.retry_check(self, err_log, BUILDBOT_RETRY_EXCEPTIONS)


    def handle_result(self, job_info):
        '''
           handle the job result when job completes

           job_info: json data of job information
        '''
        pass


    def get_job_url(self):
        return "%s/%s" % (self.view_job_url_base, self.job_no)


    def get_job_no(self):
        while not self.job_no:
            jinfo = requests_get(self.query_job_url_base, auth=self.auth)
            # o/p sample:
            curr_builds = json.loads(jinfo)['currentBuilds']
            select_url = '&'.join(["select=%s" % b for b in curr_builds])
            url = "%s/builds?%s" % (self.query_job_url_base, select_url)
            binfo = json.loads(requests_get(url, auth=self.auth))
            # o/p sample:
            #   {
            #       <build no.>: {
            #           '': ,
            #           '': ,
            #           '': ,
            #           ...
            #       },
            #       ...
            #   }
            for bno in binfo:
                if binfo[bno] and self.reason in binfo[bno]['reason']:
                    self.job_no = bno
                    break
            if not self.job_no:
                time.sleep(30)

        logger.info("Build URL: %s" % self.get_job_url())


    def poll_status(self):
        '''
           detect job status
           return job status json
        '''

        # buildbot job status
        jinfo = requests_get("%s/builds?select=%s" % \
                               (self.query_job_url_base, self.job_no),
                             auth=self.auth)
        jinfo = json.loads(jinfo)[self.job_no]
        #FIXME: is this judge reliable?
        # the job is done if "text" is not null
        if jinfo['text']:
            self.handle_result(jinfo)

        job_step_no = jinfo['currentStep']['step_number']
        job_step_nm = jinfo['currentStep']['text']
        if job_step_no != self.job_step_no:
            logger.info("Status: %s" % ' '.join(job_step_nm))
            self.job_step_no = job_step_no
