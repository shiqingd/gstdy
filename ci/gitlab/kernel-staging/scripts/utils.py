#!/usr/bin/env python3

import sys
import re
import subprocess
import logging

LOG_FMT = '%(asctime)-15s %(name)-10s %(levelname)-8s %(message)s'
#from config import LOG_FMT
KVERSION_MAKE_RE = re.compile('(?P<big_version>[0-9].[0-9]*).(?P<small_version>[0-9]*)(-rc)?(?P<rc_version>[1-9][0-9]*)?')

logger = logging.getLogger("Utils")
logging.basicConfig(format=LOG_FMT, level=logging.INFO)
#logger.addHandler(logging.StreamHandler(sys.stdout))

#below are kernel related functions
def get_kernelversion():
    """Must be run in a kernel directory"""
    r, o = execute_shell_cmd("make kernelversion")
    if r != 0:
        error_out(o, "fail to run make kernelversion")
        return r, "fail to run make kernelversion"
    else:
        return r, o[0]

def parse_kernelversion(kv_line):
    """Parse kernel version line to tuples"""
    m = KVERSION_MAKE_RE.match(kv_line)
    if m:
        return (m.group("big_version"), m.group("small_version"), m.group("rc_version"))
    else:
        return None

def get_commit_sha_by_kernelversion(kv_tuple, base_count=50, retry=6):
    """get commit sha from git log by kv tuple"""
    b, s, rc = kv_tuple
    linux_commit = "Linux " + str(b)
    count = base_count
    commit_sha = None
    while retry != 0:
        r, gl = execute_shell_cmd("git log --oneline -n "+str(count))
        for l in gl:
            if linux_commit in l:
                logger.info("Find release commit " + l + " include: " + linux_commit)
                commit_sha = l[:7]
                logger.info("Commit SHA: " + commit_sha)
                return commit_sha
        logger.info("Could not find release commit " + str(linux_commit) +  " in latest " + str(count) + " commits. Double count and check again.")
        count = count * 2
        retry -= 1
    logger.info("Could not find release commit in latest " + str(count) + " commits. Please check!")
    return commit_sha

def get_linux_release_commit_sha():
    """Get Linux release commit sha"""
    r, m = get_kernelversion()
    if r != 0:
        logger.info(m)
        return None
    kvtuple = parse_kernelversion(m)
    if not kvtuple:
        logger.info("Failed to parse kernel version: " + m)
        return None
    commit_sha = get_commit_sha_by_kernelversion(kvtuple)
    if not commit_sha:
        logger.info("Failed to get commit sha by current tuple: " + str(kvtuple))
    return commit_sha

#below are basic funtions
def execute_shell_cmd(command, use_shell=False,
                      decoder="utf-8", rt_output=False):
    """ shell command executor
        params: command(str), use_shell(bool)
        return: (return_code(int), output(list of strs))
    """
    logger.debug("Execute shell command: %s", command)
    if use_shell:
        logger.info("Command execution use shell = %s", str(use_shell))
    process_cmd = command.split()
    ret_code, output = 1, ''
    try:
        process = subprocess.run(process_cmd, shell=use_shell,
                                 stdout=subprocess.PIPE,)
                                 #stderr=subprocess.PIPE)
        ret_code, o = process.returncode, process.stdout
        output = o.decode(decoder).split("\n")
    except (OSError, ValueError) as e:
        logger.error("Exception raised when execute command %s. See %s",
                     command, str(e))
        ret_code, output = 1, str(e)
    finally:
        return ret_code, output

def error_out(logs, msg):
    logger.error("Error: %s", msg)
    for l in logs:
        logger.critical(l)
    return

