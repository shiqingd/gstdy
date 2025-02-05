#!/usr/bin/env -S PYTHONPATH=${WORKSPACE}/intel-innersource/os.linux.kernel.devops.ikit-dev-ops python3 -u
import os
import re
import sys
import json
import sys
import os
import kconfiglib
import shutil
import re,tempfile
from lib.utils import sed_inplace
import argparse

class ConfigDependencyFinder(object):

	arch_map = {
		"arm64" : [ "ARM", "ARM64" ],
		"x86" : [ "X86", "X86_64", "X86_32" ]
	}

	Kconfigs_to_mod  = [ 'init/Kconfig', 'kernel/module/Kconfig' ]

	def __init__(self, target_arch='x86', cfg_path='build/.config'):

		if target_arch.startswith('x86_'):
			target_arch = 'x86'
		self.target_arch = target_arch
		self.cfg_path = cfg_path
			
		os.environ["CC"] = 'gcc'
		os.environ["LD"] = 'ld'
		os.environ["SRCARCH"] = target_arch
		os.environ["srctree"] = '.'

		for f in self.Kconfigs_to_mod:
			if os.path.exists(f):
				print(f"Saving copy of {f}")
				shutil.copy(f, f+".bak")
				sed_inplace('d', r'^\tmodules$', filename=f)
		self.kconf = kconfiglib.Kconfig('Kconfig', suppress_traceback=True, warn_to_stderr=False)
		self.kconf._load_config(self.cfg_path, replace=True)

	def __del__(self):
		for f in self.Kconfigs_to_mod:
			if os.path.exists(f+".bak"):
				print(f"Restoring {f}")
				shutil.move(f+".bak", f)

	def get_kconfig_deps(self, sym, deps, operator, i):
		if type(sym) is tuple:
			if sym[0] == kconfiglib.OR:
				'''
				for item in sym[1:]:
					deps |= self.get_kconfig_deps(item, deps, 'OR', i)
				'''
				pass
			elif sym[0] == kconfiglib.AND:
				for item in sym[1:]:
					deps |= self.get_kconfig_deps(item, deps, 'AND',  i)
			elif sym[0] == kconfiglib.NOT:
				'''
				for item in sym[1:]:
					deps |= self.get_kconfig_deps(item, deps, 'NOT',  i)
				'''
				pass
			elif sym[0] == kconfiglib.EQUAL:
				for item in sym[1:]:
					deps |= self.get_kconfig_deps(item, deps, 'EQUAL',  i)
			elif sym[0] == kconfiglib.UNEQUAL:
				'''
				for item in sym[1:]:
					deps |= self.get_kconfig_deps(item, deps, 'UNEQUAL',  i)
				'''
			else:
				print("Unexpected operator", sym[0])
		else:
#			print(' '*i*4, operator,  '[', repr(sym), ']')
			if hasattr(sym,"direct_dep"):
				if not sym.name in [ 'y', 'n', 'm', None ]:
					if type(sym.direct_dep) is tuple:
						deps |= self.get_kconfig_deps(sym.direct_dep, deps, operator, i+1)
					if hasattr(sym, "selects"):
						for select in sym.selects:
#							print(select[0].name)
							deps.add(select[0].name)
					deps.add(sym.name)
			else:
#				print('YYYYYYYYY', sym.name )
				deps.add(sym.name)
