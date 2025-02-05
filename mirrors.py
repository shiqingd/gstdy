#!/usr/bin/env python3
###!/usr/bin/env -vS PYTHONPATH=${WORKSPACE}/linux-kernel-integration/lkit-dev-ops python3 -u

import sys
import sh
import os
import traceback

from lib.dry_run import dryrunnable, dryrunnable_method
import lib.dry_run 

# lib.dry_run.set(True)

if not "DJANGO_SETTINGS_MODULE" in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
        import django
        django.setup()

try:
	assert('DATABASE_HOST' in os.environ)
except:
	print("Environment Variable DATABASE_HOST not set", file=sys.stderr)
	sys.exit(1)

from framework.models import *
import lib.dry_run
from lib.pushd import pushd
from lib.colortext import ANSIColor, RGBColor
from django.db.models import F, Q

MIRRORHOME = '/mirrors'

__git = sh.Command('/usr/bin/git')

# @dryrunnable()
def __dryrunnable_git(*args):
	print("git", args)

def diffbetween(set1, set2):
	d1 = [ item for item in set1 if item not in set2 ]
	return d1

def get_tags(remote, pattern):
	sss = set()
	tags = __git('ls-remote', remote )
	for line in tags:
		match = re.search('refs/tags/'+pattern, line)
		if match:
			sss.add(match.group(0).strip())
	return sorted(sss)

def incremental_push(remote, pattern):
	print("pattern", pattern)
	origins = get_tags('origin', pattern)
	remotes = get_tags(remote, pattern)
	TAGS_TO_PUSH = diffbetween(remotes, origins)
	print("TAGS_TO_PUSH:", TAGS_TO_PUSH)
	for tag in TAGS_TO_PUSH:
		try:
			dryrunnable_method(__git, 'push', 'origin', tag)
		except Exception as e:
			print(e)

def main():
	repos = Repository.objects.annotate(fl_flags = F('flags').bitand(Repository.NO_MIRROR_TAGS)).filter(
		~Q(fl_flags = Repository.NO_MIRROR_TAGS), project__startswith = 'intel-innersource', repotype__repotype = 'src')
	for repo in repos:
		repo.initialize(scmdir = os.path.join(MIRRORHOME, repo.project))
		with pushd(repo.scmdir, _verbose=True):
			try:
				remotelist = __git('remote')
				if not 'mainline\n' in remotelist:
					__git('remote', 'add', 'mainline', 'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git')
				if not 'stable\n' in remotelist:
					__git('remote', 'add', 'stable', 'https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git')
				if not 'stable_rt' in remotelist:
					__git('remote', 'add', 'stable_rt', 'https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-stable-rt.git')
				try:
					dryrunnable_method(__git, 'fetch', '--all', '--force', '--tags')
				except Exception as e:
					# Ignore duplicate tags from other remotes
					print(e)
					pass
				dryrunnable_method(__git, 'checkout', repo.default_branch())
				dryrunnable_method(__git, 'clean', '-xdff')
				dryrunnable_method(__git, 'pull')
			except:
				print(traceback.format_exc())
				continue

			incremental_push('stable', "(v4\.14(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable', "(v4\.19(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable', "(v5\.4(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable', "(v5\.10(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable', "(v5\.15(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable', "(v6\.1(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('mainline', "(v6\.\d+(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('mainline', "(v5\.19(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable_rt', "(v4\.14(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable_rt', "(v4\.19(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable_rt', "(v5\.4(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable_rt', "(v5\.10(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable_rt', "(v5\.15(\.\d+)?)(-r(?:t|c)\d+)?$")
			incremental_push('stable_rt', "(v6\.1(\.\d+)?)(-r(?:t|c)\d+)?$")

	# config rep
	repos = Repository.objects.filter(project__startswith = 'intel-innersource', repotype__repotype = 'config')
	for repo in repos:
		repo.initialize(scmdir = os.path.join(MIRRORHOME, repo.project))
		with pushd(repo.scmdir, _verbose=True):
			dryrunnable_method(__git, 'fetch', '--all', '--force', '--tags')
			dryrunnable_method(__git, 'prune')
			dryrunnable_method(__git, 'checkout', repo.default_branch())
			dryrunnable_method(__git, 'clean', '-xdff')
			dryrunnable_method(__git, 'pull')

if __name__ == '__main__':
	main()

