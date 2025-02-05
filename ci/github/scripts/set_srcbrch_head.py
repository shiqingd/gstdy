#!/usr/bin/env python3

import os
import sys
import argparse
import logging
import ssl
import xmlrpc.client as xmlrpc

logger = logging.getLogger(__name__)


class XMLRPCServer:
    def __init__(self):
        self.url = "https://ikt.bj.intel.com/api/xmlrpc/"
        self.server = xmlrpc.ServerProxy(self.url, context=ssl.SSLContext())


    def set_srcbrch_head(self, prid, head):
        return self.server.set_pr_srcbrch_head(prid, head)


    def test_xmlrpc(self, text):
        return self.server.test_xmlrpc(text)


if __name__ == '__main__':
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO')
    logging.basicConfig(level=LOGLEVEL, format='%(levelname)-5s: %(message)s')

    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument('github_prid', metavar='GITHUB_PRID',
                        help='Github pullrequest ID')
    parser.add_argument('srcbrch_head', metavar='SRCBRCH_HEAD',
                        help='head of the source branch')
    args = parser.parse_args()

    # establish the connection to IoTG devops server via xmlrpc
    ido_srv = XMLRPCServer()
    logger.info("Connect %s" % ido_srv.url)
    logger.info("Set source branch head:\n    github prid: %s\n    head: %s" % \
                  (args.github_prid, args.srcbrch_head))
    rv = ido_srv.set_srcbrch_head(args.github_prid, args.srcbrch_head)
    logger.info("    result: %s" % "done" if rv else "FAILED")
