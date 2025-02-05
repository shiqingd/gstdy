#!/usr/bin/env python3

import os
import sys
import argparse
import traceback
import json
import sh
import re
from copy import copy,deepcopy
import types
import inspect
from glob import glob

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from django.db.models import F, Q

from framework.models import *

from lib.pushd import pushd
from lib.colortext import ANSIColor, RGBColor

_git = sh.Command("/usr/bin/git")

import labels

######
# ADD 
######
def __add_domain_label(d : Domain, repo : Repository):
	data = {
		"id" : repo.ext_project_id,
		"name" : "D::"+d.label_name ,
		"color" : "#FF0000",
		"text_color" : "#FFFFFF",
		"description" : d.name
	}
	labels._create_label(data)

def __add_subdomain_label(sd : Subdomain, repo : Repository):
	data = {
		"id" : repo.ext_project_id,
		"name" : "S::"+sd.name ,
		"color" : "#880000",
		"text_color" : "#FFFFFF",
		"description" : sd.description
	}
	labels._create_label(data)

########
# DELETE
########

def __delete_domain_label(d: Domain , repo : Repository):
	data = {
		"id" : repo.ext_project_id ,
		"label_id" : 'D::'+d.label_name
	}
	label = labels._get_label(data)
	data = {
		"id" : repo.ext_project_id,
		"label_id" : label["id"]
	}
	labels._delete_label(data)
	
def __delete_subdomain_label(sd: Subdomain , repo : Repository):
	data = {
		"id" : repo.ext_project_id ,
		"label_id" : 'S::'+sd.name
	}
	label = labels._get_label(data)
	data = {
		"id" : repo.ext_project_id,
		"label_id" : label["id"]
	}
	labels._delete_label(data)
	
##########
# POPULATE
##########
def _populate_group_labels(repo : Repository):
	for platform in Platform.objects.all():
		data = {
			"id" : repo.ext_group_id ,
			"name" : "P::"+platform.architecture+"::"+platform.name,
			"color" : "#0000FF",
			"description" : platform.description
		}
		labels._create_group_label(data)

def _populate_project_labels(kernel : Kernel, repo : Repository):
	for d in Domain.objects.filter(kernels = kernel):
		if d.label_name:
			data = {
				"id" : repo.ext_project_id,
				"name" : "D::"+d.label_name ,
				"color" : "#FF0000",
				"text_color" : "#FFFFFF",
				"description" : d.name
			}
			labels._create_label(data)
			for sd in d.subdomains.all():
				data = {
					"id" : repo.ext_project_id,
					"name" : "S::"+sd.name ,
					"color" : "#880000",
					"text_color" : "#FFFFFF",
					"description" : sd.description
				}
				labels._create_label(data)

#######
# PURGE
#######

def _delete_group_labels(repo : Repository):
	label_list = labels._get_group_labels({ "id" : repo.ext_group_id })
	for label in label_list:
		print(label)
		data = { "id" : repo.ext_group_id,  "label_id" : label["id"], "name" : label["name"] }
		labels._delete_group_label(data)

def _delete_project_labels(repo : Repository):
	label_list = labels._get_labels({ "id" : repo.ext_project_id })
	for label in label_list:
		print(label)
		data = {
			"id" : repo.ext_project_id,
			"label_id" : label["id"]
		}
		labels._delete_label(data)
	
######
# LIST
######

def _list_project_labels(repo : Repository):
	label_list = labels._get_labels({ "id" : repo.ext_project_id , "is_project_label" : True })
	for label in label_list:
		print(label)
	
def _list_group_labels(repo : Repository):
	label_list = labels._get_labels({ "id" : repo.ext_group_id , "is_project_label" : False })
	for label in label_list:
		print(label)
	


class Formatter(argparse.HelpFormatter):
	# use defined argument order to display usage
	def _format_usage(self, usage, actions, groups, prefix):
		if prefix is None:
			prefix = 'usage: '

		# if usage is specified, use that
		if usage is not None:
			usage = usage % dict(prog=self._prog)

		# if no optionals or positionals are available, usage is just prog
		elif usage is None and not actions:
			usage = '%(prog)s' % dict(prog=self._prog)
		elif usage is None:
			prog = '%(prog)s' % dict(prog=self._prog)
			# build full usage string
			action_usage = self._format_actions_usage(actions, groups) # NEW
			usage = ' '.join([s for s in [prog, action_usage] if s])
			# omit the long line wrapping code
		# prefix with 'usage:'
		return '%s%s\n\n' % (prefix, usage)

def __list_labels(args):
#	print('Platforms:')
#	for p in Platform.objects.all(): print("P::{}::{}".format(p.architecture, p.name))
	print('')
	k = Kernel.objects.get(name = args.kernel) 
	print('Domains Valid for Kernel %s (%s)' % (k.name, k.description))
	rows = Domain.objects.filter(kernels__in = [ k ])
	if rows:
		for d in rows:
			print("D::{}  ({})".format(d.label_name, d.name))
			print('Subdomains:')
			rows = Subdomain.objects.filter(domain__in = [ d ])
			if rows:
				for s in rows:
					 print("	S::{}".format(s.name))
			else:
				print("	None")
			print("")
	else:
		print("None")
#	[ a[0] for a in list(Platform.objects.all().values_list('architecture').distinct()) ]

def __new_domain(args):
	d = Domain.objects.filter(label_name = args.label_name).first()
	if not d:
		d = Domain(label_name = args.label_name, name = args.description)
	k = Kernel.objects.get(name = args.kernel)
	d.save()
	d.kernels.add(k)
	d.save()
	kernel = Kernel.objects.get(name = args.kernel)
	rsets = KernelRepoSet.objects.filter(kernel = kernel, repo__repotype__repotype = 'src')
	for rs in rsets:
		__add_domain_label(d, rs.repo)

