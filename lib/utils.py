#!/usr/bin/env  python3

import sys
import os
from datetime import datetime
import sh
import json
import traceback
import io
import shutil
import re
import subprocess
from subprocess import PIPE
import pexpect
import pty
from  lib.dry_run import dryrunnable, traceable, traceable_method
from lib.pushd import pushd
import select
import math
import fcntl
import tarfile
import tempfile
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import logging
logger = logging.getLogger(__name__)
# disable requests InsecureRequestWarning until it is CRITICAL
logging.getLogger('requests').setLevel(logging.CRITICAL)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_datetime = datetime.utcnow()
_datetime_string = _datetime.strftime("%y%m%dT%H%M%SZ")

_make = sh.Command("/usr/bin/make")
_rsync = sh.Command("/usr/bin/rsync")
_git = sh.Command("/usr/bin/git")
_bash = sh.Command("/bin/bash")
_wget = sh.Command("/usr/bin/wget")
_nproc = sh.Command("/usr/bin/nproc")
_ssh = sh.Command("/usr/bin/ssh")


ANDROID_ARTIFACTORY_BASE = "https://mcg-depot.intel.com/artifactory/cactus-absp-jf/build/eng-builds"

# for quiltdiff tracking tool
QUILTDIFF_URI = "otcpkt.bj.intel.com:9000"
TRIGGER_QUILTDIFF_BASE_URL = "http://"+QUILTDIFF_URI+"/trigger/qd/"
QUILTDIFF_CHGLST_BASE_URL = "http://"+QUILTDIFF_URI+"/json/"

DEFAULT_LOGFMT = "%(asctime)-15s %(levelname)-8s %(message)s"


#
# Functions
#

def strip_extra_newlines(text: str):
	return re.sub(r'[\r\n]+', ' ', text)

def bash_source(script):
	"""
	Reads and inline-processes a Bash script and adds any
	new environment variables to the caller's os.environ{}
	"""
	import subprocess
	import os
	proc = subprocess.Popen(
		['bash', '-c', 'set -a && source {} && env -0'.format(script)], 
		stdout=subprocess.PIPE, shell=False)
	output, err = proc.communicate()
	output = output.decode('utf8')
	env = dict((line.split("=", 1) for line in output.split('\x00') if line))
	os.environ.update(env)
	return env

def die(*argv):
	''' Print specified error messages and then exit with an exit code of 1 '''
	traceback.format_exc()
	warn(*argv)
	sys.exit(1)

def warn(*argv):
	''' Print an error message to stderr '''
	for line in argv:
		sys.stdout.write(line + "\n")

def base_version(domain, stable_kernel, kernel_version, domain_version):
	'''
	Capture the base kernel version for the $domain branch and verify
	it is the same as or a descendent of $kernel_verison. If so, return
	domain_version.

	:param domain
	:param stable_kernel: ???
	:param kernel_version: ???
	:param domain_version: ???
	:returns: Base Kernel Version
	'''
	domain_version = _git.merge_base(domain, stable_kernel).stdout.strip().decode()
	if kernel_version == domain_version: 
		return _git.merge_base("--is-ancestor", domain_version, kernel_version)
	else:
		return domain_version

def git_diff(ref1, ref2):
	'''
	Use git-diff to compare a merge branch with a rebasing/linear branch
	and verify that they are the same. If there are differences, drop
	into a subshell and allow the user to do some repair before exiting
	the subshell to continue.

	:param ref1: ???
	:param ref2: ???
	:returns: None
	'''
	try:
		_git.diff("--exit-code", ref1, ref2)
	except Exception:
		warn("%s and %s do not match!" % (ref1, ref2))
		warn("Please resolve diffs and exit shell to continue")
		bash_subshell("FIX DIFFS")

