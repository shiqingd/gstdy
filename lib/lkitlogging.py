#!/usr/bin/env python3

import os
import sys
import sh
import logging
from autologging import TRACE

__log = logging.getLogger(sys.argv[0] != '' and sys.argv[0] or '<console>')
__log.setLevel(TRACE)

# formatter = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s', '%m/%d/%Y %H:%M:%S')
# formatter_nl = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s\n', '%m/%d/%Y %H:%M:%S')

formatter = logging.Formatter( '%(funcName)s - %(message)s', '%m/%d/%Y %H:%M:%S')
formatter_nl = logging.Formatter( '%(funcName)s - %(message)s\n', '%m/%d/%Y %H:%M:%S')

if not "LOGFILE" in os.environ:
        # create file handler that logs debug and higher level messages
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.terminator = ''
        ch.setLevel(TRACE)
        ch.setFormatter(formatter_nl)
#        ch.setFormatter(formatter)
        __log.addHandler(ch)
else:
        # create formatter and add it to the handlers
        # add the handlers to logger
        fh = logging.FileHandler(os.environ["LOGFILE"])
        fh.setLevel(TRACE)
        fh.setFormatter(formatter)
        __log.addHandler(fh)
__log.propagate = False

def getlog():
	return __log
