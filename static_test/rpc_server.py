#!/usr/bin/env python3
#
#

import sys
import os
import re
import argparse

from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class TestFuncs:
    def transfer(self, file_name):
        fd = open(file_name, 'r')
        info = fd.read()
        return info

    def receive(self, file_name):
        return 0

# Create server
def main(argv):

    #("localhost", 8000)
    host = argv[0]
    port = int(argv[1])
    print(host)
    print(port)
    server = SimpleXMLRPCServer((host,port), requestHandler = RequestHandler)

    # Register an instance; all the methods of the instance are

    server.register_instance(TestFuncs())

    # Run the server's main loop
    server.serve_forever()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