@traceable()
def checkout(source, target): 
	''' 
	Check out a local (target) instance of a (source) branch.

	:param source: ???
	:param target: ???
	:returns: None
	'''
	try:
		traceable_method(_git, "branch", "-D", "-q", re.sub('origin/', '', source))
	except Exception as e:
		print(strip_extra_newlines(str(e)))

	try:
		traceable_method(_git, "branch", "-D", "-q", re.sub('origin/', '', target))
	except Exception as e:
		print(strip_extra_newlines(str(e)))

	if not source.startswith('origin/'):
		source = 'origin/' + source

	try:
		traceable_method(_git, "pull")
		traceable_method(_git, "checkout", "-b", target, source )
	except Exception as e:
		try:
			print(strip_extra_newlines(str(e)))
			traceable_method(_git, "checkout", source )
		except Exception:
			die(strip_extra_newlines(str(e)))
	try:
		traceable_method(_git, "reset", "--hard")
	except Exception as e:
		die(strip_extra_newlines(str(e)))

@dryrunnable()
def checkout_local(target):
	'''
	Check out a local (target) branch.

	:param target: ???
	:returns: None
	'''
	try:
		_git.checkout(target).wait()
	except Exception:
		die("Unable to checkout "+target)

@dryrunnable()
def checkout_create_branch(target):
	"""
	Create a branch

	:param target: Branch name to create.
	:returns: None
	
	"""
	print("creating branch ", target)
	try:
		_git.checkout("-b", target).wait()
	except Exception:
		die("Unable to checkout "+target)

@dryrunnable()
def reset_remote(source):
	'''
	Hard reset to the source

	:param source: ???
	:returns: None
	'''
	try:
		_git.reset("--hard", source).wait()
	except Exception:
		 die("Unable to reset " + source)

def get_sha_branch_tip(branch):
	'''
	# Capture the SHA that is the tip of the specified branch.
	# If the branch does not exist, we exit with an error message.

	:param branch: ???
	:returns: tip Captures SHA
	:rype tip: str
	'''
	try:
		tip = _git("rev-parse", "--verify", branch).wait().stdout.strip()
	except Exception as e:
		return None
	_git.log("-n1", "--format=%H", tip).wait()
	return tip

@dryrunnable()
def cherry_pick(rebasing_base, rebasing_kernel, zzz, commits):
	'''
	Cherry-pick the new patches to the rebasing branch.

	:param rebasing_base: ???
	:param rebasing_kernel: ???
	:param zzz: ???
	:param commits: ???
	:returns: None
	'''
	# Initialize the branch to rebasing_base
	try:
		_git.checkout( rebasing_kernel ).wait()
	except Exception:
		die("Unable to checkout "+rebasing_kernel)
	try:
		_git.reset( "--hard", rebasing_base).wait()
	except Exception:
		die("Failed to reset "+rebasing_kernel+" to "+rebasing_base)

	# Abort if there is nothing to cherry-pick
	count = _git.rev_list("-n", "1", "--count", zzz).wait().stdout.strip()
	if count == "0":
		return

	# Cherry-pick the desired commits
	for commit in commits:
		try:
			_git.cherry_pick(commit)
		except Exception:
			warn("Failed to cherry-pick {} to {}".format(commit, rebasing_kernel))
			warn("Please resolve conflicts and exit shell \n to continue")
			bash_subshell("FIX CHERRY-PICK")

@dryrunnable()
def resolve_conflicts(reference,prompt, warning):
	'''
	Automatically resolve a merge conflict, when possible, by checking
	out the conflicted files from a reference branch. When it is not
	possible to resolve the conflict automatically, drop to a prompt
	and allow the user to take care of it.

	:param reference
	:param prompt
	:param warning
	:returns: None

	'''
	flist = []

	output = _git.status("--porcelain").stdout.decode().strip().split("\n")
	prefix_file_tups = [tuple(elem) for elem in (output.split())]
	for prefix, filename in prefix_file_tups:
		if prefix == 'UU':
			flist.append(filename)

	conflict = False

	for prefix, filename in prefix_file_tups:
		if prefix[0] not in set(["ADCMR"]):
			conflict = True
			break
	if len(flist) > 0:
		_git.checkout([reference] + flist)
	if conflict:
		warn(warning)
		warn("Please resolve conflicts. Exit shell to continue")
		bash_subshell(prompt)
	_git.commit("--no-edit") # In case we forget...

