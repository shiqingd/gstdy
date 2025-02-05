#!/usr/bin/env python3
"""
Jenkins wrapper functions
"""

import requests
import os
import sys
import json
import logging
import inspect
from lib.dry_run import dryrunnable
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

g_auth = ( 'sys_oak',  os.environ['SYS_OAK_CRED_AD'] )

def print_with_line_number(message):
    print(f'Line {inspect.currentframe().f_back.f_lineno}: {message}')

def __get_CSRF_tokens(url):
	"""
	Get the Jenkins CSRF synchronizer token
	"""

	result = requests.get(url='{}/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'.format(url), verify = False)
	return result.text.split(':')

def form_job_url(base_url, jobname):
	if '/' in jobname:
		folder, job = jobname.split('/')
		url = f'{base_url}/job/{folder}/job/{job}'
	else:
		url = f'{base_url}/job/{jobname}'
	return url

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
	
	job_url = form_job_url(url,jobname)
	url = f'{job_url}/api/json'
	print_with_line_number(url)
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

	job_url = form_job_url(url,jobname)
	url = f'{job_url}/{build_number}/api/json'
	print_with_line_number(url)
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

	job_url = form_job_url(url,jobname)
	url = f'{job_url}/lastBuild/api/json/pretty=true'
	print_with_line_number(url)
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
	job_url = form_job_url(url,jobname)
	url = f'{job_url}/buildWithParameters?token={token}'
	print_with_line_number(url)
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
	job_url = form_job_url(url,jobname)
	url = f'{job_url}/nextbuildnumber/submit?token={token}'
	print_with_line_number(url)
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
	
	job_url = form_job_url(url,jobname)
	url = f'{job_url}/lastSuccessfulBuild/api/json/pretty=true'
	print_with_line_number({url})
	logger.debug(url)
	result = requests.get(url=url, auth = g_auth, verify=False)
	print_with_line_number(f"{result.status_code}")
	json_result = json.loads(result.text)
	return int(json_result["number"])


def get_last_successful_build(url, jobname):
	"""
	Get the current highest build number for a job

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:returns: Latest build number for the specified job
	:rtype: int
	"""
	
	job_url = form_job_url(url,jobname)
	url = f'{job_url}/lastSuccessfulBuild/api/json/pretty=true'
	print_with_line_number({url})
	logger.debug(url)
	result = requests.get(url=url, auth = g_auth, verify=False)
	print_with_line_number(f"{result.status_code}")
	json_result = json.loads(result.text)
	return json_result["url"]

def get_artifact_list(url, jobname, build_number):
	"""
	Get the artifact list of the specified build

	:param url: URL of Jenkins Master
	:type url: str
	:param jobname: Jenkins Job name
	:type jobname: str
	:param build_number: Jenkins Build number
	:type jobname: int
	:returns: the list of artifacts
	:rtype: list
	"""

	job_url = form_job_url(url,jobname)
	url = f'{job_url}/{build_number}/api/json/?tree=artifacts[relativePath]'
	print_with_line_number(url)
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


class JenkinsArtifactFinder(object):

	def __init__(self):
		pass

	def get_artifact_list(self, url, jobname, build_number):
		CJE_URL=url
		ARTIFACTORY_API_URL = "https://ubit-artifactory-or.intel.com/artifactory/api"
		ARTIFACTORY_FILE_URL = "https://ubit-artifactory-or.intel.com/artifactory"
		ARTIFACTORY_REPO_URL = f"{ARTIFACTORY_FILE_URL}/nece_linux_kernel-or-local"
		self.jobname = jobname
		self.build_number = build_number

		# Check #1 - search in Artifactory Builds for Jenkins Build Info:
		if '/' in jobname:
			folder, job = jobname.split('/')
			build_name = f"{folder}%20::%20{job}"
		else:
			build_name = jobname

		next_url = f"{ARTIFACTORY_API_URL}/build/{build_name}/{build_number}"
		response = requests.get(next_url,
			headers = { "Accept" : "application/json" , "X-JFrog-Art-Api" : os.environ["SYS_OAK_CRED_ARTIFACTORY_API"]})
		print(f"{next_url} : HTTP {response.status_code}")
		if response.status_code == 200:
			self.source_url = ARTIFACTORY_REPO_URL
			self.artifacts = [ item["path"] for item in response.json()["buildInfo"]["modules"][0]["artifacts"] ]
			return

		# Check #2 - search in Artifactory Repository for Artifacts Script-Moved from Jenkines server
		if '/' in jobname:
			folder, job = jobname.split('/')
			build_name = f"{folder}/job/{job}"
		else:
			build_name = jobname

		next_url = f"{ARTIFACTORY_API_URL}/storage/nece_linux_kernel-or-local/teams-iotgdevops00/job/{build_name}/{build_number}?list&deep=1"
		response = requests.get(next_url,
			headers = { "Accept" : "application/json" ,  "X-JFrog-Art-Api" : os.environ["SYS_OAK_CRED_ARTIFACTORY_API"]})
		print(f"{next_url} : HTTP {response.status_code}")
		if response.status_code == 200:
			self.source_url = ARTIFACTORY_REPO_URL
			self.artifacts =  [ item["uri"] for item in response.json()["files"] ]
			return

		# Check #3 - search Build Informaton on Jenkins server
		auth = ('sys_oak', os.environ['SYS_OAK_CRED_JENKINS_API'])

		next_url=f"{CJE_URL}/job/{build_name}/{build_number}"
		response = requests.get(f"{next_url}/api/json/?tree=artifacts[relativePath]", auth = auth)
		print(f"{next_url} : HTTP {response.status_code}")
		if response.status_code == 200:
			self.source_url = f"{next_url}/artifact"
			self.artifacts = [ item['relativePath'] for item in response.json()['artifacts'] ]
			return

		raise FileNotFoundError(f"No artifact path found for job {jobname} build {build_number} from any source")
