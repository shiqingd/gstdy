#!/usr/bin/env python3


import os,sys
import json
import sh
import re
import time, datetime
import cov_utils
import traceback
from hashlib import md5
import argparse

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

try:
	assert('DATABASE_HOST' in os.environ)
except:
	print("Environment Variable DATABASE_HOST not set", file=sys.stderr)
	sys.exit(1)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--ref', '-r', required=True, type=str, help='Staging Branch or Tag to Triage')
	parser.add_argument('--fix', '-f', default=False, action='store_true', help='Automatically fix defects (default: False)')
	parser.add_argument('--new', '-n', action='store_true', default=False, help='Apply to new scanning model')
	parser.add_argument('--arch', '-a', required=False, type=str, default='x86_64', help='Architecture')
	parser.add_argument('--upstream_repo', '-u', required=True, type=str, default=None, help='Path to mainline upstream kernel repo work tree')
	args = parser.parse_args()

	print(args.__dict__)

	stream_args = [ args.ref, args.arch ]
	if args.new:
		stream_args.append('True')
	project, stream, baseline = cov_utils.__get_stream_for( stream_args )

	snapshots = cov_utils.__get_snapshots_for_stream( [ stream ] )

	snap_a = None
	snap_b = None
	for s in snapshots.keys():
		if snapshots[s] == args.ref:
			snap_b = s
			print(f"Snapshot ID for {args.ref} is {snap_b}")
		elif snapshots[s] == baseline:
			snap_a = s
			print(f"Snapshot ID for {baseline} is {snap_a}")

	if not snap_a:
		raise ValueError(f"Snapshot for {baseline} could not be found")

	if not snap_b:
		raise ValueError(f"Snapshot for {args.ref} on stream {stream} could not be found")

	try:
		defects_json = cov_utils.__list_defects_for_snapshot_scope([ project, stream , snap_a, snap_b ]  )

		print(len(defects_json), "New Defects Found")
		cov_utils._triage_new_defects( defects_json, args.ref , args.arch, args.fix, upstream_repo = args.upstream_repo)
	except Exception as e:
		print(traceback.format_exc())
		sys.exit(1)
