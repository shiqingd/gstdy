#!/usr/bin/env python3

import os
import sys
import argparse
import logging
from github import Github
from github import GithubException

logger = logging.getLogger(__name__)


RESULT2EVENT = {
    'pass': 'APPROVE',
    'passed': 'APPROVE',
    'success': 'APPROVE',
    'fail': 'REQUEST_CHANGES',
    'failed': 'REQUEST_CHANGES',
    'failure': 'REQUEST_CHANGES',
}


class GithubAction:
    def __init__(self, **kwargs):
        self.event_name = kwargs.get('event_name')
        self.token = kwargs.get('token')
        self.repo_path = kwargs.get('repo_path')
        self.event_number = kwargs.get('event_number')
        self.g = None
        self.repo = None
        self.event = None
        try:
            self.g = Github(self.token)
            self.repo = self.g.get_repo(self.repo_path)
            self.event = self._get_event()
            if not self.event:
                logger.error("Event is not found: %s/%s" % \
                               (self.event_name, self.event_number))
        except GithubException as e:
            logger.error(e)
        except Exception as e:
            logger.error(e)

    def has_event(self):
        return (self.event != None)

    def create_comment(self, comment):
        c = None
        try:
            c = self._create_comment(comment)
            logger.info("Comment created: %s/%s/%s" % \
                          (self.repo_path, self.event_name, self.event_number))
            logger.info("    comment id: %d" % c.id)
        except GithubException as e:
            logger.error(e)
        except Exception as e:
            logger.error(e)

        return c

    def post_result(self, result, comment):
        pass


class GithubPRAction(GithubAction):
    def _get_event(self):
        return self.repo.get_pull(int(self.event_number))

    def _create_comment(self, comment):
        return self.event.create_issue_comment(comment)

    def post_result(self, result, comment):
        event = RESULT2EVENT[result.lower()]
        return self.event.create_review(event=event, body=comment)


class GithubPushAction(GithubAction):
    def _get_event(self):
        return self.repo.get_commit(self.event_number)

    def _create_comment(self, comment):
        return self.event.create_comment(comment)

    def post_result(self, result, comment):
        return self._create_comment(comment)



if __name__ == '__main__':
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO')
    logging.basicConfig(level=LOGLEVEL, format='%(levelname)-5s: %(message)s')

    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument('--repo-path', '-p', action='store', required=True,
                        help='The Github repo. path, e.g. <owner>/<repo>')
    parser.add_argument('--event-name', '-e', action='store', required=True,
                        choices=['push', 'pull_request'],
                        help='Specify the event name')
    parser.add_argument('--event-number', '-n', action='store', required=True,
                        help='The event ID, e.g. github.event.pull_request.number')
    parser.add_argument('--action', '-a', action='store',
                        choices=['ci_start', 'ci_end'], required=True,
                        help='Set action choice to ci_start, ci_end')
    parser.add_argument('--comment-id', '-c', action='store',
                        help='Update the comment instead of creating a new one')
    parser.add_argument('--result', '-r', action='store',
                        choices=['SUCCESS', 'FAILURE'],
                        help='Set CI validation result')
    parser.add_argument('comment', metavar='COMMENT', help='Comment text')
    args = parser.parse_args()

    if 'GITHUB_LOGIN' in os.environ:
        login_or_token = os.environ.get('GITHUB_LOGIN')
    elif 'GITHUB_TOKEN' in os.environ:
        login_or_token = os.environ.get('GITHUB_TOKEN')
    else:
        raise AssertionError("No GITHUB_LOGIN/GITHUB_TOKEN found!")

    kwargs = {
        'token': login_or_token,
        'repo_path': args.repo_path,
        'event_name': args.event_name,
        'event_number': args.event_number,
    }
    action = None
    if args.event_name == 'push':
        action = GithubPushAction(**kwargs)
    elif args.event_name == 'pull_request':
        action = GithubPRAction(**kwargs)
    assert action.has_event(), "Cannot get %s/%s" % \
                                 (args.event_name, args.event_number)

    if args.action == 'ci_start':
        action.create_comment(args.comment)
    elif args.action == 'ci_end':
        action.post_result(args.result, args.comment)
