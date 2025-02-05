#!/usr/bin/env python3
import sys
import re
import os
import json
from io import StringIO
import sh

from lib.pushd import pushd
from lib.colortext import ANSIColor
import tracers

_git = sh.Command('/usr/bin/git')

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError
from django.db.models import Q
from django.utils import timezone

from framework.models import *

class BannedWordsAuditor(object):
	"""
	Banned words auditor 

	:ivar kernel_project:	Name of kernel project as defined in SCM and DevOps DB
	:vartype kernel_project:	str
	:ivar reference:	Staging branch or tag to scan
	:vartype reference:	str
	:ivar home_dir:		Path to directory to fetch (or clone) repo
	:vartype home_dir:	str

	"""
	email_regexp = '(?:<|)(\w+[.|\w])*@(\w+[.])*\w+(?:>|)'

	banned_word_regexes = [
		'(?:https{0,1}://){0,1}((?:\S+\.)+intel\.com(?:>|))',
		'(?:https{0,1}://)((?:[0-9]{1,3}\.){3}[0-9]{1,3})',
		'[Cc]overity|[Kk]lockwork|\w*KW ',
	]

	def __init__(self, home='', kernel_project='', reference=''):
		self.kernel_project = kernel_project
		self.reference = reference
		self.home_dir = home

	def word_check(self, text):
		"""
		Check a hunk of text for banned words

		:param text:	Hunk of text to scan
		:type text:	str
		:returns:	Dictionary of lines containing banned words
		:rtype:	dict
		"""
		banned_list = []
		f = StringIO(text)
		linenum = 0
		for line in f.readlines():
			linenum += 1
			for regex in self.banned_word_regexes:
				match = re.search(regex, line)
				if match:
					if not re.match(self.email_regexp, match.group(1)):
						banned_list.append( { "linenum" : linenum, "line" : line, "text" : match.group(1) })
		return banned_list

	def run(self, verbosity=0):
		"""
		Execute banned words scan against Git reference

		:param verbosity:	Verbosity level (0-3)
		:type verbosity:	int
		:returns:	Dictionary of lines containing banned words
		:rtype:	dict
		"""

		rows = Repository.objects.filter(project = self.kernel_project)
		if len(rows) == 0:
			raise ValueError("Repository for {} not found in database".format(self.kernel_project))
		self.repository = rows[0]

		if not os.path.exists(self.home_dir):
			os.makedirs(self.home_dir)
		with pushd(self.home_dir):
			data_out = ''
			if not os.path.exists(self.kernel_project + '/.git'):
				url = self.repository.protocol + '://' + self.repository.host + '/' + self.kernel_project
				data_out += _git.clone(url).stdout.strip().decode()
			with pushd(self.kernel_project):
				data_out += _git.fetch('--all').wait().stdout.strip().decode()
				data_out += _git.checkout('master').wait().stdout.strip().decode()
				data_out += _git.pull().wait().stdout.strip().decode()
				if verbosity > 1:
					print(data_out)
				baseline = _git.describe('--tags', self.reference , _err=print).wait().stdout.decode().strip()
				baseline = re.sub(r'(?:.*)(v[4-9]\.[0-9]+(?:-r[ct][0-9]+|\.[0-9]{1,3}(?:-rt[0-9]+){0,1}){0,1}).*$', r'\1',  baseline)
				revrange = baseline+'..'+self.reference
				if verbosity > 0:
					print(revrange)
				commit_list = _git('rev-list', '--reverse', revrange).wait().stdout.strip().decode().split("\n")
				all_items = {}
				for commit in commit_list:
					if verbosity > 0:
						print(ANSIColor("green", "Commit ID:", commit))
					commit_items = {}
					patch_items = {}
					commit_msg = _git("--no-pager", "log", "-1","--format=%b", commit).wait().stdout.decode()
					if verbosity > 2:
						print(ANSIColor("green", commit_msg))
					banned_items = self.word_check(commit_msg)
					if banned_items:
						commit_items = { "items" : banned_items }
					patch_data = _git("--no-pager", "show","--no-color", "-1","--format=", commit).wait().stdout.decode(errors="ignore")
					if verbosity > 2:
						print("PATCH DATA\n" + patch_data)
					banned_items = self.word_check(patch_data)
					if banned_items:
						patch_items = { "items" : banned_items }
					if commit_items or patch_items:
						all_items[commit] = {}
						if commit_items:
							all_items[commit]["commit_msg"] = commit_items 
						if patch_items:
							all_items[commit]["patch_data"] = patch_items
						if verbosity > 0:
							print(ANSIColor("red", json.dumps(all_items[commit],indent=4)))
		return all_items
				
if __name__ == '__main__':
	# Needed only for standalone runs, so import them here
	import textwrap
	import argparse
	import traceback

	parser = argparse.ArgumentParser(prog=sys.argv[0], description="Scans a SCM (Git) repository for banned words",
	formatter_class=argparse.RawTextHelpFormatter,
	epilog=textwrap.dedent('''
	The set commits from the speficied reference (branch or tag)
	its upstaream reference tag is scanned for internal references that
	do not elong in an external release.
	'''))

	def __validate_verbosity(value):
		ivalue = int(value)
		if ivalue < 0 or ivalue > 3:
			raise argparse.ArgumentTypeError("Invalid Verbosity Level %s" % value)
		return ivalue

	parser.add_argument('--ref', '-r', required=True, type=str, help='Branch to scan')
	parser.add_argument('--project', '-p', type=str, default='kernel-bkc', help="Kernel project from which to perform scan (default: kernel-bkc)")
	parser.add_argument('--home', '-H', type=str, default=os.environ["WORKSPACE"], help="Home directory of SCM tree location (default: {})".format(os.environ["WORKSPACE"]))
	parser.add_argument('--trace', action='store_true', default=False, help="Trace script execution")
	parser.add_argument('--verbosity', type=__validate_verbosity, default=0, help=textwrap.dedent('''\
	Set verbosity level (default: 0) : Values:
	0 : Quiet
	1 : Show Commits + Detections
	2 : Print Commit Messages
	3 : Print Patch Data'''))
	args = parser.parse_args()

	print(__file__)
	if args.trace:
		sys.settrace(tracers.trace_function_calls)

	auditor = BannedWordsAuditor(home=args.home, kernel_project=args.project, reference=args.ref)

	try:
		all_items = auditor.run(args.verbosity)
		print("Banned Words Detected:")
		print(json.dumps(all_items,indent=4))
	except Exception as e:
		print(traceback.format_exc())
