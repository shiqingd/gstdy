#!/usr/bin/env python3

import re
import sys, os
import json
import time
import socket
import logging
from lib.utils import requests_get, requests_post
from lib.jobwrapper import JobWrapper
#import requests
#from requests.packages.urllib3.exceptions import InsecureRequestWarning
# disable requests output until it is CRITICAL
#logging.getLogger('requests').setLevel(logging.CRITICAL)
#requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)

class JenkinsWrapper(JobWrapper):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # common member var.
        self.job_no = None
        self.job_type = kwargs.get('job_type', None)
        self.job_server_url = kwargs.get('job_server_url')
        self.job_name = kwargs.get('job_name')
        self.param_file = kwargs.get('param_file', None)
        self.job_data = kwargs.get('job_data')
        self.auth = kwargs.get('auth')
        # jenkins common member var.
        self.query_job_url_base = '/'.join((self.job_server_url,
                                            'job',
                                            self.job_name,
                                            '%s/api/json%s'))
        self.view_job_url_base = '/'.join((self.job_server_url,
                                           'job',
                                           self.job_name,
                                           '%s'))
        self.trigger_job_url = self.view_job_url_base % 'buildWithParameters'

        result = requests_get('/'.join((self.job_server_url,
                              'crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)')))
        csrf_token_list = result.split(':')
        self.post_headers = {'cache-control': 'no-cache', 
                             'content-type': 'application/x-www-form-urlencoded', 
                             csrf_token_list[0]: csrf_token_list[1]}
        self.queue_id = None


    @staticmethod
    def ptchlst2pidlst(patch_list_str, keep_patchset=True):
        pid_re = r'^(?:http.*/)?(\d{3,}|\d{3,}/\d{1,3})/?$'
        pids = []
        for url in patch_list_str.split(','):
            # pid: <pid>/[<patchset_id>]
            pid = re.sub(pid_re, '\\1', url)
            if not keep_patchset:
                pid = pid.split('/')[0]
            pids.append(pid)
        return ','.join(pids)


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
        if resp.status_code != 201:
            logger.error(resp.text)
            return False
        else:
            self.queue_id = int(resp.headers['Location'].split('/')[-2])
            logger.debug("Queue ID: %d" % self.queue_id)
            return True


    def get_job_no(self):
        # retrieve job no interval
        retr_jno_interval = 30
        while not self.job_no:
            q_bno_url = self.query_job_url_base % \
              ('', '?tree=builds[id,number,result,queueId],queueItem[id,why]')
            resp = json.loads(requests_get(q_bno_url))
            logger.debug(resp)
            qitem = resp['queueItem']
            if qitem and qitem['id'] == self.queue_id:
                logger.info("%s, polling again in %d seconds" % \
                              (qitem['why'], retr_jno_interval))
            else:
                for b in resp['builds']:
                    if b['queueId'] == self.queue_id:
                        self.job_no = str(b['number'])
                        break
            if not self.job_no:
                time.sleep(retr_jno_interval)

        build_url = self.view_job_url_base % self.job_no
        logger.info("Build URL: %s" % build_url)


    def poll_status(self):
        '''
           detect job status
           return job status json
        '''
        jinfo = requests_get(self.query_job_url_base % (self.job_no, ''))
        jinfo = json.loads(jinfo)
        if jinfo['result']:
            self.handle_result(jinfo)

        logger.debug("Build info.: %s" % str(jinfo))
        logger.info("Status: ongoing, polling again in %d seconds" % \
                      self.sta_chk_interval)


    def retry_check(self, job_info, excepts=None):
        q_con_url = self.view_job_url_base % (self.job_no + '/consoleText')
        con_log = requests_get(q_con_url)
        JobWrapper.retry_check(self, con_log, excepts)
