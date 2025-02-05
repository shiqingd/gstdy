#!/usr/bin/env python3

"""Simple check patch parser"""

import os
import re
import sys
import logging
from lib.utils import cmd_pipe, get_kernel_baseline, DEFAULT_LOGFMT

logger = logging.getLogger(__name__)


CHECKPATCH_ERROR_RE = re.compile(r'total: (?P<err_count>[0-9].*) errors, (?P<war_count>[0-9].*) warnings')


def run_checkpatch(opts):
    """Run checkpatch with given start, end commit and arguments"""
    cmd = "./scripts/checkpatch.pl --strict --codespell --no-signoff %s" % opts
    logger.info("Checkpatch cmdline: %s" % cmd)
    rv, out, err = cmd_pipe(cmd)
    logger.info("Checkpatch cmd executed, return: %i" % rv)
    return out
    
def parse_cplog(cplogs):
    """Parse checkpatch logs"""
    count, error, warning = 0, 0, 0
    for line in cplogs:
        per_patch_result = CHECKPATCH_ERROR_RE.match(line)
        if per_patch_result:
            count += 1
            error += int(per_patch_result.group('err_count'))
            warning += int(per_patch_result.group('war_count'))
    logger.info("Summary: Checkpatch scanned %i commits, including %i errors, %i warnings." % \
                  (count, error, warning))
    logger.info("Save checkpatch logs to checkpatch.log.")
    if count == 0:
        logger.error("No commit was checked! Please check log!")
        return 1
    return error

def main():
    """ Read check patch result and check error exists or not
        Suggest data create command: git log --pretty=medium base_notrusty..base_mergetrustry
    """
    logging.basicConfig(format=DEFAULT_LOGFMT, level=logging.INFO)

    if "CHKPATCH_DIR" in os.environ:
        chkpdir = os.environ["CHKPATCH_DIR"]
        opts = "--patch %s/*" % chkpdir
        # check if this is a upstreamed patch, ignore the checkpatch scan if yes
        df_re = re.compile(r'^diff --git a\/')
        up_re = re.compile(
          r'^\s*\[?\s*(?:upstream commit|commit) ([\da-f]{8,})(?: upstream\.?|)\s*\]?\s*$',
          flags=re.I)
        for path, dirs, files in os.walk(chkpdir):
            for f in files:
                isup = False
                fp = os.path.join(chkpdir, f)
                with open(fp, 'r') as fd:
                    for l in fd.read().splitlines():
                        m = df_re.search(l)
                        if m:
                            break
                        else:
                            m = up_re.search(l)
                            if m:
                                isup = True
                                break
                if isup:
                    # remove the upstreamed patch file
                    logger.info("Upstreamed patch found: %s, skip" % f)
                    os.remove(fp)
        # check if all patches have been removed
        if not os.listdir(chkpdir):
            logger.info("All are upstreamed patches, skip checkpatch scan")
            return 0
    else:
        baseline, start_commit = get_kernel_baseline('HEAD')
        if not start_commit:
            logger.error("Failed to get Linux release/rc commit on current branch. Please check!")
            return 1
        logger.info("Detected baseline: %s" % baseline)
        opts = "-g %s..%s" % (start_commit, end_commit)
    out = run_checkpatch(opts)
    if len(out) == 0:
        logger.error("Failed to run checkpatch in current directory. Please check!")
        return 2

    error_count = parse_cplog(out.splitlines())
    return error_count


if __name__ == "__main__":
    sys.exit(main())

