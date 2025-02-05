#!/usr/bin/env python3

'''
Use some Django inntrospection to dump the values of 
any DevOps Fameworks table
'''

import os
import sys
import sh
import re
import importlib
import traceback
import json
from django.db.models.functions import Length, Cast
from django.db.models import Max
from django.apps import apps
from lib.colortext import ANSIColor


if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from framework.models import *

def __dump_tables(argv):
	allmodels = apps.all_models['framework']
	for m in allmodels:
		klass = allmodels[m]
		print('##############################', klass.__name__, '##############################')
		print(klass.objects.all())
#		print(len(klass.objects.all()))

def __show_table(argv):
	name = argv[0]
	mod = importlib.import_module('framework.models')
	klass = getattr(mod, name)
	fieldlist = [ f.__dict__['column'] for f in klass._meta.fields ]
	width = {}

	# Get column widths for formatting
	for f in fieldlist:
		width[f] = max(len(f), klass.objects.aggregate(val=Max(Length(Cast(f, output_field=CharField()))))["val"])

	print("\n\nPostgreSQL DB Table %s (Django model frameworks.models.%s)\n\n" % (klass._meta.db_table, name))

	for f in fieldlist:
		print("%-*.*s " % ( width[f],  width[f], f), end='')
	print('')
	for f in fieldlist:
		print("%-*.*s " % ( width[f],  width[f], '='*width[f] ), end='')
	print('')
	rows = klass.objects.all().order_by('id')
	for row in rows:
		for f in fieldlist:
			attr = getattr(row, f)
			print("%-*.*s " % ( width[f],  width[f], str(attr) ), end='')
		print('')

def __validate_Remote(argv):
	for r in Remote.objects.all().order_by('remote_name'):
		if not r.staging_template or not r.push_template:
			continue
		print(r.remote_name, ':')
		print('	', 'FROM:', ANSIColor("yellow", r.local_repo.project), ANSIColor("green", r.staging_template.template.template))
		print('	', 'TO:  ', ANSIColor("yellow", r.remote_repo.project), ANSIColor("green", r.push_template.template.template))

def __validate_Templates(argv):
	print("TAG Templates:")
	for r in TagTemplate.objects.all().order_by('template__template'):
		print('KERNEL:', ANSIColor("yellow", r.kernel.name), "TEMPLATE:" , ANSIColor("green", r.template.template))
	print("BRANCH Templates:")
	for r in BranchTemplate.objects.all().order_by('template__template'):
		print('NAME:', r.name, 'KERNEL:', ANSIColor("yellow", r.kernel.name), "TEMPLATE:" , ANSIColor("green", r.template.template))

if __name__ == '__main__':
	print(sys.argv)
	try:
		if len(sys.argv) > 1:
			ret = globals()[sys.argv[1]](sys.argv[2:])
		else:
			ret = globals()[sys.argv[1]]()
		if ret is not None:
			print(ret)
	except Exception as e:
		print(traceback.format_exc())
		sys.exit(1)
	sys.exit(0)
