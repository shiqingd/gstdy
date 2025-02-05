#!/usr/bin/env python3
"""

Executing Trace Support Functions

"""

__modules_to_trace = set( ["__main__"] )

def trace_module(modulename):
	if not isinstance(modulename, str):
		raise ValueError('module name must be a string')
	__modules_to_trace.add(modulename)

def untrace_module(modulename):
	if not isinstance(modulename, str):
		raise ValueError('module name must be a string')
	__modules_to_trace.remove(modulename)

def trace_function_calls(frame, event, arg):
	'''
	Callback function used with sys.settrace() to trace function calls within
	a standalone script.

	:param frame: Call Frame
	:type frame: Python call frame object. See https://docs.python.org/3/reference/datamodel.html#types
	:param event: Event type
	:type event:  str - See https://docs.python.org/3.4/library/sys.html#sys.settrace for valid events
	:param arg: Additional arguments depending on event
	:type arg: Varies

	'''
	# Skip function calls to modules outside of __main__
#	print(frame.f_globals['__name__'])
#	if frame.f_globals['__name__'] != '__main__':
	if not frame.f_globals['__name__'] in __modules_to_trace:
		return trace_function_calls
	if event == 'call':
		code = frame.f_code
		print('<'+event+'>', code.co_filename, code.co_firstlineno, end=': ')
		try:
			obj = frame.f_locals['self']
			print("{}.{}(".format(obj.__class__.__name__, code.co_name), end='')
		except:
			print("{}(".format(code.co_name), end='')
		for i in range(frame.f_code.co_argcount):
			name = code.co_varnames[i]
			if name != 'self':
				arg = frame.f_locals[name]
				if isinstance(arg, str) :
					# truncate at first newline
					idx = arg.find('\n')
					if idx > 64:
						arg = arg[:64]+'...'
					elif idx > 0:
						arg = arg[:idx]+'...'
					arg = '"'+arg+'"'
				elif isinstance(arg, object):
					arg = arg.__class__.__name__
				print("{}={},".format(name,arg), end=' ')
		print(')')
	return trace_function_calls

