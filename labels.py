#!/usr/bin/env python3

import sys, os
import requests
import tracers
import json

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from django.db.models import F, Q
from django.core.exceptions import ValidationError
from framework.models import *

from lib.pushd import pushd
from lib.colortext import ANSIColor, RGBColor

GITLAB_PRIVATE_TOKEN = "wKqLMyxFxnsRvRKJizYK"

# Validates labels against DB and returns
# a dictionary of label values
def validate_list(labels : list ) -> dict:

	target_labels = {
		"architecture" : None,
		"platform" : None,
		"domain" : None,
		"subdomain" : None
	}

	def _validate_platform(groups):
		kwargs = {}
		if groups[1] != 'all':
			kwargs["name"] = groups[1]
		kwargs["architecture"] = groups[0]
		if not Platform.objects.filter(**kwargs).first():
			raise ValidationError("Labels "+str(groups)+" not found")
		target_labels["architecture"] = groups[0]
		target_labels["platform"] = groups[1]

	def _validate_domain(groups):
		if not Domain.objects.filter(label_name = groups[0]).first():
			raise ValidationError("Label "+str(groups[0])+" not found")
		target_labels["domain"] = groups[0]

	def _validate_subdomain(groups):
		if not Subdomain.objects.filter(name = groups[0]).first():
			raise ValidationError("Label "+str(groups[0])+" not found")
		target_labels["subdomain"] = groups[0]

	label_regexps =  [
		( r'P::(\S+)::(\S+)', _validate_platform ),
		( r'D::(\S+)', _validate_domain ),
		( r'S::(\S+)',  _validate_subdomain )
	]
	for label in labels:
		for exp in label_regexps:
			m = re.match(exp[0], label)
			if m:
				exp[1](m.groups())

	assert (target_labels["domain"] is not None)
	return target_labels

# Works for both series file LABELS lines
# and env var CI_MERGE_REQUEST_LABELS from Gitlab-CI
def parse_label_string(label_str : str) -> list:
	r = re.compile(r'[PDS]::[0-9A-Za-z_\-]+(?:\:\:[0-9A-Za-z_\-]+){0,1}')
	label_list = sorted(r.findall(label_str))
	return label_list

def _delete_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	print(data)
#	resp = requests.delete("https://gitlab.devtools.intel.com/api/v4/projects/"+str(data["id"])+"/labels", headers = headers, json = data)
	resp = requests.delete("https://gitlab.devtools.intel.com/api/v4/projects/"+str(data["id"])+"/labels/"+data["label_id"], headers = headers)
	print(resp.text)

def _delete_group_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	print(data)
	resp = requests.delete("https://gitlab.devtools.intel.com/api/v4/groups/"+str(data["id"])+"/labels", headers = headers, json = data)
	print(resp.text)

def _get_labels(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	resp = requests.get("https://gitlab.devtools.intel.com/api/v4/projects/"+str(data["id"])+"/labels?per_page=100", headers = headers)
	return json.loads(resp.text)

def _get_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	resp = requests.get("https://gitlab.devtools.intel.com/api/v4/projects/"+str(data["id"])+"/labels/"+data["label_id"], headers = headers)
	return json.loads(resp.text)

def _get_group_labels(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	resp = requests.get("https://gitlab.devtools.intel.com/api/v4/groups/"+str(data["id"])+"/labels?per_page=100", headers = headers)
	return json.loads(resp.text)

def _create_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	print(data)
	resp = requests.post("https://gitlab.devtools.intel.com/api/v4/projects/"+str(data["id"])+"/labels", headers = headers, json = data)
	print(resp.text)

def _create_group_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	print(data)
	resp = requests.post("https://gitlab.devtools.intel.com/api/v4/groups/"+str(data["id"])+"/labels", headers = headers, json = data)
	print(resp.text)

def _edit_group_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	print(data)
	resp = requests.put("https://gitlab.devtools.intel.com/api/v4/groups/"+str(data["id"])+"/labels", headers = headers, json = data)
	print(resp.text)

def _edit_label(data:dict):
	headers = { "Accept" : "application/json", "Content-Type" : "application/json" , "PRIVATE-TOKEN" : GITLAB_PRIVATE_TOKEN }
	print(data)
	resp = requests.put("https://gitlab.devtools.intel.com/api/v4/projects/"+str(data["id"])+"/labels/"+str(data["label_id"]), headers = headers, json = data)
	print(resp.text)

"""
if __name__ == '__main__':
	PROJECT_ID=84617
	sys.settrace(tracers.trace_function_calls)
	data = {
		"id" : PROJECT_ID , 
		"name" : "platform::domain::subdomain2",
		"color" : "#0000FF",
		"text_color" : "#FFFFFF",
		"description" : "SEcond test label"
		}
	__create_label(data)
	__get_labels(data)
"""
