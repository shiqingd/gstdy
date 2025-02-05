#!/usr/bin/env python3

import os
import sys
import sh
import argparse
import traceback
import re
import json
from datetime import datetime
import time
from io import StringIO
from lib.dry_run import dryrunnable

if not "DJANGO_SETTINGS_MODULE" in os.environ:
		os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
		import django
		django.setup()

from framework.models import *
import lib.dry_run
from lib.pushd import pushd
from lib.colortext import ANSIColor, RGBColor
from lib.PatchParser import get_patch_id, get_patch_dict
from django.db.models import F, Q

import pytz
from django.utils import timezone

_git = sh.Command("/usr/bin/git")

#lib.dry_run.set(True)

#FIXME deprecate this in favor of an upcoming wrapper in lib.dry_run
@dryrunnable()
def __dryrunnable_git(*args):
    _git(args)

def __get_new_patches(version_tag, branch):
	print("MAJOR VERSION:", version_tag)
	print("BRANCH:", branch)
	_git("checkout", branch)
	__dryrunnable_git("pull")
	revlist = _git("rev-list", "--no-merges", "--reverse" , version_tag+".."+branch, _tty_out=False)
	revlist = revlist.split()
	print(ANSIColor("bright_green", "\tUpdating %s..%s: %d patches" % (version_tag, branch, len(revlist))))
	i = 0
	total_revs = len(revlist)
	for rev in revlist:
		patch = StableKernel.objects.filter(commit_id = rev).first()
		if not patch:
			try:
				patch_body = _git("show", "-1", "--format=%b", rev, _tty_out=False).stdout.decode('utf-8', errors='ignore')
				output = _git("patch-id", _tty_out=False, _in=StringIO(patch_body)).stdout.decode('utf-8', errors='ignore')
				payload_hash = output.split()[0]
				output = _git("log", "-1", '--format=%at %ae %s', rev, _tty_out=False).stdout.decode().strip()
				timestamp, author, subject = re.match('^([0-9]+) (\S+) (.+)$', output).groups()
				git_desc = _git("describe", "--tags", "--match", "v[2-9].*", rev).stdout.decode('utf-8', errors='ignore')
				r = re.compile('(v[2-9]\.[0-9]+(?:-r[ct][0-9]+|\.[0-9]{1,3}(?:-rt[0-9]+){0,1}){0,1}).*$')
				m = r.match(git_desc)
				tag = m and m.group(1) or None
				try:
					date = timezone.make_aware(datetime.fromtimestamp(int(timestamp)))
				except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError) as e:
					print(ANSIColor("yellow", "Adjusting Ambiguous time stamp for", rev))
					date = timezone.make_aware(datetime.fromtimestamp(int(timestamp)+7200))
				patch = StableKernel(payload_hash = payload_hash,
					commit_id = rev,
					author = author,
					subject = subject,
					tag = tag,
					date = date)
				if 'intel.com' in patch.author:
					print(ANSIColor("green", str(patch.to_dict())))
				else:
					print(patch.to_dict())
				patch.save()					# Add to DB
			except Exception as e:
				print(traceback.format_exc())
				print(rev, "FAILED")
		i += 1
		if (i % 100 == 0) : print(i, "of", total_revs, round(float(i)/float(total_revs)*100.0, 3) , '%')

bash = sh.Command("/bin/bash")

def __populate_from_stable(version_number):
	version_tag = 'v'+version_number
	print("VERSION TAG:", version_tag)
	print("VERSION NUMBER:", version_number)
	repo = Repository.objects.get(repotype__repotype = 'lts')
	assert(os.path.exists(os.path.join(os.environ["WORKSPACE"],repo.project)))
	__git = repo.initialize(scmdir=os.path.join(os.environ["WORKSPACE"],repo.project))	# returns a sh.Command() object
	with pushd(repo.scmdir):
		print(__git("fetch", "--all", "--tags", _tty_out=False))
		stable_tag = bash('-c', 'git tag --sort  version:refname | grep -o "v[2-9]\.[0-9]\{1,2\}$" | tail -1', _tty_out=False).stdout.decode().strip()
		print("STABLE TAG:", stable_tag)
		version_branch = 'linux-'+version_number+'.y'
		__get_new_patches(version_tag, version_branch)


def __populate_from_mainline():
	repo = Repository.objects.get(repotype__repotype = 'mainline')
	assert(os.path.exists(os.path.join(os.environ["WORKSPACE"],repo.project)))
	__git = repo.initialize(scmdir=os.path.join(os.environ["WORKSPACE"],repo.project))	# returns a sh.Command() object
	with pushd(repo.scmdir):
		print(__git("fetch", "--all", "--tags", _tty_out=False))
		mainline_tag = bash('-c', 'git tag --sort  version:refname | grep -o "v[2-9]\.[0-9]\{1,2\}$" | tail -1', _tty_out=False).stdout.decode().strip()
		print("MAINLINE TAG:", mainline_tag)
		__get_new_patches(mainline_tag, "master")


if __name__ == '__main__':

	assert(os.path.exists(os.environ["WORKSPACE"]))
	for kernel in Kernel.objects.filter(name__in = [ '5.4lts', '5.10lts' ]):
		__populate_from_stable(kernel.base_kernel)
	__populate_from_mainline()
