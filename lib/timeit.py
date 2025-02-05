#!/usr/bin/env python3

import time                                                

def timeit(method):
	'''
	decorator to print elapsed execution time of a function or method
	'''

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        print('%r (%r, %r) %2.2f sec' % \
              (method.__name__, args, kw, te-ts))
        return result

    return timed
