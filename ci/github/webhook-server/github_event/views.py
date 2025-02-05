import os
import re
import json
import yaml
import logging
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.response import Response

from lib import utils
from lib.jobwrapper import BUILD_SERVERS
from lib.jenkinswrapper import JenkinsWrapper

logger = logging.getLogger('django.server')

# load yaml file when views.py is loaded
mydir = os.path.dirname(os.path.abspath(__file__))
CONF_FILE = os.path.join(mydir, 'webhooks-conf.yml')
with open(CONF_FILE, 'r') as cfg:
    CONF = yaml.safe_load(cfg)

REGISTRY_FILE = os.path.join(CONF['log_dir'], CONF['registry_file'])


def register_event(event_name, sha, updated, pr_no_id=''):
    rv = False
    entry = "%s:%s:%s:%s" % (event_name, sha, updated, pr_no_id)
    with open(REGISTRY_FILE, 'a+') as f:
        # get the lock
        utils.lock_file(f)
        f.seek(0)
        text = f.read()
        m = re.search(r'^%s' % entry, text, flags=re.M)
        if not m:
            f.write("%s\n" % entry)
            rv = True
        # release the lock
        utils.unlock_file(f)

    return rv


# return: the list of test case name
def get_testplan(event_type, conf, payload):
    rules = conf['rules']
    testcases = set()
    rule_groups = []
    rule_types = None
    branches = {}
    if event_type == 'pull_request':
        rule_types = ['base', 'head', 'base_exclude', 'head_exclude']
        branches['base'] = payload['pull_request']['base']['ref']
        branches['base_exclude'] = payload['pull_request']['base']['ref']
        branches['head'] = payload['pull_request']['head']['ref']
        branches['head_exclude'] = payload['pull_request']['head']['ref']
    elif event_type == 'push':
        rule_types = ['ref', 'ref_exclude']
        branches['ref'] = payload['ref']
        branches['ref_exclude'] = payload['ref']
    for t in rule_types:
        if t in rules and rules[t]:
            rule_groups.append((t, rules[t],))
    logger.info("  base: %s, head: %s, ref: %s" % \
                  (branches.get('base', ''),
                   branches.get('head', ''),
                   branches.get('ref', '')))
    for g in rule_groups:
        # rule type
        t = g[0]
        # rule list under this type
        rl = g[1]
        logger.info("  rule type: %s" % t)
        for r in rl:
            m = re.search(r['branch'], branches[t])
            if m:
                logger.info("    %s: matched" % r['branch'])
                if t.endswith('_exclude'):
                    testcases = testcases.difference(r['testcases'])
                else:
                    testcases = testcases.union(r['testcases'])
                break
            else:
                logger.info("    %s: NOT matched" % r['branch'])
    testplan = None
    if testcases:
        # full testcase list
        tcl = conf['full_testcases']
        testplan = [ tcl[i] for i in testcases ]

    return testplan