@dryrunnable()
def merge_branch( kernel, domain, merge_point):

	'''
	Merge the domain branch into the non-rebasing branch. Note that we
	merge to the merge_sha as determined by the last commit sha that
	is passed in the commits string. This accounts for the cases where
	we do not want to merge the entire branch (e.g. android-4.9.y).

	:param kernel: ???
	:param domain: ???
	:param merge_point: ???
	:returns: None

	'''
	try:
		_git.checkout(kernel)
	except Exception:
		die("Unable to checkout " + kernel)
	try:
		_git.merge("--no-ff", "merge_point", "--log", "-m", "Merge {} into {}".format(domain, kernel))
	except Exception:
		resolve_conflicts("rebasing/{}".format(kernel),
			"FIX MERGE Failure to merge {} into {}".format(domain, kernel), "")

@dryrunnable()
def check_merged(base_branch, domain):
	'''
	Check to see if a branch has been fully merged. If it there
	are patches to be merged, return a list of commits that need
	to be cherry-picked.
	
	Note that check_merged uses the git-cherry command. The commit
	SHAs prefixed with -. Those prefixed with + do not - these are
	the ones we care about. This function filters them out and returns
	a list of SHAs for commits that are new and not included yet in
	the release.

	:param base_branch: ???
	:param domain: ???
	:returns: None

	'''

	try:
		commits=_git.cherry( base_branch, domain).stdout.decode().strip().split()
		ii = iter(commits)
	except Exception:
		die("Failed to run: _git.cherry( $base_branch $domain")
	all_commits = []
	new_commits = []
	try:
		while ii:
			sign = ii.__next__()
			commit = ii.__next__()
			all_commits.append(commit)
			if sign == '+':
				new_commits.append(commit)
	except StopIteration:
		pass
	return new_commits

@dryrunnable()
def log_run_cmd(label, cmd, *args):
	current_directory = os.getcwd()
	log_file_name = "{}/build.log".format(current_directory)
	err_file_name = "{}/build.err".format(current_directory)
	log_file = open(log_file_name, "ab")
	error_file = open(err_file_name, "ab")

	header = "({}) {} {}\n".format(label, cmd, ' '.join(args)).encode("utf-8")
	log_file.write(header)
	error_file.write(header)

	prc = subprocess.run([cmd, *args], stdout=PIPE, stderr=PIPE)

	# Stderr gets written after stdout; Python really has a problem
	# with interleaving things the way that you'd normally get from tee.

	log_file.write(prc.stdout)
	sys.stdout.write(prc.stdout.decode("utf-8"))
	error_file.write(prc.stderr)
	sys.stderr.write(prc.stderr.decode("utf-8"))

	log_file.close()
	error_file.close()

	return prc.returncode

@dryrunnable()
def check_build(local_branch, target, arch_type, *files):

	'''
	Check to see if a branch will build

	:param local_branch: ???
	:param target: ???
	:param arch_type: ???
	:param files

	'''

	checkout_local(local_branch)
	print("check if it will build "+target)

	if arch_type == "arm64":
		make_cmd = "make ARCH={} CROSS_COMPILE = aarch64-linux-gnu-".format(arch_type)
	else:
		make_cmd = "make ARCH={} ".format(arch_type) + " CROSS_COMPILE=/opt/poky/2.4.2/sysroots/x86_64-pokysdk-linux/usr/bin/x86_64-poky-linux/x86_64-poky-linux-"

	ret = 1
	if len(files) > 0:
		# use merge_config to bring all fragments together
		# just merge, don't try to do any make *config updates
		print ("Merging", list(args))
		log_run_cmd(local_branch, make_cmd, "distclean")
		ret = log_run_cmd(soc_config, "scripts/kconfig/merge_config.sh", soc_config, args)
		if ret != 0:
			pass
			#errexit=ret # save error exit state restore later
		log_run_cmd(local_branch, make_cmd, "-j", _nproc().strip())
	else:
		for config in [ 'allyesconfig', 'allmodconfig', 'allnoconfig' ]:
			log_run_cmd(local_branch, make_cmd, "distclean")
			ret = log_run_cmd(local_branch, make_cmd, config)
			if ret != 0:
				pass
				# errexit=ret # save error exit state restore later
			ret = log_run_cmd(local_branch, make_cmd, "-j",  _nproc().strip())
			save_ret = ret
			if save_ret != 0:
				ret = save_ret
	return ret

