#!/usr/bin/env python3
"""
Decorator function to implement a "dry run" mode for class methods and functions

This decorator is intended to be used during development and testing, where
an operation that could modify a filesystem, repository, or other persistently-
stored object is not desired.

Example usage:

@dryrunnable()
def func(arg):
push_remote(remote_name, remote_branch)

"""
import sys
from functools import wraps # Needed to allow autodoc to get docstrings of decorated functions
import inspect

from lib.colortext import PaletteColor, ANSIColor

class DryRunBool:
	value = False
	verbose = True

dry_run = None

def set(value:bool):
	DryRunBool.value = value

def get():
	return DryRunBool.value

def verbose(value:bool):
	DryRunBool.verbose = value

class dryrunnable(object):
	"""
	Decorator Function implement the "dry run" of class methods and functions
	"""
	def __init(self, *args, **kwargs):
		self.args = args
		self.kwargs = kwargs

	def __call__(self, func):
		@wraps(func)
		def dry_run_wrapper(*args,**kwargs):
			modulename = inspect.getmodule(func).__name__
			if DryRunBool.value:
				if DryRunBool.verbose:
					print(PaletteColor(9, "DRY_RUN:", modulename+'.'+func.__name__, str(args), str(kwargs and kwargs or '')))
				return None
			else:
				if DryRunBool.verbose:
					print(modulename+'.'+func.__name__, str(args), kwargs and kwargs or '' )
				return func(*args,**kwargs)
		return dry_run_wrapper

class traceable(object):
	"""
	Decorator Function implement the "dry run" of class methods and functions
	"""
	def __init(self, *args, **kwargs):
		self.args = args
		self.kwargs = kwargs

	def __call__(self, func):
		@wraps(func)
		def trace_wrapper(*args,**kwargs):
			modulename = inspect.getmodule(func).__name__
			print(ANSIColor("green", modulename+'.'+func.__name__, str(args), kwargs and kwargs or '' ))
			return func(*args,**kwargs)
		return trace_wrapper

@dryrunnable()
def dryrunnable_command(command, *args, timeout=None):
	if isinstance(args[0], list):
		args = tuple(args[0])
	if timeout is not None:
		import signal
		cmd = command(args, _bg=True , _tty_out=False, _out=sys.stdout, _err=sys.stderr, _timeout=timeout, _timeout_signal=signal.SIGALRM)
	else:
		cmd = command(args, _bg=True , _tty_out=False, _out=sys.stdout, _err=sys.stderr)
	print(str(cmd.cmd))
	cmd.wait()
	print("%s returns %d" % (cmd.cmd[0], cmd.exit_code))
	if cmd.exit_code != 0:
		raise Exception("%s returns %d" % (cmd.cmd[0], cmd.exit_code))

def dryrunnable_method(method, *args, **kwargs):
	a = inspect.getfullargspec(method)
	try:
		modulename = inspect.getmodule(method).__name__
	except AttributeError as e:	# if method not in a module
		modulename = method.__class__.__name__
	if DryRunBool.value:
		if DryRunBool.verbose:
			print(PaletteColor(9, "DRY_RUN:", modulename+'.'+method.__name__, str(args), str(kwargs and kwargs or '')))
		ret = True
	else:
		if DryRunBool.verbose:
			print(modulename+'.'+method.__name__, str(args), kwargs and kwargs or '')
		if not a.args:
			ret = method()
		else:
			ret = method(*args, **kwargs)
	return ret

def traceable_method(method, *args, **kwargs):
	a = inspect.getfullargspec(method)
	try:
		modulename = inspect.getmodule(method).__name__
	except AttributeError as e:	# if method not in a module
		modulename = method.__class__.__name__
	print(ANSIColor("green", modulename+'.'+method.__name__, str(args), kwargs and kwargs or '' ))
	return method(*args,**kwargs)

if __name__ == '__main__':
	@dryrunnable()
	def test(name):
		print("hello "+name)

	@dryrunnable()
	def test2(name,last):
		print("hello2 {} {}".format(name,last))

	def test3(*args):
		print("test3" , args)

	test("Patrick")
	test2("Pat", "Noziska")
	dry_run = True
	test("Patrick")
	test2("Pat", "Noziska")
	dry_run = False
	test("Patrick")
	test2("Pat", "Noziska")
	dryrunnable_method(test3, 'a', 'b')
