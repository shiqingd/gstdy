#!/usr/bin/env python3

import os
import sys
import sh
import shutil
		
if not "DJANGO_SETTINGS_MODULE" in os.environ: 
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from framework.models import *
import lib.utils
from lib.pushd import pushd
from lib.colortext import ANSIColor

_repo = sh.Command(os.path.join(os.environ["HOME"],"bin/repo"))

def __edit_sync_cmd_max_jobs():
	bash_snippet = '''set =x
SRCFILE=subcmds/sync.py
IFLINE=`grep -n 'if self.jobs > MAX_JOBS' ${SRCFILE} | cut -f1 -d:`
SEDCMD="${IFLINE},$((IFLINE+2))s/^/#/g"
sed -i ${SEDCMD} ${SRCFILE}
unset SRCFILE
unset IFLINE
unset SEDCMD
set +x
'''
	lib.utils.bash_source(bash_snippet)
	
def __process_stdout(line):
	print(ANSIColor("green",line), end='')

def __process_stderr(line):
	print(ANSIColor("red",line), end='')

def _sync_android_repos(fresh_repo = False):
	android_repos = AndroidRepo.objects.all()
	for r in android_repos:
		# DB columns:
		# name: symbolic name
		# branch: branch specified in 'repo init'
		# manifest: manifest (if any) specified in 'repo init'
		#	if manifest = '<skip>', don't sync it
		repo_dir="/var/lib/jenkins/shares/android/{}".format(r.name)
		repo_dir="/android/android/{}".format(r.name)
		print("repo_dir="+repo_dir)
		if '<skip>' in r.manifest:
			continue
		os.makedirs(repo_dir, exist_ok=True)
		with pushd(repo_dir):
			# Build repo from scratch only if explicitly told to with 'yes'
			if fresh_repo:
				shutil.rmtree(".repo", ignore_errors=True)
			if not os.path.exists(".repo"):
				args = [ "-u", "ssh://android.intel.com/manifests", "-b", r.branch, "--mirror" ]
				if r.manifest:
					args += [ "-m" , r.manifest ]
				print("_repo.init("+str(args)+")")
				_repo.init(args, _out=__process_stdout, _err=__process_stderr)
			else:
				_repo.selfupdate()
			args = [ "-c", "-f", "-j7" ]
			print("_repo.sync("+str(args)+")")
			_repo.sync(args, _out=__process_stdout, _err=__process_stderr)

if __name__ == '__main__':
#	__edit_sync_cmd_mas_jobs()
	return _sync_android_repos(fresh_repo = (len(sys.argv) > 1 and sys.argv[1] == '-f'))