@dryrunnable()
def commit_local(msg):
	'''
	commit all local changes to the config
	presumes we are on the correct local branch

	:param msg: ???

	'''
	try:
                diff_text = _git.diff("--name-status" , _tty_out=False).wait().strip()
                if diff_text:
                    _git.commit("-as", "-m" , msg)
	except Exception:
		die("Commit Failed")

@dryrunnable()
def create_tag(tag_name, msg):
	'''
	Tag the current HEAD

	:param tag_name: ???
	:param mag - mag
	:returns: None

	'''
	print ("git tag -a ", tag_name)
	_git.tag("-a", tag_name, "HEAD", "-m", msg)

@dryrunnable()
def push_tag(remote_name,tag_name):
	# Push tag to the remote
	print ("git push tag ", remote_name, tag_name)
	_git.push(remote_name, tag_name)

@dryrunnable()
def push_remote( remote_name, local_branch, remote_branch, force_push=False):
	'''
	# Push to the remote branch

	:param remote_name: ???
	:param local_branch: ???
	:param remote_branch: ???
	:param force_push: ???

	'''
	args = []
	if force_push:
		args.append("-f")
	args += [ remote_name, local_branch + ":refs/heads/" + remote_branch ]
	_git.push( args )

@dryrunnable()
def push_remote_test( remote_name, local_branch, remote_branch, force_push=False):
	'''
	# Dummy version of push_remote.

	:param remote_name: ???
	:param local_branch: ???
	:param remote_branch: ???
	:param force_push: ???

	'''
	args = []
	if force_push:
		args.append("-f")
	args += [ remote_name, local_branch + ":refs/heads/" + remote_branch ]
	#_git.push( args )
	print("PUSH_REMOTE_TEST Dummy: git push", ' '.join(args))

@dryrunnable()
def rebase_local_remote(remote_name, local_branch, remote_branch):
	# Rebase local to the remote branch
	_git.rebase( remote_name + '/' + remote_branch, local_branch)

def date_stamp(remote_branch, major_kernel_version):
	'''
	# get the date string, week, and kernel version
	#
	:param remote_branch
	:param major_kernel_version
	:return 
	:return date_string
	:return week.day
	:return kernel_version

	'''
	d = int(
		_git.log("-1","--format=%ct",remote_branch, _tty_out=False).stdout)

	dt = datetime.fromtimestamp(d)
	date_string = dt.strftime("%Yw%V.%w-%H%M%S)")
	week_day = dt.strftime("w%V.%w")
	desc = _git.describe("--tags","--match","v[0-9].*",remote_branch).stdout.decode()
	kernel_version = re.sub(r'(v4\.[0-9]{1,2}(?:-rc[0-9]{1,2}|\.[0-9]{1,3}|))', r'\1', desc)
	return date_string, week_day, kernel_version

@dryrunnable()
def __do_repo_download(repo_args, dry_run):

	_repo = sh.Command(os.path.join(os.environ["HOME"],"bin/repo"))
	try:
		_repo(repo_args).wait()
	except sh.ErrorReturnCode as e:
		print("repo download failed")
		return e.exit_code

