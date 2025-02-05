#!/usr/bin/env python3

"""Simple check patch parser"""

import re
import sys

CHECKPATCH_ERROR_RE = re.compile(r'total: (?P<err_count>[0-9].*) errors')


def main(data):
    """ Read check patch result and check error exists or not
        Suggest data create command: git log --pretty=medium base_notrusty..base_mergetrustry
    """
    count = 0
    error = 0
    for line in data:
        per_patch_result = CHECKPATCH_ERROR_RE.match(line)
        if per_patch_result:
            count += 1
            error += int(per_patch_result.group('err_count'))
    print("Find %d errors in total %d patch"%(error, count))
    return error


if __name__ == "__main__":
    log_fn = sys.argv[1]
    with open(log_fn, 'r', errors='ignore', encoding='utf-8') as fd:
        data_lines = fd.readlines()
    sys.exit(main(data_lines))