def __new_subdomain(args):
	domain = Domain.objects.get(label_name = args.domain)
	sd = Subdomain.objects.filter(name = args.name).first()
	if not sd:
		sd = Subdomain(name = args.name, description = args.description)
	sd.save()
	domain.subdomains.add(sd)
	domain.save()
	kernel = Kernel.objects.get(name = args.kernel)
	rsets = KernelRepoSet.objects.filter(kernel = kernel, repo__repotype__repotype = 'src')
	for rs in rsets:
		__add_subdomain_label(sd, rs.repo)

def __reload_labels(args):
	kernel = Kernel.objects.get(name = args.kernel)
	rsets = KernelRepoSet.objects.filter(kernel = kernel, repo__repotype__repotype = 'src')
	for rs in rsets:
		repo = rs.repo
		__delete_project_labels(repo)
		__delete_group_labels(repo)
		__populate_group_labels(repo)
		__populate_project_labels(repo)

COMMANDS = { 
	"get-labels" : __list_labels,
	"add-domain" : __new_domain,
	"add-subdomain" : __new_subdomain,
	"reload-labels" : __reload_labels
}

def _list_commands():
	return ", ".join( c for c in COMMANDS.keys() )

def _validate_command(value):

	if value in COMMANDS.keys():
		return value
	else:
		raise ArgumentTypeError("Invalid Command %s" % ( value ) )
	
	gvars = copy(globals())
	validfuncs = []
	for k,v in gvars.items():
		if isinstance(v, types.FunctionType) and inspect.getmodule(v).__name__ == '__main__' and k.startswith('__'):
			validfuncs.append(k)
	print(value)
	print(validfuncs)
	if value in validfuncs:
		return value
	else:
		raise ArgumentTypeError("Invalid Command %s" % ( value ) )

def _validate_local_funcs(value):
	
	gvars = copy(globals())
	validfuncs = []
	for k,v in gvars.items():
		if isinstance(v, types.FunctionType) and inspect.getmodule(v).__name__ == '__main__' and k.startswith('__'):
			validfuncs.append(k)
	print(value)
	print(validfuncs)
	if value in validfuncs:
		return value
	else:
		raise ArgumentTypeError("Invalid Command %s" % ( value ) )

def __validate_new_domain_name(value):
	if value == 'help':
		raise ArgumentTypeError("Domain label '%s' is invalid" % ( value ) )
		return None
	if len(value) > 8:
		raise ArgumentTypeError("Domain label '%s' is too long (8 characters max)" % ( value ) )
	return value

if __name__ == '__main__':
	command_parser = argparse.ArgumentParser(prog=sys.argv[0], formatter_class = Formatter)

	subparsers = command_parser.add_subparsers(dest='command',help="Choose a command")
	print(type(subparsers))

	list_parser = subparsers.add_parser('get-quilt-patches', help='"get_quilt-patches" help', formatter_class = Formatter)
	list_parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
	print(type(list_parser))

	list_parser = subparsers.add_parser('get-labels', help='"get-labels" help', formatter_class = Formatter)
	list_parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
	print(type(list_parser))

	add_dom_parser = subparsers.add_parser('add-domain', help='"add-domain" help', formatter_class = Formatter)
	add_dom_parser.add_argument('label_name', type=__validate_new_domain_name, help="new domain label name (max 8 characters)")
	add_dom_parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
	add_dom_parser.add_argument('--description', '-d', required=True, type=str, help="Short description of domain")
	print(type(add_dom_parser))

	add_subdom_parser = subparsers.add_parser('add-subdomain', help='"add-subdomain" help', formatter_class = Formatter)
	add_subdom_parser.add_argument('name', type=__validate_new_domain_name, help="new subdomain label name (max 8 characters)")
	add_subdom_parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
	add_subdom_parser.add_argument('--domain', '-D', required=True, type=Domain.validate, help=Domain.list())
	add_subdom_parser.add_argument('--description', '-d', required=True, type=str, help="Short description of subdomain")
#	add_subdom_parser.set_defaults(action=lambda: 'add-subdomain')
	print(type(add_subdom_parser))

	"""
	parser.add_argument('label_name', nargs=1, type=str, help="Name of label to operate on")
	parser.add_argument('--platform', '-P', required=True, type=CPU.validate, help="Valid Values: "+CPU.list())
	parser.add_argument('--domain', '-D', required =True, type=Domain.validate, help="Valid Values: "+Domain.list())
	parser.add_argument('--subdomain', '-S', required =True, type=Subdomain.validate, help="Valid Values: "+Subdomain.list())
	parser.add_argument('--description', '-c', required =True, type=str, help="Short Description of the Label")
#	parser.add_argument('--dry_run', action='store_true', help="Do not actually do anything; just print what would happen")
	"""

	args = command_parser.parse_args()
	print(args)
	try:
		COMMANDS[args.command](args)
	except Exception as e:
		print(traceback.format_exc())
		sys.exit(1)

"""
	assert(os.path.exists(os.environ["WORKSPACE"]))
	try:
		if len(sys.argv) > 2:
			ret = globals()[sys.argv[1]](sys.argv[2:])
		else:
			ret = globals()[sys.argv[1]]()
		if ret is not None:
			print(ret)
	except Exception as e:
		print(traceback.format_exc())
		sys.exit(1)
	sys.exit(0)
"""