@dryrunnable()
def bash_subshell(purpose):
	"""
	Create a subshell with a prompt so that the user can manually fix
	any conflicts that have occured. The "purpose" parameter becomes
	part of the prompt.

	:param purpose:	Prompt

	"""
	print(purpose)
	# I don't know if it's possible to set an environment variable here.
	pty.spawn(["/bin/sh"])

@dryrunnable()
def push_github(remote, local_branch, remote_branch):
	"""
	Push to gihub remote branch

	:param remote:	???
	:param local_branch:	???
	:param remote_branch:	???

	"""
	# FIXME set prompt "(%|#|\\$) $"
	child = pexpect.spawn("git push %s %s:%s" % (remote, local_branch, remote_branch))
	child.expect("Username for")
	child.sendline("sys-oak")
	child.expect("Password for")
	child.sendline(os.environ.get('SYS_OAK_CRED_AD'))
	child.expect(pexpect.EOF, timeout = None)

@dryrunnable()
def push_tag_github( remote_name, tag_name):
	"""
	Push tag to gihub remote branch

	:param remote:	???
	:param local_branch:	???
	:param remote_branch:	???
	# set prompt "(%|#|\\$) $"

	"""
	# FIXME set prompt "(%|#|\\$) $"
	child = pexpect.spawn("git push %s %s" % (remote_name, tag_name))
	child.expect("Username for")
	child.sendline("sys-oak")
	child.expect("Password for")
	child.sendline(os.environ.get('SYS_OAK_CRED_AD'))
	child.expect(pexpect.EOF, timeout = 10)

def get_sha_last_commit(kernel_dir):
	'''
	get the sha of the last commit

	:param kernel_dir:	???
	:returns:	Git Commit ID (SHA)
	:raises:	LookupError

	'''
	with sh.pushd(kernel_dir):
		sha1 = _git.log("--pretty=format:%h","-n1","--abbrev=8",_tty_out=False).stdout.strip().decode()
		if sha1 == '':
			raise LookupError("%s HEAD SHA not found" % kernel_dir)
	return sha1

def get_intel_ww(_year, _month, _day):

	'''
	return the intel work week from year, month, and day.

	Date %U option for work week is very close to what intel uses.
	%U option start on 00 for some years and for other it starts on 01.
	on the years it starts on 00 we need to add 1 to get the Intel work week.

	:param _year: ???
	:param _month: ???
	:param _day: ???

	:returns: _ww - The Intel Work Week as str()

	'''
	_ww = int(datetime.strptime(_year+"-"+_month+"-"+_day, "%Y-%m-%d").strftime("%U"))
	_ww_begin_of_year = int(datetime.strptime(_year+"-01-01", "%Y-%m-%d").strftime("%U"))
	_ww_begin_of_next_year = int(datetime.strptime(str(int(_year)+1)+"-01-01", "%Y-%m-%d").strftime("%U"))

	if _ww_begin_of_year == 0 :
		_ww += 1
	return str(_ww)

def get_ww_string(staging_number):
	'''
	Returns  the work week string using the staging number,
	AND the release string using the work week string and staging number

	:param staging_number
	:returns: date_string
	:returns: release_string

	'''
	_date = datetime.strptime(staging_number, '%y%m%dT%H%M%SZ')
	_year=_date.strftime("%Y")
	_month=_date.strftime("%m")
	_day=_date.strftime("%d")
	_dow=_date.strftime("%w")
	_time=_date.strftime("%H%M%S")

	_ww = get_intel_ww(_year,_month,_day)

	date_string = staging_number
	release_string = staging_number+" / "+_year+"w"+_ww+"."+_dow+"-"+_time+"/"+_date.strftime("%Y-%m-%d %H:%M:%S")

	return date_string, release_string

def get_my_dir(path):
	"""Returns the directory of the argument passed to it.
	get_my_dir("/foo/bar/baz") returns "/foo/bar/"."""
	return os.path.dirname(path)

