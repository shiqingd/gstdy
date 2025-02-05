#!/usr/bin/env python3

import re
import os
import sys
import json

'''
REPOS = [
('OWR/IoTG/ESE/Linux-Integration/Yocto/manifest','https://github.com/intel-innersource/os.linux.yocto.build.manifest.git'),
('OWR/IoTG/ESE/Linux-Integration/Yocto/yocto-repo_manifest',''),
('linux-kernel-integration/kernel-staging','https://github.com/intel-innersource/os.linux.kernel.kernel-staging.git'),
('linux-kernel-integration/kernel-lts',''),
('linux-kernel-integration/kernel-lts-quilt',''),
('linux-kernel-integration/kernel-config','https://github.com/intel-innersource/os.linux.kernel.kernel-config'),
('linux-kernel-integration/kernel-staging',''),
('linux-kernel-integration/kernel-dev-quilt','https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt.git'),
('linux-kernel-integration/kernel-lts-cve','https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve.git'),
('linux-kernel-integration/kernel-lts-staging','https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git'),
('linux-kernel-integration/mainline-tracking-staging','https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git'),
('linux-kernel-integration/kernel-lts-staging-test',''),
('linux-kernel-integration/kernel-dev-quilt-test',''),
('linux-kernel-integration/mainline-tracking',''),
('linux-kernel-integration/iotg-kernel-staging','https://github.com/intel-innersource/os.linux.kernel.iot-kernel-staging.git'),
('linux-kernel-integration/iotg-kernel-overlay-staging',''),
('linux-kernel-integration/iotg-kernel-overlay','https://github.com/intel-innersource/os.linux.kernel.iotg-kernel-overlay.git')
]
'''
REPOS = [
('linux-kernel-integration/kernel-dev-quilt','https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt.git'),
('linux-kernel-integration/kernel-lts-cve','https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve.git'),
('linux-kernel-integration/kernel-lts-staging','https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git'),
('linux-kernel-integration/mainline-tracking-staging','https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git'),
('linux-kernel-integration/iotg-kernel-staging','https://github.com/intel-innersource/os.linux.kernel.iot-kernel-staging.git'),
('linux-kernel-integration/iotg-kernel-overlay','https://github.com/intel-innersource/os.linux.kernel.iotg-kernel-overlay.git')
]

if not "DJANGO_SETTINGS_MODULE" in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
        import django
        django.setup()

from framework.models import *

'''
def main():
	for t in REPOS:
		print('===================================')
		rows = Repository.objects.filter(project = t[0])
		for r in rows:
			print(r.pk, r.protocol, r.host, r.project, '---> ', end='')
			if t[1]:
				match = re.match('(^.+)://([^/]+)/(.+)', t[1])
				r.pk = None
				r.protocol = match.group(1)
				r.host = match.group(2)
				r.project = match.group(3)
				r.ext_project_id = 0
				r.ext_group_id = 0
				print(r.pk, r.protocol, r.host, r.project)
				r.save()
			print('')
'''

def main():
	repos = json.load(open("/tmp/repos.json"))
	rows = Repository.objects.filter(project__contains = 'intel-innersource')
	for r in rows:
		print(r.pk, r.protocol, r.host, r.project, r.ext_group_id, r.ext_project_id)
		for repo in repos:
			print(repo["full_name"])
			if r.project == repo["full_name"]:
				print(repo["id"])
				break


if __name__ == '__main__':
	main()
		
