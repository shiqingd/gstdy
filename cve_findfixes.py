#!/usr/bin/env python3

import sys, os
import json
import requests
import sh
from lib.pushd import pushd
from lib.colortext import ANSIColor
import argparse


__git = sh.Command("/usr/bin/git")

# "https://raw.githubusercontent.com/nluedtke/linux_kernel_cves/master/data/stream_data.json",
# "https://github.com/nluedtke/linux_kernel_cves/blob/master/data/stream_fixes.json",
kernel_cves_json = 'https://raw.githubusercontent.com/nluedtke/linux_kernel_cves/master/data/kernel_cves.json'

if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--repo', '-r', required=True, type=str, help="pathname to mainline linux-stable repo (e.g. /home/your_idsid/linux-stable)")
	parser.add_argument('--pattern', '-p', required=True, type=str, help="text pattern of files changes to search for in CVE fixes (e.g. 'drm')")
	args = parser.parse_args()

	r = requests.get(url = kernel_cves_json, allow_redirects=True)
	print(r.status_code)
	if r.status_code == 200:
		j = json.loads(r.text)
		with pushd(args.repo):
			for k in sorted(j.keys()):
				if k < "CVE-2014":
					continue
				if "fixes" in j[k]:
					if j[k]["fixes"] == "":
						print(k, j[k]["fixes"])
						continue
					try:
						base_tag = __git('--no-pager', 'describe', j[k]["fixes"]).stdout.strip().decode()
						print(k, ANSIColor("green", j[k]["fixes"]), ANSIColor("yellow",base_tag))
						files = __git('--no-pager', 'show', '--format=', '--name-only', j[k]["fixes"]).stdout.strip().decode()
						if args.pattern in files:
							print(ANSIColor("red", files))
					except Exception as e:
						print(e)
				else:
					print(k, "")

