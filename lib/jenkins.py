#!/usr/bin/env python3
"""
Jenkins wrapper functions
"""

import requests
import os
import json
import logging
from lib.dry_run import dryrunnable
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

g_auth = ( 'sys_oak',  os.environ['SYS_OAK_CRED_JENKINS_API'] )

def __get_CSRF_tokens(url):
	"""
	Get the Jenkins CSRF synchronizer token
	"""

	result = requests.get(url='{}/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'.format(url), verify = False)
	return result.text.split(':')

def get_build_list(url, jobname):
	"""
	Get the list of most recent builds for a job

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:returns: Latest build number for the specified job
	:rtype: list
	"""
	url = '{}/job/{}/api/json'.format(url, jobname)
	result = requests.get(url=url, auth = g_auth, verify=False)
	print('='*40, result.text)
	json_result = json.loads(result.text)
	return json_result["builds"]

def get_build_info(url, jobname, build_number):
	"""
	Get the recent builds for a job

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:returns: Latest build number for the specified job
	:rtype: list
	"""
	url = '{}/job/{}/{}/api/json'.format(url, jobname, build_number)
	result = requests.get(url=url, auth = g_auth, verify=False)
	json_result = json.loads(result.text)
	return json_result

def get_last_good_build_by_param(url, jobname, param, value):

	for build in get_build_list(url, jobname):
		build_number = build["number"]
		build_info = get_build_info(url, jobname, build_number)
		if build_info["result"] != "SUCCESS":
			continue
		for a in build_info["actions"]:
			if not '_class' in a:
				continue
			if a["_class"] == 'hudson.model.ParametersAction':
				for jparam in a["parameters"]:
					if jparam["name"] == param:
						if jparam["value"] == value:
							print('FOUND', jparam["value"])
							return build_number
					
	return None


def get_latest_build_number(url, jobname):
	"""
	Get the current highest build number for a job

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:returns: Latest build number for the specified job
	:rtype: int
	"""
	url = '{}/job/{}/lastBuild/api/json/pretty=true'.format(url, jobname)
	try:
		result = requests.get(url=url, auth = g_auth, verify=False)
		json_result = json.loads(result.text)
		return int(json_result["number"])
	except Exception as e:
		print(e)
		return -1
		

@dryrunnable()
def build_with_parameters(url, token, jobname, params):
	"""
	Queue a Jenkins job 

	:param url: URL of Jenkins Master
	:type url: str
	:param token: Jenkins user token (used in place of username/password"
	:type token: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:param params:	dictionary of job parameters
	:type params: dict
	:returns: test output of HTTP request
	:rtype: str
	"""
	csrf_token_list = __get_CSRF_tokens()
	url = '{}/job/{}/buildWithParameters?token={}'.format(url, jobname, token)
	result = requests.post(url, auth = g_auth, verify=False,
		headers = { 'cache-control' : 'no-cache', 'content-type' : 'application/x-www-form-urlencoded', csrf_token_list[0] : csrf_token_list[1] },
		 data = params)
	return result.text

@dryrunnable()
def set_next_build_number(url, user, token, jobname, number):
	"""
	Set the next build number for a job

	:param url: URL of Jenkins Master
	:type url: str
	:param token: Jenkins user token (used in place of username/password"
	:type token: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:param number:	value of next build number
	:rtype: int
	:returns: HTTP exit code
	:rtype: int
	"""
	csrf_token_list = __get_CSRF_tokens(url)
	url = '{}/job/{}/nextbuildnumber/submit?token={}'.format(url, jobname, token)
	result = requests.post(url, auth = g_auth,  verify=False,
		headers = { 'cache-control' : 'no-cache', 'content-type' : 'application/x-www-form-urlencoded', csrf_token_list[0] : csrf_token_list[1] },
		data = "nextBuildNumber=%d" % number)
	return result.status_code

def get_lastpassed_build_number(url, jobname):
	"""
	Get the current highest build number for a job

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:returns: Latest build number for the specified job
	:rtype: int
	"""
	url = '{}/job/{}/lastSuccessfulBuild/api/json/pretty=true'.format(url, jobname)
	logger.debug(url)
	result = requests.get(url=url, auth = g_auth, verify=False)
	json_result = json.loads(result.text)
	return int(json_result["number"])

def get_artifact_list(url, jobname, jno):
	"""
	Get the artifact list of the specified build

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:param jno: Jenkins Build number
	:type jobname: int
	:returns: the list of artifacts
	:rtype: list
	"""
	url = '{}/job/{}/{}/api/json/?tree=artifacts[relativePath]'.format(url, jobname, jno)
	logger.debug(url)
	try:
		result = requests.get(url=url, auth = g_auth, verify=False)
		if result.status_code != requests.codes.OK:
			raise requests.RequestException("Unable to get artifacts '%s'(status: %d)" % (url, result.status_code))
		json_result = json.loads(result.text)
	except requests.RequestException as exc:
		raise requests.RequestException("Unable to get artifacts '%s': %s" % (url, str(exc)))
	finally:
		if result is not None:
			result.close()
	return [ a['relativePath'] for a in json_result['artifacts'] ]
