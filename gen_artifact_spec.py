#!/usr/bin/env python3

import sys
import os
import json

if not "DJANGO_SETTINGS_MODULE" in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
        import django
        django.setup()

try:
	assert('DATABASE_HOST' in os.environ)
except:
	print("Environment Variable DATABASE_HOST not set", file=sys.stderr)
	sys.exit(1)

from framework.models import JenkinsJob, Kernel, Platform, Artifacts

def main():
	spec = {}
	try:
		kernel = Kernel.objects.get(name = sys.argv[2])
		job = JenkinsJob.objects.get(jobname = sys.argv[1], kernel = kernel)
		platform = Platform.objects.get(name = sys.argv[3])
		artifacts = Artifacts.objects.get(job = job, kernel = kernel, platform = platform)
		spec["files"] = []
		for p in artifacts.patterns.all():
			_file = { "flat" : p.flat, "pattern" : p.pattern, "target" : artifacts.target.target }
			spec["files"].append(_file)
		print(json.dumps(spec,indent=4))
	except Exception as e:
		spec = { "ERROR" : str(e) }
		print(json.dumps(spec,indent=4))
		sys.exit(1)
		pass

if __name__ == '__main__':
	main()