#		print(i, deps)
		return(deps)

	def Kconfig_dependencies(self, cfg):
		deps = set()
		try:
			dependency = self.get_kconfig_deps(self.kconf.syms[cfg], deps, '', 0)
			for arch in self.arch_map.keys():
				if arch == self.target_arch:
					continue
				bad_targets = (lambda x,y : [ item for item in x if item in y ])(self.arch_map[arch], dependency)
				if bad_targets:
					raise ValueError(cfg , "depends on incompatible target(s): "+str(bad_targets)+", will be dropped")
		except KeyError as e:
			print(cfg, ": no upstream dependency found", file=sys.stderr)

		return deps

	def __expand_values(self, value):
		# FIXME : NO-OP this functon for now
		# FIXME : Create a macro expansion here
		return value


	def Makefile_dependency(self, source_file):

		dirname = os.path.dirname(source_file)
		object_name = re.sub('\.c$', '.o', os.path.basename(source_file))
		module_objs = {}
		config_objs = {}
		dep_objs = {}
		env_vars = {}
		
		makefile = os.path.join(dirname,"Makefile")
		if not os.path.exists(makefile):
			makefile = os.path.join(dirname,"Kbuild")
		while not os.path.exists(makefile):
	#		print("WARNING: can't find Makefile or Kbuild for ", dirname, "- moving up one dir")
			leafdirname = os.path.basename(dirname)
			object_name = os.path.join(leafdirname, object_name)
			dirname = os.path.dirname(dirname)
			makefile = os.path.join(dirname,"Makefile")
			if not os.path.exists(makefile):
				makefile = os.path.join(dirname,"Kbuild")

	#	print("NEW MAKEFILE", makefile)
	#	print("NEW OBJECT", object_name)

		try:
			lines = open(makefile).readlines()
		except Exception as e:
			print('===========================', e)
			return(None)

		# Create a flexible iterator so that
		# Multiple Lines can be joined
		i = iter(lines)
		while True:
			try:
				ll = next(i).strip()
				if not ll:
					continue
				# Collect continuation lines
				while ll[-1] == '\\':
						ll += next(i).strip()
				ll = re.sub('\\\\','',ll)
				match = re.search('[^\-]+-\$[\(\{]CONFIG_(\S+)[\)\}]\s*[+:]=\s+(.+)$', ll)
	#			match = re.search('[^\-]+-\$[\(\{]CONFIG_(\S+)[\)\}]\s+[+:]=\s+(.+)$', ll)
				if match:
					key = match.group(1)
	#				print("MATCH:", key)
					if key in config_objs:
						config_objs[key] += match.group(2).split()
					else:
						config_objs.update({ key : self.__expand_values(match.group(2).split()) })
					continue
				match = re.search('(\S+-y)\s+[+:]=\s+(.+)$', ll)
				if match:
					key = re.sub('-y', '.o', match.group(1))
					if 'ccflags' in key:
						continue
					if key in dep_objs:
						dep_objs[key] += match.group(2).split()
					else:
						dep_objs.update( { key : self.__expand_values(match.group(2).split()) })
					continue
				match = re.search(r'(\S+)\s+[:+]=\s+(.+)$', ll)
				if match:
					key = match.group(1)
					if 'ccflags' in key:
						continue
					if '-objs' in key:
						key = re.sub('-objs', '.o', key)
						if key in module_objs:
							module_objs[key] += match.group(2).split()
						else:
							module_objs.update( { key : self.__expand_values(match.group(2).split()) })
					else:
						env_vars[key] = match.group(2)
					continue
			except StopIteration:
				break
	#	print("MODULE_OBJS:", json.dumps(module_objs, indent=4))
	#	print("DEP_OBJS:", json.dumps(dep_objs, indent=4))
	#	print("CONFIG_OBJS:",json.dumps(config_objs, indent=4))
	#	print("ENV_VARS:", json.dumps(env_vars, indent=4))
		modobj = object_name
	#	print("INITIAL:",modobj)
		for k in module_objs.keys():
			if object_name in module_objs[k]:
				modobj = k
				break
	#	print("CURRENT:",modobj)
		for k in dep_objs.keys():
			if object_name in dep_objs[k]:
				modobj = k
				break
	#	print("CURRENT:",modobj)
		config_var = None
		for k in config_objs.keys():
			if modobj in config_objs[k]:
				config_var = k
				break
		return(config_var)

if __name__ == '__main__':

	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--arch', '-a', required=True, type=str, help="Target kernel architecture [ 'x86', 'arm64' ]")
	parser.add_argument('--input-file', '-i', help="File containing list of files changed")
	parser.add_argument('files_changed', nargs='*', help="List of files changed")
	args = parser.parse_args()

	if args.input_file and args.files_changed:
		parser.error("Both file paths and input file cannot be specified at the same time.")

	if args.files_changed:
		fileset = args.files_changed
	elif args.input_file:
		fileset = [ f.strip() for f in open(args.input_file, "r").readlines() ]

	cfg_deps = set()
	finder = ConfigDependencyFinder(target_arch=args.arch)
	for filename in fileset:
		cfg = finder.Makefile_dependency(filename)
		if cfg:
			try:
				kdeps = finder.Kconfig_dependencies(cfg)
				print(f"{filename} needs {cfg} and {kdeps}", file=sys.stderr)
				cfg_deps.add(cfg)
				cfg_deps |= kdeps
			except ValueError as e:
				# Don't add the config it an exception is raised
				print(e, file=sys.stderr)
	print(" ".join(cfg for cfg in sorted(cfg_deps)), file=sys.stdout)
	del finder

	with open("/tmp/mergeconfigs", "w+") as mfile:
		for cfg in sorted(cfg_deps):
			print(f"CONFIG_{cfg}=y", file=mfile)
		print(f"CONFIG_RETPOLINE=n", file=mfile)

	sys.exit(0)
