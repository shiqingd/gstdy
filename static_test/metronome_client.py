#!/usr/bin/env python

"""
Collector, XML RPC server is a function cluster which collect
results of triggered actions on other platforms.
"""

import sys
import argparse
import logging
if sys.version_info[0] > 2:
    import xmlrpc.client as xmlrpc
else:
    import xmlrpclib as xmlrpc

sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
LOG_FMT = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sh.setFormatter(LOG_FMT)

logger = logging.getLogger('CollectorClient')
logger.setLevel(logging.DEBUG)
logger.addHandler(sh)

SERVER = ('http://otcpkt.bj.intel.com:9090')

def send(server_url, result, job_id, msg, vendor, data):
    try:
        server = xmlrpc.ServerProxy(server_url)
        logger.info("Platform %s task finished, result: %s", vendor, "result")
        logger.debug("Data: %s", data)
        r, m = server.receive(result, job_id, msg, vendor, data)
        if r:
            logger.info(m)
        else:
            logger.error(m)
    except Exception as e:
        logger.error("Exception caught when send result to collector.")
        logger.error("Exception: %s", e)
    return

def parser_generator():
    """"""
    parser = argparse.ArgumentParser(description="Patch collector")
    parser.add_argument('-v', dest='vendor', action='store')
    parser.add_argument('-i', dest='job_id', action='store')
    parser.add_argument('-r', dest='result', action='store')
    parser.add_argument('-m', dest='msg', action='store')
    parser.add_argument('-s', dest='server', action='store', required=False)
    #option paremeters
    parser.add_argument('--add-msg-to-data', dest="data_add_msg", action='store_true')
    parser.add_argument('--need-stop', dest="need_stop", action='store_true')
    #parameters should be a string in dict format
    return parser

def main(arg_list):
    """"""
    parser = parser_generator()
    if len(arg_list) == 0:
        parser.print_help()
        return 1
    args = parser.parse_args(arg_list)
    server = args.server if args.server else SERVER
    logger.info("Connect to RPC server: %s", server)
    logger.info("Send job result to collector server.")
    logger.info("Task result: %s, leave msg: %s", args.result, args.msg)
    data = dict()
    data["result"] = args.result
    if args.data_add_msg:
        data["msg"] = args.msg
    if args.need_stop:
        #vendor job failed so it will stop after next update job executed
        data["vendor_stop_next"] = args.need_stop
    send(server, args.result, args.job_id, args.msg, args.vendor, data)
    return

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