@dryrunnable()
def echo_to_file(string, file, append=False):
	"""
	Emulates the Bash command-line:
	echo <string> > file
	"""
	with open(file, append and "a" or "w") as outfile:
		outfile.write(string)

# FIXME - this should be moved to a class method of class *Template()
def template_compute(template, params):
	"""
	Computes a string based on a template in the following format:

	'"{}".format(<key>)'

	Each 'key' corresponds to a key in the dictionary argument 'params'

	:param template:  template to use
	:type template: str
	:param params:	Dictionary of parameters to fill into template
	:type template: dict

	.. note: This should be moved to a class method of class *Template()
	"""

	token = '<([a-z]+)>'
	format_string = re.sub(token, 'params["\\1"]', template)
	return eval(format_string)

def find_file_in_sys_path(filename):
	"""
	Finds a file within PYTHONPATH (sys.path)

	:param filename:  file to find (single file name or relative path)
	:type template: str
	:returns: full path of file name if found
	:rtype: str
	:raises: FileNotFoundError

	"""

	for path in sys.path:
		fullpath = os.path.join(path,filename)
		if os.path.exists(fullpath):
			return fullpath
	raise FileNotFoundError("Cannot find file %s in directories in sys.path" % filename)


def cmd(command, logger=logger,
        stdout_log_level=logging.INFO,
        stderr_log_level=logging.DEBUG,
        exit_on_fail=False,
        errmsg=None):
    """
    Variant of subprocess.run that accepts a logger instead of stdout/stderr,
    and logs stdout messages via logger.info and stderr messages via
    logger.error.

    :param command: shell command described by a string or string list.
    :param logger: the logger which output is printed to. Use
           logging.basicConfig() to initialize the default logger at the root
           caller.
    :param stdout_log_level: set the level of output for the logger.
    :param stdout_log_level: set the level of stderr for the logger.
    :param exit_on_fail: if True, exit the process if there is any failure.
    :param errmsg:: send fail message to logger.error if cmd fails.
    """
    logger.debug(command)
    proc = subprocess.Popen(command,
                            shell=True,
                            executable="/bin/bash",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    log_level = {
        proc.stdout: stdout_log_level,
        proc.stderr: stderr_log_level
    }

    def check_io():
        ready_to_read = select.select(
            [proc.stdout, proc.stderr], [], [], 1000)[0]
        for io in ready_to_read:
            line = io.readline().decode()
            if not line:
                continue
            logger.log(log_level[io], line[:-1])

    # keep checking stdout/stderr until the proc exits
    while proc.poll() is None:
        check_io()

    check_io()  # check again to catch anything after the process exits

    rc = proc.wait()
    if rc != 0:
        emsg = errmsg if errmsg else "The command failed"
        if exit_on_fail:
            logger.error("%s(exit_code: %d), terminated." % (emsg, rc))
            sys.exit(rc)
        else:
            logger.error("%s(exit_code: %d), ignored." % (emsg, rc))
            return rc
    else:
        return rc


def cal_cpu_num(max_cpu_multiplier=0.95, memory_per_job_gb=1):
    """
    Compute the number of parallel jobs according to the number of
    processors and available ram size

    :param max_cpu_multiplier: the portion of cpus that are used to run
           the parallel jobs
    :type max_cpu_multiplier: float
    :param memory_per_job_gb: the number of memory in GB needed for a job
    :type memory_per_job_gb: float
    :returns: the actual number of parallel jobs supported by cpu and mem
    :rtype: int

    """

    cpuinfo_fl = '/proc/cpuinfo'
    meminfo_fl = '/proc/meminfo'
    cpuinfo = None
    meminfo = None
    cpu_related_pjobs = 1
    mem_related_pjobs = 1
    with open(cpuinfo_fl, 'r') as f:
        cpuinfo = f.read()
    with open(meminfo_fl, 'r') as f:
        meminfo = f.read()

    cpu_related_pjobs = math.floor(
        float(len(re.findall('processor', cpuinfo))) * max_cpu_multiplier)

    m = re.search('MemAvailable:\s+(\d+)\s+([kKmMgG])B', meminfo)
    if m:
        ram_sz, unity = int(m.group(1)), m.group(2)
        unity = unity.lower()
        if unity == 'k':
            ram_sz = ram_sz / 1024.0 / 1024.0
        elif unity == 'm':
            ram_sz = ram_sz / 1024.0

        # take around 1 GB per job
        mem_related_pjobs = math.ceil(float(ram_sz) / memory_per_job_gb)
    return min([cpu_related_pjobs, mem_related_pjobs])


class ShCmdError(Exception):
    pass


def cmd_pipe(command):
    logger.debug("Run shell cmd: %s", command)
    returncode = 1
    output = None
    error = None
    try:
        proc = subprocess.Popen(command,
                                shell=True, \
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                executable='/bin/bash')

        output = proc.stdout.read().decode().strip()
        error = proc.stderr.read().decode().strip()
        returncode = proc.wait()
    except (OSError, ValueError) as e:
        returncode = 2
        error = str(e)
    finally:
        if output:
            logger.info(output)
        if error:
            logger.error(error)
        return returncode, output, error


@dryrunnable()
def is_branch(repo_url, ref):
    """
    Check if the ref is a branch or tag in the git repo.

    param repo_url: the url of the git repository
    param ref: ref of the branch or tag
    returns: boolean
    """

    output = ''
    try:
        output = _git(
            "ls-remote", "--heads", "--tags", repo_url, ref).stdout.decode()
        logger.info(output)
    except Exception:
        die("Failed ls-remote: %s, %s" % (repo_url, ref))
    match = re.search(r'refs/tags', output)
    return (match is None)


def get_kernel_baseline(ref, is_rt=False):
    """
    Get the upstream kernel version for a revision(branch/tag)

    param ref: kernel branch/tag/sha1
    returns: (kernek version, sha1)
    """

    commands = r"""
    declare rev=%s
    declare is_rt=%s
    declare tmpfl=/tmp/tags.$$
    git log --decorate=full --simplify-by-decoration --pretty=oneline ${rev} | \
      sed -rn 's/^([0-9a-f]+)\s+\(tag(:\s+|:\s+refs\/tags\/)(v[0-9]+\.[0-9\.rct-]*),*.*$/\3.\1/p' \
        > $tmpfl
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        exit 1
    fi
    # output sample:
    #   v4.17-rc7.commit
    #   v4.17-rc6.commit
    #   v4.17-rc5.commit
    #   v4.17.commit
    # or:
    #   v4.14-rc8.commit
    #   v4.14.55.commit
    #   v4.14.54.commit
    # strip '-rcN' and commit, then sort, the last one is the latest base
    declare kernel_ver
    declare kernel_ver_base
    # disable errtrace here
    set +e
    if [[ "${rev}" =~ \-rt[0-9]+ ]] || [ "$is_rt" == "true" ]; then
        # for rt kernel tag
        kernel_ver_base=$(\
            grep -E '\-rt[0-9]+' $tmpfl | \
              sed -r -e 's/-rc[0-9]+//' \
                     -e 's/-rt[0-9]+//' \
                     -e 's/\.[0-9a-f]{4,}$//' | \
                sort -t'.' -k1.2,1n -k2,2n -k3,3n | tail -1)
        # check if official release(i.e. w/o -rcN) exists
        kernel_ver=$(\
            grep -E "^${kernel_ver_base}-rt[0-9]+\.[0-9a-f]{4,}\$" $tmpfl | \
              sort | tail -1)
        test -z "$kernel_ver" && \
          kernel_ver=$(\
            grep -E "^${kernel_ver_base}-rc[0-9]+-rt[0-9]+" $tmpfl | \
              sort | tail -1)
    else
        # for kernel tag w/o -rtN
        kernel_ver_base=$(\
            grep -vE '\-rt[0-9]+' $tmpfl | \
              sed -r -e 's/-rc[0-9]+//' \
                     -e 's/-rt[0-9]+//' \
                     -e 's/\.[0-9a-f]{4,}$//' | \
                sort -t'.' -k1.2,1n -k2,2n -k3,3n | tail -1)
        # check if official release(i.e. w/o -rcN) exists
        kernel_ver=$(grep -E "^${kernel_ver_base}\.[0-9a-f]{4,}\$" $tmpfl)
        test -z "$kernel_ver" && \
          kernel_ver=$(\
              grep -E "^${kernel_ver_base}-rc[0-9]+\.[0-9a-f]{4,}" $tmpfl | \
                sort | tail -1)
    fi
    rm -f $tmpfl
    # note that the double percent signs are escaped by python
    echo "${kernel_ver%%.*} ${kernel_ver##*.}"
    """ % (ref, "true" if is_rt else "false")
    (rc, out, err) = cmd_pipe(commands)
    if rc != 0:
        raise ShCmdError("get kernel baseline failed: %s\n%s" % (ref, err))
    return out.strip().split()


def make_tarfile(output_filename, source_dir, compression='gz'):
    """
    Create tarfile
    param output_file: the dest tarball file path
    param source_dir: the source folder
    param compression: the compression format, gz, xz, bz2
    returns: None
    """

    with tarfile.open(output_filename, "w:%s" % compression) as tar:
        tar.add(source_dir, arcname='.')

def sed_inplace(cmd=None, pattern=None, repl=None, filename=None):
	'''
	Perform the pure-Python equivalent of in-place `sed` substitution: e.g.,
	`sed -i -e 's/'${pattern}'/'${repl}' "${filename}"`.
	FIXME : Only 's' and 'd' supported at thie time
	'''
	r = re.compile(pattern)

	# NOTE: using mode="w" instead of mode="w+b" to better support text
	with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
		with open(filename) as src_file:
			for line in src_file:
				if cmd == 's':
					tmp_file.write(r.sub(repl, line))
				elif cmd == 'd':
					if not r.search(line):
						tmp_file.write(line)
				else:
					raise ValueError('sed_inplace(): Unsupported cmd={}'.format(cmd))

	# Overwrite the original file with the munged temporary file in a
	# manner preserving file attributes (e.g., permissions).
	shutil.copystat(filename, tmp_file.name)
	shutil.move(tmp_file.name, filename)


def requests_retry_session(retries=10,
                           backoff_factor=0.3,
                           status_forcelist=(401, 500, 502, 504),
                           session=None):
    session = session or requests.Session()
    retry = Retry(total=retries,
                  read=retries,
                  connect=retries,
                  backoff_factor=backoff_factor,
                  status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def requests_get(url, q_data=None, auth=None):
    resp = None
    logger.debug("Query URL: %s" % url)
    try:
        resp = requests_retry_session().get(url, auth=auth, verify=False)
        logger.debug(resp.text)
        if resp.status_code != requests.codes.ok:
            logger.error(resp.reason)
            logger.error(resp.text)
            sys.exit(resp.status_code)
    except Exception as e:
        logger.error(e)
        logger.error("requests.get() failed after retries: %s, terminated" % \
                       e.__class__.__name__)
        sys.exit(500)

    return resp.text


def requests_post(url, data, headers, auth, verify=False):
    resp = None
    logger.debug("Post URL: %s" % url)
    try:
        resp = requests_retry_session().post(url,
                                             data=data,
                                             headers=headers,
                                             auth=auth,
                                             verify=verify)
    except Exception as e:
        logger.error(e)
        logger.error("requests.post() failed: %s, terminated" % \
                       e.__class__.__name__)
        sys.exit(500)

    return resp


def lock_file(fd):
    fcntl.flock(fd, fcntl.LOCK_EX)


def unlock_file(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
