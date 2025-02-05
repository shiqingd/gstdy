#!/usr/bin/env python3

"""Banned words check script"""

import os
import re
import sys
import yaml
import logging
from lib.utils import get_kernel_baseline, cmd_pipe, DEFAULT_LOGFMT

logger = logging.getLogger(__name__)


def find_banned_words(msg, bannedword_re, whitelist_re):
    """Find banned words in a commit msg"""
    matched = bannedword_re.findall(msg)
    matched_set = set()
    for m in matched:
        matched_set.add(m)
    msg_bug = []
    for m in matched_set:
        s = whitelist_re.search(m)
        if s:
            continue

        msg_bug.append(m)
    return msg_bug


def parse_commits(commit_lines):
    """parse git log commit lines and transfer to commits"""
    # regexp patterns for parsing each item of commit
    cmt_re = re.compile(r'^(From|Commit:)\s+([a-f0-9]{8,})(\s+|$)')
    ath_re = re.compile(r'^(From|Author):\s+(.*)\s+<(.*)>\s*$')
    tsp_re = re.compile(r'^Date:\s+')
    sub_re = re.compile(r'^Subject:\s+(.*)$')
    blk_re = re.compile(r'^\s*$')

    # dict to store commit data
    commits = []
    commit = None
    msg = None
    msg_begin = False
    i = 0
    linecnt = len(commit_lines)
    while True:
        if i < linecnt:
            line = commit_lines[i]
            i += 1
        else:
            commit['message'] = os.linesep.join(msg)
            commits.append(commit)
            break

        m = cmt_re.search(line)
        if m:
            if msg_begin:
                commit['message'] = os.linesep.join(msg)
                commits.append(commit)
                msg_begin = False

            # a new commit, initialize msg and commit
            commit = {'hash': m.group(2)}
        else:
            m = ath_re.search(line)
            if m:
                commit['author'] = m.group(2)
                commit['email'] = m.group(3)
            else:
                m = sub_re.search(line)
                if m:
                    commit['subject'] = m.group(1)
                    # msg block begins, initialize msg list
                    msg = []
                    msg_begin = True
                    # if the next line is blank, skip it
                    m = blk_re.search(commit_lines[i])
                    if m:
                        i += 1
                else:
                    # skip date line
                    m = tsp_re.search(line)
                    if m:
                        continue
                    else:
                        if msg_begin:
                            msg.append(line)

    return commits


def main():
    """ Read git commit data and check if any of commits have any banned words.
        Suggest data create command: git log --pretty=medium base_notrusty..base_mergetrustry
    """
    logging.basicConfig(format=DEFAULT_LOGFMT, level=logging.INFO)

    cmtlog = None
    if "COMMIT_LOG" in os.environ:
        assert os.path.exists(os.environ["COMMIT_LOG"]), \
               "%s does not exist" % os.environ["COMMIT_LOG"]
        with open(os.environ["COMMIT_LOG"], "r") as fd:
            cmtlog = fd.read()
    else:
        baseline, start_commit = get_kernel_baseline('HEAD')
        if not start_commit:
            logger.error("Failed to get Linux release/rc commit on current branch. Please check!")
            return 1
        logger.info("Detected baseline: %s" % baseline)
        rv, cmtlog, err = cmd_pipe("git log %s..HEAD" % start_commit)
        if rv != 0:
            logger.error("Failed to run git log to fetch commit message!")
            return 2
        with open("commit.log", "w+", encoding="utf-8") as fd:
            fd.write(cmtlog)

    # load banned words from yaml
    mydir = os.path.dirname(os.path.abspath(__file__))
    yaml_fl = os.path.join(mydir, 'bannedwords.yml')
    with open(yaml_fl, 'r') as y:
        bw_yaml = yaml.safe_load(y)
    # bw: banned word
    bw_dict = bw_yaml['bannedword']
    whitelist = bw_yaml['whitelist']
    bw_list = [ w for k in sorted(bw_dict.keys()) for w in bw_dict[k] ]
    bw_re = re.compile(r"\b(%s)\b" % '|'.join(bw_list), re.IGNORECASE)
    wl_re = re.compile(r"\b(%s)\b" % '|'.join(whitelist), re.IGNORECASE)

    logger.info("Start to parse git commit messages and check if any bannedwords found.")
    commits = parse_commits(cmtlog.splitlines())
    commit_error = list()
    for commit in commits:
        msg_bug = find_banned_words(commit["message"], bw_re, wl_re)
        if msg_bug:
            commit_error.append((commit["subject"], commit["email"], msg_bug))
    if commit_error:
        result = 'fail'
        msg = "Find %d commits have banned words in total %d commits." % \
                (len(commit_error), len(commits))
        for e in commit_error:
            logger.error("Subject: %s\nAuthor: %s\nFound banned words: %s\n" % \
                           (e[0], e[1], ", ".join(e[2])))
    else:
        result = 'pass'
        msg = "No banned words used in total %d commits." % len(commits)
        commit_error = None
    logger.info(msg)
    return 0 if result == "pass" else 1

if __name__ == "__main__":
    sys.exit(main())
