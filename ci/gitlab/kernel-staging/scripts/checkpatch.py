#!/usr/bin/env python3

"""Simple check patch parser"""

import re
import sys
import logging

import utils

CHECKPATCH_ERROR_RE = re.compile(r'total: (?P<err_count>[0-9].*) errors, (?P<war_count>[0-9].*) warnings')
logger = logging.getLogger("CheckPatch")
logging.basicConfig(format=utils.LOG_FMT, level=logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

def run_checkpatch(start_commit, end_commit, args):
    """Run checkpatch with given start, end commit and arguments"""
    cmd = "./scripts/checkpatch.pl " + args + " -g " + start_commit + ".." + end_commit
    logger.info("Checkpatch cmdline: " + cmd)
    r, gl = utils.execute_shell_cmd(cmd)
    logger.info("Checkpatch cmd executed, return: " + str(r))
    return gl
    
def parse_cplog(cplogs):
    """Parse checkpatch logs"""
    count, error, warning = 0, 0, 0
    for line in cplogs:
        per_patch_result = CHECKPATCH_ERROR_RE.match(line)
        if per_patch_result:
            count += 1
            error += int(per_patch_result.group('err_count'))
            warning += int(per_patch_result.group('war_count'))
    logger.info("Checkpatch scanned " + str(count) + " commits include " + str(error) + " errors, " + str(warning) + "warnings.")
    logger.info("Save checkpatch logs to checkpatch.log.")
    if count == 0:
        logger.error("No commit was checked! Please check log!")
        return 1
    return error

def main():
    """ Read check patch result and check error exists or not
        Suggest data create command: git log --pretty=medium base_notrusty..base_mergetrustry
    """
    start_commit = utils.get_linux_release_commit_sha()
    if not start_commit:
        logger.error("Failed to get Linux release/rc commit on current branch. Please check!")
        return 1
    gl = run_checkpatch(start_commit, "HEAD", "--no-signoff")
    if len(gl) == 0:
        logger.error("Failed to run checkpatch in current directory. Please check!")
        return 2
    with open("checkpatch.log", "w+", encoding="utf-8") as fd:
        fd.write(u"\n".join(gl))
    error_count = parse_cplog(gl)
    return error_count



if __name__ == "__main__":
    sys.exit(main())
