#!/usr/bin/env python3

"""Banned words check script"""

import re
import sys
import logging

import utils

EMBARGOED_WORDS_RE = re.compile(r'(OYB|Oyster bay|OysterBay|SPR|SPR-LCC|SPR-MCC|Sapphire Rapids|EagleStream|Eagle stream|' + \
                                r'MeteorLake|MTL)\s' + \
                                r'|not for upstream' , re.IGNORECASE)
                                #extra kwords added from removed commit, re.IGNORECASE)
BANNED_WORDS_RE = re.compile(r'http.*\.intel.com|kojiclear|([0-9]{1,3}\.){3}[0-9]{1,3}')
logger = logging.getLogger("BannedWordScan")
logging.basicConfig(format=utils.LOG_FMT, level=logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

def find_banned_words(msg, banned_words=BANNED_WORDS_RE):
    """Find banned words in a commit msg or not"""
    has_banned_words = banned_words.search(msg)
    msg_bug = None
    if has_banned_words:
        msg_bug = has_banned_words.group()
        if 'linux.intel.com' in msg_bug:
            msg_bug = None
        elif 'www.intel.com' in msg_bug:
            msg_bug = None
    return msg_bug

def parse_commits(commit_lines):
    """parse git log commit lines and transfer to commits"""
    # dict to store commit data
    commits = list()
    commit = dict()
    # iterate lines and save
    for line in commit_lines:
        if line == '' or line == '\n':
            # ignore empty lines
            pass
        elif bool(re.match('commit', line, re.IGNORECASE)):
            # commit xxxx
            if len(commit) != 0:        ## new commit, so re-initialize
                commits.append(commit)
                commit = dict()
                commit = {'hash' : re.match('commit (.*)', line, re.IGNORECASE).group(1)}
        elif bool(re.match('merge:', line, re.IGNORECASE)):
            # Merge: xxxx xxxx
            pass
        elif bool(re.match('author:', line, re.IGNORECASE)):
            # Author: xxxx <xxxx@xxxx.com>
            m = re.compile('Author: (.*) <(.*)>').match(line)
            commit['author'] = m.group(1)
            commit['email'] = m.group(2)
        elif bool(re.match('date:', line, re.IGNORECASE)):
            pass
        elif bool(re.match('    ', line, re.IGNORECASE)):
            # (4 empty spaces)
            if commit.get('subject') is None:
                commit['subject'] = line.strip()
                commit['message'] = ""
            commit['message'] += "%s\n" %(line.strip())
        else:
            logger.error('ERROR: Unexpected Line: ' + line)
    commits.append(commit)
    return commits

def main():
    """ Read git commit data and check if any of commits have any banned words.
        Suggest data create command: git log --pretty=medium base_notrusty..base_mergetrustry
    """
    start_commit = utils.get_linux_release_commit_sha()
    if not start_commit:
        logger.error("Failed to get Linux release/rc commit on current branch. Please check!")
        return 1
    r, gitlogs = utils.execute_shell_cmd("git log "+start_commit+"..HEAD")
    if r != 0:
        logger.error("Failed to run git log to fetch commit message!")
        return 2
    with open("commit.log", "w+", encoding="utf-8") as fd:
        fd.write(u"\n".join(gitlogs))
    logger.info("Start to parse git commit messages and check if any bannedwords found.")
    commits = parse_commits(gitlogs)
    commit_error = list()
    for commit in commits:
        msg_bug = find_banned_words(commit["message"])
        if msg_bug:
            commit_error.append((commit["subject"], commit["email"], msg_bug))
        msg_embargoed = find_banned_words(commit["message"], banned_words=EMBARGOED_WORDS_RE)
        if msg_embargoed:
            commit_error.append((commit["subject"], commit["email"], msg_embargoed))
    if commit_error:
        result = 'fail'
        msg = "Find %d commits have banned words in total %d commits checked." \
              %(len(commit_error), len(commits))
        for e in commit_error:
            logger.error("Subject: %s\nAuthor: %s\nFound banned words: %s\n" \
                  %(e[0], e[1], e[2]))
    else:
        result = 'pass'
        msg = "No banned words used in total %d commits checked." %len(commits)
        commit_error = None
    logger.info(msg)
    return 0 if result == "pass" else 1

if __name__ == "__main__":
    sys.exit(main())
