#!/usr/bin/env python3

import os
import sys
import inspect
import copy
import argparse
import logging
from ci.github.testcases import CITestCase
from ci.github.testcases.coverityscan import CoverityScan

logger = logging.getLogger(__name__)


def main():
    LOGLEVEL = os.environ.get('LOGLEVEL', 'DEBUG')
    logging.basicConfig(level=LOGLEVEL, format='%(levelname)-5s: %(message)s')

    # get all imported testcase classes
    testcases = [
        k for k, v in globals().items() \
            if inspect.isclass(v) and \
               v.__module__.startswith('ci.github.testcases.')
    ]

    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument('--ci-testcase', '-t', action='store',
                        required=True, choices=testcases, nargs="+",
                        help='Specify the test case to execute')
    parser.add_argument('--arch', '-a', action='store',
                        help='Target ARCH of the kernel compilation')
    parser.add_argument('--out-path', '-o', action='store',
                        help='Output path of the kernel compilation')
    args = parser.parse_args()

    # FIXME: support executing multiple test cases
    # create testcase instance dynamically by class name
    citc_class = globals()[ args.ci_testcase[0] ]
    kwargs = copy.deepcopy(args.__dict__)
    citc = citc_class(**kwargs)
    citc.execute()


if __name__ == '__main__':
    main()
