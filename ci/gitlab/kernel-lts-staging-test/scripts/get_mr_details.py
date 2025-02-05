"""Demo script to get merge request information"""

import requests
import json
import sys

API_URL = "https://gitlab.devtools.intel.com/api/v4"
HEADERS = {"PRIVATE-TOKEN": "sn-L-sfdbmrBkXzciXxK"}
#$CI_API_V4_URL/projects/$CI_PROJECT_ID/repository/commits/$CI_COMMIT_SHA/merge_requests

def get_mr_by_mr(project_id, merge_request_iid):
	r = requests.get(API_URL+"/projects/"+str(project_id)+"/merge_requests/"+str(merge_request_iid), headers=HEADERS)
	try:
		mr_data = json.loads(r.text)
		print("Dump information of merge_request ", mr_data["title"])
		print("source_branch: ", mr_data["source_branch"])
		print("desription: ", mr_data["description"])
		print("labels: ", mr_data["labels"])
	except Exception as e:
		print(e)
	return

def get_mr_by_commit(project_id, commit_sha):
	r = requests.get(API_URL+"/projects/"+str(project_id)+"/repository/commits/"+str(commit_sha)+"/merge_requests", headers=HEADERS)
	try:
		mr_data = json.loads(r.text)[0]
		print("Dump information of merge_request ", mr_data["title"])
		print("source_branch: ", mr_data["source_branch"])
		print("desription: ", mr_data["description"])
		print("labels: ", mr_data["labels"])
	except Exception as e:
		print(e)
	return

def main(arg_list):
	mode, project_id, second_param = arg_list[:3]
	if mode == "commit":
		return get_mr_by_commit(project_id, second_param)
	elif mode == "mergerequest":
		return get_mr_by_mr(project_id, second_param)
	else:
		print("Unsupport mode: ", mode)
		print("Others: ", project_id, second_param)
		return 1


if __name__ == "__main__":
	main(sys.argv[1:])
	pass