def trigger_ci(event_type, github_payload):
    repo_name = github_payload['repository']['name']
    if repo_name not in CONF:
        logger.info("Unrecognized repo: %s, skipped." % repo_name)
        return None

    # load the job parameters
    job_data = {
        'github_url': github_payload['repository']['html_url'],
        'github_repo_fullname': github_payload['repository']['full_name'],
        'github_event_name': event_type,
        'github_event_action': '',
        'github_event_number': None,
        'github_before': '',
        'github_ref': '',
        'github_sha': '',
        'github_head_ref': '',
        'github_base_ref': '',
        'github_head_sha': '',
        'github_base_sha': '',
        'github_labels': '',
        'ci_testplan': None,
    }
    prnoid = ''
    registered_sha = None
    updated = github_payload['repository']['updated_at']
    if event_type == 'pull_request':
        logger.info("Received pr: %s" % \
                      github_payload['pull_request']['html_url'])
        labels = github_payload['pull_request']['labels']
        prno = github_payload['pull_request']['number']
        if not len(labels):
            logger.info("  No label found, skipped")
            return None

        if github_payload['action'] == 'closed' and \
           github_payload['pull_request']['merged']:
            job_data['github_event_action'] = 'merged'
        else:
            job_data['github_event_action'] = github_payload['action']
        job_data['github_event_number'] = str(prno)
        job_data['github_prid'] = str(github_payload['pull_request']['id'])
        job_data['github_head_ref'] = github_payload['pull_request']['head']['ref']
        job_data['github_base_ref'] = github_payload['pull_request']['base']['ref']
        job_data['github_head_sha'] = github_payload['pull_request']['head']['sha']
        job_data['github_base_sha'] = github_payload['pull_request']['base']['sha']
        prnoid = "%i_%i" % (github_payload['pull_request']['number'],
                            github_payload['pull_request']['id'])
        registered_sha = job_data['github_head_sha']
        # set labels
        job_data['github_labels'] = ','.join([l['name'] for l in labels])
    elif event_type == 'push':
        logger.info("Received push: %s, %s, %s" % \
                      (github_payload['repository']['name'],
                       github_payload['ref'],
                       github_payload['after']))
        job_data['github_before'] = github_payload['before']
        job_data['github_ref'] = github_payload['ref']
        job_data['github_sha'] = github_payload['after']
        # for push event, use github_sha as the event number
        # which would be used for posting comment on Github
        job_data['github_event_number'] = job_data['github_sha']
        registered_sha = job_data['github_sha']
    else:
        logger.warn("Unrecognized event, skipped:")
        logger.warn(github_payload)
        return None

    testplan = get_testplan(event_type, CONF[repo_name], github_payload)
    if not testplan:
        logger.info("  No branch rule matched, skipped")
        return None
    job_data['ci_testplan'] = ','.join(testplan),

    # check if it is a duplicated event, otherwise, register it
    rst = register_event(job_data['github_event_name'],
                         registered_sha,
                         updated,
                         prnoid)
    if not rst:
        logger.info(
          "  Duplicated event, ignored: %s, %s" % (registered_sha, updated))
        return None

    jhost = CONF['jenkins_host']
    job_name = CONF[repo_name]['jenkins_job']
    job_server_url = BUILD_SERVERS[jhost]['url']
    job_user = BUILD_SERVERS[jhost]['user']
    job_pass = BUILD_SERVERS[jhost]['pass']
    job_type = BUILD_SERVERS[jhost]['type']

    job = JenkinsWrapper(job_type=job_type,
                         job_server_url=job_server_url,
                         job_name=job_name,
                         auth=(job_user, job_pass),
                         job_data=job_data)

    logger.info("  Github CI started")
    # trigger the job
    job.trigger_job()
    # wait until the build is started and build no. is assigned
    job.get_job_no()

    log_fl = os.path.join(CONF['log_dir'], job.job_name, "%s.json" % job.job_no)
    os.makedirs(os.path.dirname(log_fl), exist_ok=True)
    with open(log_fl, 'w') as l:
        l.write(json.dumps(github_payload, indent=4))
    logger.info("  Saved the payload in %s" % log_fl)

    return job


class Github_Event_Handler(APIView):
    def post(self, request, *args, **kwargs):
        event_type = request.headers.get("X-GitHub-Event")
        event_id = request.headers.get("X-GitHub-Delivery")
        payload = json.loads(request.body)

        event_fl = os.path.join(CONF['log_dir'], "payloads", event_id)
        with open(event_fl, 'w') as l:
            l.write(json.dumps(payload, indent=4))

        # strip 'refs/heads' from ref
        if 'ref' in payload and payload['ref']:
            payload['ref'] = payload['ref'].replace('refs/heads/', '')
        # for CI
        job = trigger_ci(event_type, payload)

        # for other usage
        # ...

        return Response({'status': 'ok'})


    # handle get request
    def get(self, request, *args, **kwargs):
        # get get request params : request.query_params

        return Response({'status': 'ok'})
