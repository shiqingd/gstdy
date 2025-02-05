#!/usr/bin/env python3
#

import sys
import os
import sh
import subprocess
import shutil
import traceback
import re
import argparse
import time, datetime
import logging
from autologging import TRACE
import suds.wsse
import suds.client
import json
import datetime
import pytz
import requests
from filelock import SoftFileLock
import pkt_cov_config as pkt_cov_config
from hashlib import md5

from suds.transport.https import HttpAuthenticated
from urllib.request import HTTPSHandler
import ssl

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

try:
	assert('DATABASE_HOST' in os.environ)
except:
	print("Environment Variable DATABASE_HOST not set", file=sys.stderr)
	sys.exit(1)

from framework.models import CoverityProject, Repository
import lib.dry_run
from lib.pushd import pushd
from lib.colortext import ANSIColor, RGBColor
from django.db.models import F, Q

lib.dry_run.verbose = True

class HttpsTransport(HttpAuthenticated):

	def u2handlers(self):
		# use handlers from superclass
		handlers = HttpAuthenticated.u2handlers(self)

		# create custom ssl context, e.g.:
		# ctx = ssl.create_default_context(cafile="/path/to/ca-bundle.pem")
		ssl._create_default_https_context = ssl._create_unverified_context
		ctx = ssl._create_unverified_context()
		# configure context as needed...
		ctx.check_hostname = False

		# add a https handler using the custom context
		handlers.append(HTTPSHandler(context=ctx))
		return handlers


def get_client(url):
	url = "".join(url.split())
	client = suds.client.Client(url, transport=HttpsTransport(), timeout=3600)
	return client


# Set up SOAP-Based Coverity Web Services API
class CWS:
	url=pkt_cov_config.COV_URL
	MyConfSrv=url+"/ws/v9/configurationservice?wsdl"
	MyDefSrv=url+"/ws/v9/defectservice?wsdl"

	# Setup authorization
	Security = suds.wsse.Security()
	Security.tokens.append(suds.wsse.UsernameToken(pkt_cov_config.USERNAME, pkt_cov_config.PASSWORD))

	# Configuration Service Client - Projects, Streams, Component Maps, Snapshots and Defect Attributes
	print("Connect to configuration service: {}".format(MyConfSrv))
	ConfServiceClient = suds.client.Client(MyConfSrv, timeout=3600)
	ConfServiceClient.set_options(wsse=Security)

	# Defect Service Client - Defects and Defect Instances
	print("Connect to defect service: {}".format(MyDefSrv))
	DefServiceClient = suds.client.Client(MyDefSrv, timeout=3600)
	DefServiceClient.set_options(wsse=Security)


class pushd():
	def __init__(self, _dir):
		self.prevdir = os.getcwd()
		self._dir = _dir

	def __enter__(self):
		os.chdir(self._dir)
#		print("PUSHD:" , os.getcwd())

	def __exit__(self, *args):
		os.chdir(self.prevdir)
#		print("POPD:" , os.getcwd())


__dry_run = False

__log = logging.getLogger(sys.argv[0] != '' and sys.argv[0] or '<console>')
__log.setLevel(TRACE)

formatter = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s', '%m/%d/%Y %H:%M:%S')
formatter_nl = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s\n', '%m/%d/%Y %H:%M:%S')

if not "LOGFILE" in os.environ:
	# create file handler that logs debug and higher level messages
	ch = logging.StreamHandler(stream=sys.stdout)
	ch.terminator = ''
	ch.setLevel(TRACE)
	ch.setFormatter(formatter_nl)
	__log.addHandler(ch)
else:
	# create formatter and add it to the handlers
	# add the handlers to logger
	fh = logging.FileHandler(os.environ["LOGFILE"])
	fh.setLevel(TRACE)
	fh.setFormatter(formatter)
	__log.addHandler(fh)
__log.propagate = False

__nproc = sh.Command('/usr/bin/nproc')().strip()

__git = sh.Command('/usr/bin/git')


def try_shell_command(command, args, timeout=None):

	kwargs = { "_bg" : True, "_out" : __log.info, "_err": __log.error }
	if timeout:
		import signal
		kwargs["_timeout"] = timeout
		kwargs["_timeout_signal"] = signal.SIGALRM
	if sh.__version__ >= '2.0':
		kwargs["_return_cmd"] = True
	cmd = command(args, **kwargs)
	__log.info(cmd.cmd)
	cmd.wait()
	__log.info("%s returns %d" , cmd.cmd[0], cmd.exit_code)
	if cmd.exit_code != 0:
		raise Exception("%s returns %d" % (cmd.cmd[0], cmd.exit_code))


defconfig_priority = [
	'x86_64_defconfig',
	'bxt/yocto/x86_64_defconfig'
]


def __reset_to_master_and_pull():
	try_shell_command(__git, [ "reset", "--hard", "origin/master" ] )
	try_shell_command(__git, [ "checkout", "master" ] )
	try_shell_command(__git, [ "fetch" , "--all", "--tags", "--force" ] )
	try_shell_command(__git, [ "pull" ] )


g_objProject = None

def __get_config(project, snapshot):

	global g_objProject

#	staging_number = re.sub('.+([0-9]{6}[-T][0-9]{4,6}Z{0,1})$', '\\1', snapshot)
	config_dir = os.path.join(pkt_cov_config.REPO_BASE, g_objProject.config_repo.project)
	with pushd(config_dir):
		__reset_to_master_and_pull()
		branches = __git('--no-pager', 'branch', '-a', '--no-color').strip().split("\n")
		for line in branches:
#			match = re.search(staging_number+'$', line)
			match = re.search(snapshot+'$', line)
			if match:
				ref = re.sub('  remotes/', '', line).strip()
				__git.checkout(ref)
				config_files = __git('--no-pager', 'ls-files').strip().split('\n')
				for config in defconfig_priority:
					if config in config_files:
						print('Using Branch {} Kconfig {} from {}'.format(ref, config, config_dir))
						return ref, config
		tags = __git('--no-pager', 'tag', '--list', '--no-color').strip().split("\n")
		for tag in tags:
			if snapshot == tag:
				__git.checkout(tag)
				config_files = __git('--no-pager', 'ls-files').strip().split('\n')
				for c in config_files:
					print(c)
				for config in defconfig_priority:
					if config in config_files:
						print('Using Tag {} Kconfig {} from {}'.format(tag, config, config_dir))
						return tag, config
	raise ValueError('No Config Reference (branch or tag) found (or no config found at '+str(defconfig_priority)+'for '+snapshot)


def __get_version():
	version = CWS.ConfServiceClient.service.getVersion()
	__log.info (version)
	return version


def __get_projects():
	projectsList = CWS.ConfServiceClient.service.getProjects()
	for prj in projectsList:
		print (prj)


def __get_streams():
	streamsList = CWS.ConfServiceClient.service.getStreams()
	for stream in streamsList:
		print (stream)


def  __trim_snapshots_in_stream(argv, count=4):

	ref = argv[0]
	arch = argv[1]

	# Lookup project, stream and baseline based on ref name and arch
	project, stream, baseline = __get_stream_for( [ ref, arch ])

	snapshots = __get_snapshots_for_stream([ stream ])
	check_is_delete_snapshots = []
	for s in snapshots.keys():
		if snapshots[s] != baseline:
			check_is_delete_snapshots.append([s, snapshots[s]])
	# Reason for restriction: Stream only retains 5 snapshots and deletes the oldest one.
	sorted_snapshots = sorted(check_is_delete_snapshots, key=lambda x: (x[0], x[1]))
	while len(sorted_snapshots) >= count:
		__delete_snapshot(sorted_snapshots)
		del sorted_snapshots[0]


def __delete_snapshot(argv):
	snapshotId = CWS.ConfServiceClient.factory.create("snapshotIdDataObj")
	snapshotId.id=int(argv[0])
	try:
		CWS.ConfServiceClient.service.deleteSnapshot(snapshotId=snapshotId)
		while True:
			deleteSnapshotJobInfo = CWS.ConfServiceClient.service.getDeleteSnapshotJobInfo(snapshotId=snapshotId)
			print (deleteSnapshotJobInfo)
			try:
				if deleteSnapshotJobInfo.status == deleteSnapshotJobStatus.SUCCEEDED:
					break
			except Exception as e:
				break
			time.sleep(1)
	except suds.WebFault as e:
		print(str(e))
		raise e


def __get_snapshots_for_stream(argv):
	objStream = CWS.ConfServiceClient.factory.create("streamIdDataObj")
	objStream.name=argv[0]
	objSnapshotIds = CWS.ConfServiceClient.service.getSnapshotsForStream(streamId=objStream)
	snapshots = {}
	print(objSnapshotIds)
	for sid in objSnapshotIds:
		sInfo = CWS.ConfServiceClient.service.getSnapshotInformation(snapshotIds = sid)
		snapshots[sid.id] = sInfo[0].description
	return snapshots


def __get_component_maps(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("componentMapFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	objMaps = CWS.ConfServiceClient.service.getComponentMaps(filterSpec=filterSpec)
	for cmap in objMaps:
		print (cmap)

#import base64
#import zlib
#
#def __get_file_contents(stream, md5, path):
#	objStream = CWS.ConfServiceClient.factory.create("streamIdDataObj")
#	objStream.name=stream
#	objFile = CWS.DefServiceClient.factory.create("fileIdDataObj")
#	objFile.contentsMD5 = md5
#	objFile.filePathname = path
#	objContent = CWS.DefServiceClient.service.getFileContents(streamId=objStream, fileId=objFile)
#	filebytes = zlib.decompress(base64.b64decode(objContent.contents))
#	print('--------------------------------')
#	print(objContent.fileId)
#	print(filebytes.decode())

def __list_defects_for_stream(argv):
	startIndex = 0
	defect_ids = []
	totalNumberOfRecords = None
	streamIds = CWS.DefServiceClient.factory.create("streamIdDataObj")
	streamIds.name = argv[0]
	while True:
		# create a page specification object
		__log.info("Get Defects Starting from %d\n" , startIndex)
		pageSpec = CWS.DefServiceClient.factory.create("pageSpecDataObj")
		pageSpec.pageSize = 100
		pageSpec.sortAscending = True
		pageSpec.startIndex = startIndex
		filterSpec = CWS.DefServiceClient.factory.create("snapshotScopeDefectFilterSpecDataObj")
		filterSpec.issueComparison = "ABSENT"
		filterSpec.streamIncludeNameList = CWS.DefServiceClient.factory.create("streamIdDataObj")
		filterSpec.streamIncludeNameList.name = argv[0]
		filterSpec.statusNameList = "New"
		defectsPages = CWS.DefServiceClient.service.getMergedDefectsForStreams(streamIds=streamIds, pageSpec=pageSpec, filterSpec=filterSpec)
		if len(defectsPages) == 1:
			break
		# API Docs are WRONG: This was deduced by trial and error:
		# tuple ( "objectName" , value )
		# tuple ( "mergedDefectIds" , [ list ] )
		# tuple ( "mergedDefects" , [ list ] )
		# tuple ( "toalNumberOfRecords" , int )
		for page in defectsPages:
			if page[0] == 'mergedDefectIds':
				defect_id_list = page[1]
			elif page[0] == 'mergedDefects':
				defect_list = page[1]
			else:
				if not totalNumberOfRecords:
					totalNumberOfRecords = page[1]
		for defect in defect_id_list:
			defect_ids.append(defect.cid)
		startIndex += len(defect_id_list)
		if startIndex >= totalNumberOfRecords:
			break
	return (defect_ids)


def __list_projects(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("projectFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	projectsList = CWS.ConfServiceClient.service.getProjects(filterSpec=filterSpec)
	for prj in projectsList:
		print (prj)


def __list_streams(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("streamFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	objStreams = CWS.ConfServiceClient.service.getStreams(filterSpec=filterSpec)
	if not objStreams:
		print("No streams found matching pattern", argv[0])
		return None
	return objStreams

def __list_triage_stores(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("triageStoreFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	objStores = CWS.ConfServiceClient.service.getTriageStores(filterSpec=filterSpec)
	for store in objStores:
		print (store)


def __get_snapshot(argv):
	sid = CWS.ConfServiceClient.factory.create("snapshotIdDataObj")
	sid.id = int(argv[0])
	try:
		sInfo = CWS.ConfServiceClient.service.getSnapshotInformation(snapshotIds = sid)
		return sInfo
	except Exception as e:
		print(str(e))
		return None

def __list_snapshots(argv):
	objStream = CWS.ConfServiceClient.factory.create("streamIdDataObj")
	objStream.name=argv[0]
	objSnapshotIds = CWS.ConfServiceClient.service.getSnapshotsForStream(streamId=objStream)
	for sid in objSnapshotIds:
		print (sid)
		sInfo = CWS.ConfServiceClient.service.getSnapshotInformation(snapshotIds = sid)
		print (sInfo)


def __list_defects_for_snapshot_scope(argv):
	projectId = CWS.ConfServiceClient.factory.create("projectIdDataObj")
	projectId.name = argv[0]
	filterSpec = CWS.DefServiceClient.factory.create("snapshotScopeDefectFilterSpecDataObj")
	filterSpec.issueComparison = "ABSENT"
	filterSpec.streamIncludeNameList = CWS.DefServiceClient.factory.create("streamIdDataObj")
	filterSpec.streamIncludeNameList.name = argv[1]
	filterSpec.statusNameList = "New"
	startIndex = 0
	totalNumberOfRecords = None
	defects_to_triage = []
	while True:
		pageSpec = CWS.ConfServiceClient.factory.create("pageSpecDataObj")
		if not totalNumberOfRecords:
			pageSpec.pageSize = 100
		else:
			pageSpec.pageSize = min(100, (totalNumberOfRecords - startIndex))
		pageSpec.startIndex = startIndex
		snapshotScope = CWS.DefServiceClient.factory.create("snapshotScopeSpecDataObj")
		snapshotScope.compareOutdatedStreams = True
		snapshotScope.showOutdatedStreams = True
		if len(argv) > 2:
			snapshotScope.compareSelector = argv[2]
			snapshotScope.showSelector = argv[3]
		else:
			snapshotScope.compareSelector = "first()"
			snapshotScope.showSelector = "last()"
		defectsPages = CWS.DefServiceClient.service.getMergedDefectsForSnapshotScope(projectId=projectId,
							filterSpec=filterSpec,
							pageSpec=pageSpec,
							snapshotScope=snapshotScope)
		if len(defectsPages) == 1:
			print(defectsPages)
			break
		# API Docs are WRONG: This was deduced by trial and error:
		# tuple ( "objectName" , value )
		# tuple ( "mergedDefectIds" , [ list ] )
		# tuple ( "mergedDefects" , [ list ] )
		# tuple ( "toalNumberOfRecords" , int )
		for page in defectsPages:
			if page[0] == 'mergedDefectIds':
				defect_id_list = page[1]
			elif page[0] == 'mergedDefects':
				defect_list = page[1]
			else:
				if not totalNumberOfRecords:
					totalNumberOfRecords = page[1]
					print('Total CIDs Filtered:', startIndex, totalNumberOfRecords)

		print('Processing index', startIndex, 'of', totalNumberOfRecords)

		# Now, get all the instances of a defect within a single defect CID
		dfilterSpec = CWS.DefServiceClient.factory.create("streamDefectFilterSpecDataObj")
		dfilterSpec.includeDefectInstances = True
		for defect in defect_id_list:	# <class 'suds.sudsobject.mergedDefectIdDataObj'>
			print('CID:', defect.cid)
			try:
				streamDefectData = CWS.DefServiceClient.service.getStreamDefects(mergedDefectIdDataObjs = [ defect ], filterSpec = dfilterSpec)
				process = False
				for item in streamDefectData:	# <class 'suds.sudsobject.streamDefectDataObj'>
					for a in item.defectStateAttributeValues:
						if a.attributeDefinitionId.name == 'DefectStatus':
							if a.attributeValueId.name == 'New':
								process = True
					if process:
						for instance in item.defectInstances: # <class 'suds.sudsobject.defectInstanceDataObj'>
							for event in instance.events: # <class 'suds.sudsobject.eventDataObj'>
								if event.main:
									j = { "cid" : defect.cid }
									pathname = re.sub('^/','',event.fileId.filePathname)
									patnname = re.sub(r'.+/workspace/.*intel-innersource/[^/]+/', '', pathname)
									j["filePathname"] = pathname
									j["lineNumber"] = event.lineNumber
									j["contentsMD5"] = event.fileId.contentsMD5
									defects_to_triage.append(j)
					else:
						for a in item.defectStateAttributeValues:
							if a.attributeDefinitionId.name == 'DefectStatus':
								print(a.attributeDefinitionId.name, a.attributeValueId.name)
			except Exception as e:
				print(e)

		startIndex += len(defect_list)
		if startIndex >= totalNumberOfRecords:
			break

	reduced_defects = [dict(t) for t in set([tuple(sorted(d.items())) for d in defects_to_triage])]
	output_filename = "/tmp/defects-{}-{}.out".format(argv[2], argv[3])
	try:
		open(output_filename, "w").write(json.dumps(reduced_defects))
	except:
		output_filename = None

	return reduced_defects

def __delete_stream(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("streamFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	print (filterSpec)
	objStreams = CWS.ConfServiceClient.service.getStreams(filterSpec=filterSpec)
	print (objStreams)
	if len(objStreams) > 0:
		print (objStreams[0].id)
		CWS.ConfServiceClient.service.deleteStream(streamId=objStreams[0].id)
	else:
		return None


def __create_project(argv):
	projectSpec = CWS.ConfServiceClient.factory.create("projectSpecDataObj")
	projectSpec.name=argv[0]
	print (projectSpec)
	objProject = CWS.ConfServiceClient.service.createProject(projectSpec=projectSpec)
	print (objProject)


def __create_stream(argv):
	projectId = CWS.ConfServiceClient.factory.create("projectIdDataObj")
	projectId.name = argv[0]
	streamSpec = CWS.ConfServiceClient.factory.create("streamSpecDataObj")
	streamSpec.description = argv[1]
	streamSpec.triageStoreId=CWS.ConfServiceClient.factory.create("triageStoreIdDataObj")
	streamSpec.enableDesktopAnalysis = True
	streamSpec.language = 'CXX'
	streamSpec.name = argv[1]
	streamSpec.summaryExpirationDays = 60
	streamSpec.autoDeleteOnExpiry = True
	streamSpec.triageStoreId.name = pkt_cov_config.TRIAGE_STORE
	componentMapId=CWS.ConfServiceClient.factory.create("componentMapIdDataObj")
	componentMapId.name = "Default"
	streamSpec.componentMapId = componentMapId
	try:
		CWS.ConfServiceClient.service.createStreamInProject(projectId=projectId,streamSpec=streamSpec)
	except suds.WebFault as f:
		if f.fault.detail.CoverityFault.errorCode in ['1301']:
			print ('Warning: %s %s' % (f.fault.detail.CoverityFault.errorCode,f.fault.faultstring))
		else:
			print('Warning: %s %s' % (f.fault.detail.CoverityFault.errorCode, f.fault.faultstring))
			print (f)
		raise f


def __copy_stream(argv):
	projectId = CWS.ConfServiceClient.factory.create("projectIdDataObj")
	projectId.name = argv[0]
	sourceStreamId = CWS.ConfServiceClient.factory.create("streamIdDataObj")
	sourceStreamId.name = argv[1]
	objStreamData = CWS.ConfServiceClient.service.copyStream(projectId=projectId,sourceStreamId=sourceStreamId)
	print(objStreamData)


def __rename_stream(argv):
	# Must obtain exsiting stream objects to make streamUpdate() work
	filterSpec = CWS.ConfServiceClient.factory.create("streamFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	streamsList = CWS.ConfServiceClient.service.getStreams(filterSpec=filterSpec)
	streamData = streamsList[0]
	streamId = CWS.ConfServiceClient.factory.create("streamIdDataObj")
	streamId.name = argv[0]
	streamSpec = CWS.ConfServiceClient.factory.create("streamSpecDataObj")
	streamSpec.name = argv[1]
	streamSpec.componentMapId = streamData.componentMapId
	streamSpec.triageStoreId = streamData.triageStoreId
	CWS.ConfServiceClient.service.updateStream(streamId=streamId, streamSpec=streamSpec)


def __create_triage_store(argv):
	triageStoreSpec = CWS.ConfServiceClient.factory.create("triageStoreSpecDataObj")
	triageStoreSpec.name = argv[0]
	triageStoreSpec.description = argv[1]
	CWS.ConfServiceClient.service.createTriageStore(triageStoreSpec=triageStoreSpec)


def __delete_project(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("projectFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	print (filterSpec)
	objProjects = CWS.ConfServiceClient.service.getProjects(filterSpec=filterSpec)
	print (objProjects)
	if len(objProjects) > 0:
		print (objProjects[0].id)
		CWS.ConfServiceClient.service.deleteProject(projectId=objProjects[0].id)


def __project_exists(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("projectFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	projectsList = CWS.ConfServiceClient.service.getProjects(filterSpec=filterSpec)
	return len(projectsList) > 0


def __stream_exists(argv):
	filterSpec = CWS.ConfServiceClient.factory.create("streamFilterSpecDataObj")
	filterSpec.namePattern=argv[0]
	streamsList = CWS.ConfServiceClient.service.getStreams(filterSpec=filterSpec)
	return len(streamsList) > 0

g_objProject = None

def __scan_build(argv, commit = True, arch = 'x86_64'):
	project = argv[0]
	stream = argv[1]
	snapshot = argv[2]
	config_file = argv[3]

	global g_objProject

	try:
#		__build_ignore_model([])

		arch_compiler = {
			"x86_64" : "gcc",
			"arm64" : "aarch64-linux-gnu-gcc"
		}

		xcompile_arg = {
			"x86_64" : "CROSS_COMPILE=",
			"arm64" : "CROSS_COMPILE=aarch64-linux-gnu-"
		}


		COV_IDIR = os.path.join(pkt_cov_config.WORKSPACE, pkt_cov_config.COV_IDIR, stream)

		cov_build_args = [ "--dir",  COV_IDIR ] \
		+ [ "--config",  pkt_cov_config.CONFIG_FILE ]\
		+ [ "--parallel-translate="+__nproc ]\
		+ [ "make" , "O="+pkt_cov_config.BUILD_DIR , "ARCH="+arch, "-j", __nproc ]
		if arch != 'x86_64':
			cov_build_args += [ xcompile_arg[arch] ]


		cov_import_scm_args = [ "--dir",  COV_IDIR ] \
		+ [ "--scm", "git" ] \
		+ [ "--log", "/dev/null" ]

		cov_analyze_args = [ "--dir",  COV_IDIR ] \
		+ [ "--ticker-mode", "no-spin" ] \
		+ [ "--strip-path", os.getcwd() + '/' ] \
		+ [ "--all" ] \
		+ [ "--aggressiveness-level", "high" ] \
		+ [ "--enable", "ENUM_AS_BOOLEAN" ] \
		+ [ "--enable", "HFA" ] \
		+ [ "--enable", "PARSE_ERROR" ] \
		+ [ "--enable", "STACK_USE" ] \
		+ [ "--enable", "USER_POINTER" ] \
		+ [ "-j", __nproc ]
#		+ [ "--model-file", ignore_model ] \

		cov_run_desktop_args = [ "--dir", COV_IDIR ] \
		+ [ "--analyze-scm-modified" ] \
		+ [ "--host" , pkt_cov_config.HOST ] \
		+ [ "--stream", stream ] \
		+ [ "--user", pkt_cov_config.USERNAME ] \
		+ [ "--password", pkt_cov_config.PASSWORD ] \
		+ [ "--scm", "git" ] \
		+ [ "--restrict-modified-file-regex", "+\.[ch]$" ]

		cov_commit_defects_args = [ "--dir",  COV_IDIR ] \
		+ [ "--ticker-mode", "no-spin" ] \
		+ [ "--scm", "git" ] \
		+ [ "--url",  pkt_cov_config.COMMIT_URL ] \
		+ [ "--stream",  stream ] \
		+ [ "--user",  pkt_cov_config.USERNAME ] \
		+ [ "--password",  pkt_cov_config.PASSWORD ] \
		+ [ "--description",  snapshot ]

		cov_manage_emit_args = [ "--dir",  COV_IDIR ] \
		+ [ "add-other-hosts" ]

		if not os.path.exists(pkt_cov_config.BUILD_DIR):
			os.makedirs(pkt_cov_config.BUILD_DIR)

		if not os.path.exists(pkt_cov_config.CONFIG_FILE):
			try_shell_command(__cov_configure, ["--config", pkt_cov_config.CONFIG_FILE, "--compiler", arch_compiler[arch], "--comptype", "gcc", "--template"])

		try:
			srcfile = os.path.join(g_objProject.config_repo.scmdir,config_file)
			if arch == 'x86_64':
				basename = 'x86_64_defconfig'
				dstfile = 'arch/x86/configs/x86_64_defconfig'
			elif arch == 'arm64':
				basename = 'defconfig'
				dstfile = 'arch/{}/configs/defconfig'
			else:
				raise ValueError("Invalid arch "+arch)
			__log.info("COPY {} {}".format(srcfile, dstfile))
			shutil.copy2(srcfile, dstfile)
		except Exception as e:
			print(e)
			print("Using existing {}".format(dstfile))

		try_shell_command(sh.Command("/usr/bin/make"),
						[ "O="+pkt_cov_config.BUILD_DIR, "ARCH="+arch, basename])

		# Add a compatibility argument for later versions of Python 'sh' package
		kwargs = sh.__version__ >= '2.0' and { "_return_cmd" : True } or {}

		# FIXME - figure out how to prevent cov-build for asking for more config options for arm64 builds
		cmd = __cov_build(cov_build_args, _in="y\ny\ny\ny\ny\ny\ny\ny\ny\n", _out=__log.info, _err=__log.error, **kwargs)
		__log.info(cmd.cmd)
		cmd.wait()
		__log.info("%s returns %d" , cmd.cmd[0], cmd.exit_code)
		if cmd.exit_code != 0:
			raise Exception("%s returns %d" % (cmd.cmd[0], cmd.exit_code))
#		try_shell_command(__cov_build, cov_build_args)
#		try_shell_command(__cov_import_scm, cov_import_scm_args)
		# Merge emits that may be left over from other runs or hosts
		try_shell_command(__cov_manage_emit, cov_manage_emit_args)
		try_shell_command(__cov_analyze, cov_analyze_args)
		if commit:
			while True:
				try:
					try_shell_command(__cov_commit_defects, cov_commit_defects_args)
					break
				except sh.TimeoutException as e:
					__log.error(str(e))

		# FIXME: remove leftover lock files in emit/ and output directories
		# FIXME: pjnozisk to ask Synopsys about BKM for dealiing with leftover lock files
		for lockfile in sh.find(COV_IDIR, "-iname" , "*.lock").split():
			try:
				os.remove(lockfile)
			except Exception as e:
				# Don't fail - just report error and move on
				print(lockfile, ":", e)

	except Exception as e:
		__log.error(traceback.format_exc())
		raise e
	return 0




def __get_baseline(argv):
	ref = argv[0]
	cmd = __git([ "show-ref", ref ], _err=print).wait()
	if cmd.exit_code != 0:
		__log.error(output.exit_code+'='+output.stderr.decode())
		return None
	else:
		commit = cmd.stdout.decode().strip().split()[0]
		baseline = __git.describe([ '--tags', '--match', 'v[4-9]*', commit ], _err=print).wait().stdout.decode().strip()
		baseline = re.sub(r'(?:.*)(v[4-9]\.[0-9]+(?:-r[ct][0-9]+|\.[0-9]{1,3}(?:-rt[0-9]+){0,1}){0,1}).*$', r'\1',
						baseline)
		__log.info("Baseline for "+ref+" is "+baseline)
		return baseline


def __get_staging_number(argv):
	ref = argv[0]
	cmd = __git([ "show-ref", ref], _err=print).wait()
	if cmd.exit_code != 0:
		__log.error(output.exit_code+'='+output.stderr.decode())
		return None
	else:
		refinfo = cmd.stdout.decode().strip().split()
		baseline = __git.describe([ '--tags', refinfo[1] ], _err=print).wait().stdout.decode().strip()
		baseline = re.sub(r'(?:.*)([0-9]{6}[-T][0-9]{4,6}Z{0,1})$', r'\1',  baseline)
		return baseline


def __update_triage_for_cid(argv):
	triageStore = CWS.DefServiceClient.factory.create("triageStoreIdDataObj")
	triageStore.name = argv[0]
	mergedDefectIdDataObjs = CWS.DefServiceClient.factory.create("mergedDefectIdDataObj")
	mergedDefectIdDataObjs.cid = argv[1]
	defectState = CWS.DefServiceClient.factory.create("defectStateSpecDataObj")
	defectState.defectStateAttributeValues = CWS.DefServiceClient.factory.create("defectStateAttributeValueDataObj")
	attr_dict = {
		"Legacy" : True,
#		"DefectStatus" : "Dismissed",
		"Classification" : "False Positive",
#		"Action" : "Ignore"
		"Action" : "Upstream"
	}
	attrs = []
	for k in attr_dict.keys():
		attr = CWS.DefServiceClient.factory.create("defectStateAttributeValueDataObj")
		attr.attributeDefinitionId = CWS.DefServiceClient.factory.create("attributeDefinitionIdDataObj")
		attr.attributeValueId = CWS.DefServiceClient.factory.create("attributeValueIdDataObj")
		attr.attributeDefinitionId.name = k
		attr.attributeValueId.name = attr_dict[k]
		attrs.append(attr)
	defectState.defectStateAttributeValues = attrs

	retries_left = 10
	while retries_left:
		try:
			ret = CWS.DefServiceClient.service.updateTriageForCIDsInTriageStore(triageStore=triageStore,
				 mergedDefectIdDataObjs=mergedDefectIdDataObjs, defectState=defectState)
			break
		except Exception as e:
			__log.error("%s", str(e))
			retries_left -= 1
			if retries_left:
				__log.error("%d retries left", retries_left)
				time.sleep(3)
			else:
				raise e
	return ret


def __clear_upstream_defects(argv):
	__log.info("Clear Upstream Defects for %s\n", argv[0])
	defect_ids = __list_defects_for_stream([ argv[0]  ])
	for cid in defect_ids:
		__log.info(cid)
		__update_triage_for_cid( [ pkt_cov_config.TRIAGE_STORE , cid ])


def __scan_ref_under_stream(argv):
	project = argv[0]
	stream = argv[1]
	ref = argv[2]
	arch = argv[3]

	__log.info ( "Stream %s Snapshot %s", stream, ref)

	__init_project_repos(project, stream, ref)

	__setup_stream([ project, stream ])
	snapshots = __get_snapshots_for_stream([ stream ])
	for s in snapshots.keys():
		if snapshots[s] == ref:
			__log.info("Stream %s Snapshot %s Already Scanned", stream, ref)
			return
	with pushd(g_objProject.repo.scmdir):
		__log.info("Creating Snapshot Scan for %s (%s)", stream, ref)
		try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
		__reset_to_master_and_pull()
		try_shell_command(__git, [ "checkout", ref ] )
#		config_ref, config_file = __get_config(project, ref)
		if arch == 'x86_64':
			config_file = "x86_64_defconfig"
		elif arch == 'arm64':
			config_file = "defconfig"
		else:
			raise ValueError("Invalid arch type "+arch)
		__scan_build([ project, stream , ref, config_file ], arch = arch)
		__reset_to_master_and_pull()

def __stored_baseline_exists(argv):
	baseline = argv[0]
	retval = os.path.exists(os.path.join(pkt_cov_config.BASELINE_IDIR, baseline))
	__log.info((retval and ' ' or 'NO ') + 'Stored baseline exists for ' + baseline)
	return retval 


def __retrieve_stored_baseline(argv):
	stream = argv[0]
	baseline = argv[1]
	dst = os.path.join(pkt_cov_config.WORKSPACE, pkt_cov_config.COV_IDIR, stream)
	src = os.path.join(pkt_cov_config.BASELINE_IDIR, baseline)
	lock_file = os.path.join(pkt_cov_config.BASELINE_IDIR, "baseline.lck")
	__log.info("Acquiring Baseline Lock...")
	with SoftFileLock(lock_file).acquire():
		__log.info("Baseline Lock Acquired...")
		try:
			__log.info("Retrieving {}".format(src))
			shutil.rmtree(dst, ignore_errors=True)
			shutil.copytree(src, dst)
		except FileExistsError as e:
			__log.info("Baseline {} already retrieved".format(dst))


def __store_baseline(argv):
	stream = argv[0]
	baseline = argv[1]
	src = os.path.join(pkt_cov_config.WORKSPACE, pkt_cov_config.COV_IDIR, stream)
	dst = os.path.join(pkt_cov_config.BASELINE_IDIR, baseline)
	lock_file = os.path.join(pkt_cov_config.BASELINE_IDIR, "baseline.lck")
	__log.info("Acquiring Baseline Lock...")
	with SoftFileLock(lock_file).acquire():
		__log.info("Baseline Lock Acquired...")
		try:
			__log.info("Storing {} to {}".format(src,dst))
			shutil.copytree(src, dst)
		except FileExistsError as e:
			__log.info("Baseline {} already stored".format(dst))


def __commit_stored_baseline(argv):
	stream = argv[0]
	baseline = argv[1]
	dst = os.path.join(pkt_cov_config.WORKSPACE, pkt_cov_config.COV_IDIR, stream)
	# Use lock file to make sure only one host at a time tries to reset the baseline emits
	lock_file = os.path.join(pkt_cov_config.BASELINE_IDIR, "baseline.lck")
	__log.info("Acquiring Baseline Lock...")
	with SoftFileLock(lock_file).acquire():
		__log.info("Baseline Lock Acquired...")
		cov_manage_emit_args = [ "--dir",  dst , "reset-host-name" ]
		try_shell_command(__cov_manage_emit, cov_manage_emit_args)
		cov_commit_defects_args = [ "--dir", dst ] \
		+ [ "--ticker-mode", "no-spin" ] \
		+ [ "--scm", "git" ] \
		+ [ "--url",  pkt_cov_config.COMMIT_URL ] \
		+ [ "--stream",  stream ] \
		+ [ "--user",  pkt_cov_config.USERNAME ] \
		+ [ "--password",  pkt_cov_config.PASSWORD ] \
		+ [ "--description",  baseline ]
		while True:
			try:
				__log.info('Committing stored baseline {} to {}'.format(baseline, stream))
				try_shell_command(__cov_commit_defects, cov_commit_defects_args)
				break
			except sh.TimeoutException as e:
				__log.error(str(e))

import csv
def __save_defects_for_snapshot_scope(project, stream, base_snapid, new_snapid):
	projectId = CWS.ConfServiceClient.factory.create("projectIdDataObj")
	projectId.name = project
	startIndex = 0
	totalNumberOfRecords = None
	defects_to_triage = []
	#list the new snapshot :
	fd_new_Ids = open(new_snapid+'_mergedDefectIds.txt', 'w')
	fd_news = open(new_snapid+'_mergedDefects.txt', 'w')
	fd_csv = open(new_snapid+'_mergedDefects.csv', 'w')
	writer = csv.writer(fd_csv)
	head = ['CID', 'Type', 'Impact', 'Status','Files','FunctionName']
	writer.writerow( head )
	new_high_defect = []
	new_middle_defect = []
	new_low_defect = []
	while True:
		pageSpec = CWS.ConfServiceClient.factory.create("pageSpecDataObj")
		if not totalNumberOfRecords:
			pageSpec.pageSize = 1000
		else:
			pageSpec.pageSize = min(1000, (totalNumberOfRecords - startIndex))
		pageSpec.startIndex = startIndex
		snapshotScope = CWS.DefServiceClient.factory.create("snapshotScopeSpecDataObj")
		snapshotScope.compareOutdatedStreams = True
		snapshotScope.showOutdatedStreams = True
		snapshotScope.compareSelector = base_snapid
		snapshotScope.showSelector = new_snapid
		defectsPages = CWS.DefServiceClient.service.getMergedDefectsForSnapshotScope(projectId=projectId,
								pageSpec=pageSpec,
								snapshotScope=snapshotScope)

		if len(defectsPages) == 1:
			print(defectsPages)
		else:
			for page in defectsPages:
				#print(page)
				if page[0] == 'mergedDefectIds':
					#print(page)
					fd_new_Ids.write( str(page ))
					defect_id_list = page[1]
				elif page[0] == 'mergedDefects':
					fd_news.write( str(page ))
					for item in page[1]:
					#head = ['CID', 'Type', 'Impact', 'Status','Files','FunctionName']
						CID = item.cid
						Type = item.displayType
						Impact = item.displayImpact
						Files = item.filePathname
						try:
							FunctionName = item.functionName
						except:
							FunctionName = ''
						for Attribute in item.defectStateAttributeValues:
							if Attribute.attributeDefinitionId.name == 'DefectStatus':
								Status = Attribute.attributeValueId.name
								break
						row = [CID, Type, Impact, Status,Files,FunctionName]
						writer.writerow( row )
						if Status != 'Dismissed':
							if Impact == 'High':
								new_high_defect.apend(row)
							elif Impact == 'Medium':
								new_middle_defect.apend(row)
							else:
								new_low_defect.apend(row)
					defect_list = page[1]
				else:
					if not totalNumberOfRecords:
						totalNumberOfRecords = page[1]
						print(new_snapid+ "Total detected CIDs number is: ", totalNumberOfRecords)
		startIndex += len(defect_list)
		if startIndex >= totalNumberOfRecords:
			fd_new_Ids.close()
			fd_news.close()
			fd_csv.close()
			break
	print( new_high_defect)
	print(new_middle_defect)
	print(new_low_defect)
	return new_high_defect, new_middle_defect, new_low_defect

def __save_report(argv):
#	project = argv[0]
#	stream = argv[1]
#	ref = argv[2]

	ref = argv[0]
	arch = argv[1]
	if len(argv) > 2:
		new_method = argv[2]
	else:
		new_method = None

	# Lookup project, stream and baseline based on ref name and arch
	project, stream, baseline = __get_stream_for( [ ref, arch , new_method])

	print(f"Ref is {ref}")
	print(f"Project is {project}")
	print(f"Stream is {stream}")
	print(f"Baseline is {baseline}")
	#__list_snapshots(str(stream))
	objStream = CWS.ConfServiceClient.factory.create("streamIdDataObj")
	objStream.name = stream
	objSnapshotIds = CWS.ConfServiceClient.service.getSnapshotsForStream(streamId=objStream)
	#base snapid
#	base_snapid = str(objSnapshotIds[0].id)
	base_snapid = ''
	new_snapid = ''
#	print("baseline snapid is " + base_snapid)
	for sid in objSnapshotIds:
		#print (sid)
		sInfo = CWS.ConfServiceClient.service.getSnapshotInformation(snapshotIds = sid)
		if baseline == sInfo[0].description:
			base_snapid = str(sid.id)
			print("baseline snapid is " + base_snapid)
		if ref in sInfo[0].description:
			print(ref +"'s snapid is "+ str(sid.id))
			new_snapid = str(sid.id)
			break
	if base_snapid == '':
		print(f"Can't find baseline snapshot {baseline}, please check the server and stream!")
		sys.exit(1)	# No use continuing from here - fail the run
	if new_snapid == '':
		print(f"Can't find ref snapshot {ref}, please check the server and stream!")
		sys.exit(1)	# No use continuing from here - fail the run
	projectId = CWS.ConfServiceClient.factory.create("projectIdDataObj")
	projectId.name = project
	startIndex = 0
	totalNumberOfRecords = None
	defects_to_triage = []
	#list the new snapshot :
	#fd_reports = open(ref+'__'+new_snapid+'.txt', 'w')
	fd_reports = open(ref.split('/')[-1]+'__'+new_snapid+'.txt', 'w')
	fd_csv = open(new_snapid+'_Defects.csv', 'w')
	writer = csv.writer(fd_csv)
	head = ['CID', 'Type', 'Impact', 'Status','Files','FunctionName']
	writer.writerow( head )
	new_high_defect = []
	new_middle_defect = []
	new_low_defect = []
	fd_reports.write("This is the coverity scan report for "+ref+'\r\n')
	fd_reports.write("The project name is "+project+'\r\n')
	fd_reports.write("The stream name is "+stream+'\r\n')
	fd_reports.write("The Snapshot Id is "+new_snapid+'\r\n')
	fd_reports.write("The baseline Snapshot Id is "+base_snapid+'\r\n')
	while True:
		pageSpec = CWS.ConfServiceClient.factory.create("pageSpecDataObj")
		if not totalNumberOfRecords:
			pageSpec.pageSize = 1000
		else:
			pageSpec.pageSize = min(1000, (totalNumberOfRecords - startIndex))
		pageSpec.startIndex = startIndex
		snapshotScope = CWS.DefServiceClient.factory.create("snapshotScopeSpecDataObj")
		snapshotScope.compareOutdatedStreams = True
		snapshotScope.showOutdatedStreams = True
		snapshotScope.compareSelector = base_snapid
		snapshotScope.showSelector = new_snapid
		defectsPages = CWS.DefServiceClient.service.getMergedDefectsForSnapshotScope(projectId=projectId,
								pageSpec=pageSpec,
								snapshotScope=snapshotScope)
		if len(defectsPages) == 1:
			print(defectsPages)
		else:
			for page in defectsPages:
				#print(page)
				if page[0] == 'mergedDefectIds':
					#print(page)
					defect_id_list = page[1]
				elif page[0] == 'mergedDefects':
					for item in page[1]:
					#head = ['CID', 'Type', 'Impact', 'Status','Files','FunctionName']
						CID = item.cid
						Type = item.displayType
						Impact = item.displayImpact
						Files = item.filePathname
						try:
							FunctionName = item.functionName
						except:
							FunctionName = ''
						for Attribute in item.defectStateAttributeValues:
							if Attribute.attributeDefinitionId.name == 'DefectStatus':
								Status = Attribute.attributeValueId.name
								break
						row = [CID, Type, Impact, Status,Files,FunctionName]
						writer.writerow( row )
						if Status == 'New':
							if Impact == 'High':
								new_high_defect.append(row)
							elif Impact == 'Medium':
								new_middle_defect.append(row)
							else:
								new_low_defect.append(row)
					defect_list = page[1]
				else:
					if not totalNumberOfRecords:
						totalNumberOfRecords = page[1]
						print(new_snapid+ "Total detected CIDs number is: ", totalNumberOfRecords)
		startIndex += len(defect_list)
		if startIndex >= totalNumberOfRecords:
			fd_csv.close()
			break
	fd_reports.write("There are %d new high defects \r\n" %len(new_high_defect))
	fd_reports.write("There are %d new middle defects \r\n" %len(new_middle_defect))
	fd_reports.write("There are %d new low defects\r\n " %len(new_low_defect))
	fd_reports.write("more information please check in coverity web: " + pkt_cov_config.COV_URL + "\r\n")
	fd_reports.write("\r\n ")

	fd_reports.write( str(new_high_defect))
	fd_reports.write("\r\n ")
	fd_reports.write(str(new_middle_defect))
	fd_reports.write("\r\n ")
	fd_reports.write(str(new_low_defect))
	fd_reports.close()

	if len(new_high_defect) or len(new_middle_defect) or len(new_low_defect):
		result = 2
	else:
		result = 1

	import upload_dashboard
	reporturl = upload_dashboard.save(file_list = [new_snapid+'_Defects.csv',ref.split('/')[-1]+'__'+new_snapid+'.txt'],tag=ref,result=result,category='coverity')
	




def __run_get_coverity_history(argv):
	COVERTY_BAK_HOST = os.environ.get('IKT_BJ_DB', 'ikt.bj.intel.com')
	COVERTY_BAK_API = f'https://{COVERTY_BAK_HOST}/api/test_report/?tag='
	ref = argv[0]
	if '/' in ref:
		tag = ref.split('/')[-1]
	else:
		tag = ref

	pwd = os.getcwd()
	coverity_dir = os.path.join(pwd,'coverity_dir')
	coverity_csvfile = None
	coverity_txtfile = None
	if not os.path.exists(coverity_dir):
		os.mkdir(coverity_dir)
	else:
		shutil.rmtree(coverity_dir)
		os.mkdir(coverity_dir)
	url = f'{COVERTY_BAK_API}{tag}'
	req = requests.get(url, verify=False)
	data = req.json()
	assert data, f'ERROR: {url} returns no data <{data}>'
	coverity_bak_url = None
	for i in data:
		if i.get('tag') == tag:
			if i.get('Coverity'):
				coverity_bak_url = i.get('Coverity')[0].get('reporturl')
	assert coverity_bak_url, f'Not found coverity url. tag name={tag}'

	# FIXME = these os.system() calls need to be converted to more Pythonic requests.get() calls
	# FIXME = this can be reduced to a single call
	cmd0 = 'wget --no-check -P %s %s/ -r -np -nd -R index.html*  -e robots=off'% (coverity_dir,coverity_bak_url)
	os.system(cmd0)

	coverity_csvfiles = os.listdir(coverity_dir)
	for file in  coverity_csvfiles:
		if 'csv' in file and 'History' not in file:
			coverity_csvfile = os.path.join(coverity_dir,file)
			coverity_new_csvfile_name = file.split('.csv')[0]+'_Triage_History.csv'
			coverity_new_csvfile_path = os.path.join(coverity_dir,coverity_new_csvfile_name)
		if 'txt' in file and 'History' not in file:
			coverity_txtfile = os.path.join(coverity_dir,file)
			coverity_new_txtfile_path = os.path.join(coverity_dir,file.split('.txt')[0]+'_Triage_History.txt')
	f0 = open(coverity_txtfile,'r')
	for f in f0.readlines():
		if 'The Snapshot Id is' in f:
			New_Snapshot_id = f.split('The Snapshot Id is')[-1].strip()
		elif 'The baseline Snapshot Id is' in f:
			Baseline_Snapshot_id = f.split('The baseline Snapshot Id is')[-1].strip()
		elif 'The project name is' in f:
			project = f.split('The project name is')[-1].strip()
		elif 'The stream name is' in f:
			stream = f.split('The stream name is')[-1].strip()
	print(tag,New_Snapshot_id,Baseline_Snapshot_id)

	f1 = open(coverity_csvfile, 'r')
	reader = csv.DictReader(f1)
	f2 = open(coverity_new_csvfile_path,'w')
	writer = csv.DictWriter(f2,fieldnames=['CID','Type','Impact','Status','Files','Triage_history'])
	writer.writeheader()

	fd_reports = open(coverity_new_txtfile_path, 'w')
	fd_reports.write("This is the coverity scan report for "+tag+'\r\n')
	fd_reports.write("The project name is "+project+'\r\n')
	fd_reports.write("The stream name is "+stream+'\r\n')
	fd_reports.write("The Snapshot Id is "+New_Snapshot_id+'\r\n')
	fd_reports.write("The baseline Snapshot Id is "+Baseline_Snapshot_id+'\r\n')



	old_csv_new_defect_ids = []

	for row in reader:
		cid = row['CID']
		status = row['Status']
		if status == 'New':
			old_csv_new_defect_ids.append(cid)

	coverity_all = __get_coverity_all(New_Snapshot_id,Baseline_Snapshot_id,old_csv_new_defect_ids,project)
#	print(coverity_all)
	print(len(coverity_all))

	new_high_defect = []
	new_middle_defect = []
	new_low_defect = []
	change_defect = {}
	noblock_defects = []
	block_defects = []
	ignore_action = ["Ignore", "Upstream", "Whiltlisted"]
	for cid,row in coverity_all.items():
		Type = row[1]
		impact = row[2]
		status = row[3]
		files = row[4]
		history = __get_cov_triage_history(cid)
		print(history)

		if status == 'New':
			if impact == 'High':
				new_high_defect.append(row)
			elif impact == 'Medium':
				new_middle_defect.append(row)
			else:
				new_low_defect.append(row)
		else:
			if status not in change_defect:
				change_defect[status] = [row]
			else:
				change_defect[status].append(row)

		writer.writerow({
					'CID':cid,
					'Type':Type,
					'Impact':impact,
					'Status':status,
					'Files':files,
					'Triage_history':history
					})
		if status == "Triaged":
			if history["action"][-1] in ignore_action:
				noblock_defects.append(row)
			else:
				block_defects.append(row)
		elif status in [ "Dismissed", "Absent Dismissed",  "Fixed" ]:
			noblock_defects.append(row)
		else:
			block_defects.append(row)
	f1.close()
	f2.close()
	fd_reports.write("%s defect(s) was/were triaged. %s defect(s) no block, %s defects(s) block.For details, please refer to %s.\r\n"% (len(old_csv_new_defect_ids),len(noblock_defects),len(block_defects),coverity_new_csvfile_name))
	fd_reports.write("%s defects(s) block,\r\nDetials:%s\r\n"% (len(block_defects),block_defects))
	fd_reports.write("%s defects(s) no block,\r\nDetials:%s\r\n"% (len(noblock_defects),noblock_defects))
	fd_reports.write("%s high-level new defects are currently unprocessed. \r\nDetails:" %len(new_high_defect))
	fd_reports.write(str(new_high_defect))
	fd_reports.write("\r\n%s middle-level new defects are currently unprocessed. \r\nDetails:" %len(new_middle_defect))
	fd_reports.write(str(new_middle_defect))
	fd_reports.write("\r\n%s low-level new defects are currently unprocessed. \r\nDetails:" %len(new_low_defect))
	fd_reports.write(str(new_low_defect))
	fd_reports.write("\r\nmore information please check in coverity web: " + pkt_cov_config.COV_URL + "\r\n")
	fd_reports.write("\r\n ")
	fd_reports.close()
	if len(block_defects):
		result = 2
	else:
		result = 1
	import upload_dashboard
	upload_dashboard.save(file_list = [coverity_new_csvfile_path,coverity_new_txtfile_path],tag=ref,result=result,category='coverity')

def __get_coverity_all(new_snapid,base_snapid,old_defectids,project):
	coverity_all = {}
	projectId = CWS.ConfServiceClient.factory.create("projectIdDataObj")
	projectId.name = project
	startIndex = 0
	totalNumberOfRecords = None
	while True:
		pageSpec = CWS.ConfServiceClient.factory.create("pageSpecDataObj")
		if not totalNumberOfRecords:
			pageSpec.pageSize = 1000
		else:
			pageSpec.pageSize = min(1000, (totalNumberOfRecords - startIndex))
		pageSpec.startIndex = startIndex
		snapshotScope = CWS.DefServiceClient.factory.create("snapshotScopeSpecDataObj")
		snapshotScope.compareOutdatedStreams = True
		snapshotScope.showOutdatedStreams = True
		snapshotScope.compareSelector = base_snapid
		snapshotScope.showSelector = new_snapid
		# Get only the defects not in the baseline scan for performance reasons (they are already auto-dismissed)
		filterSpec = CWS.DefServiceClient.factory.create("snapshotScopeDefectFilterSpecDataObj")
		filterSpec.issueComparison = "ABSENT"
		defectsPages = CWS.DefServiceClient.service.getMergedDefectsForSnapshotScope(projectId=projectId,
								filterSpec=filterSpec,
								pageSpec=pageSpec,
								snapshotScope=snapshotScope)

		if len(defectsPages) == 1:
			print(defectsPages)
		else:
			for page in defectsPages:
				#print(page)
				if page[0] == 'mergedDefectIds':
					#print(page)
					defect_id_list = page[1]
				elif page[0] == 'mergedDefects':
					for item in page[1]:
						CID = str(item.cid)
						Type = item.displayType
						Impact = item.displayImpact
						Files = item.filePathname
						if CID in old_defectids:
							try:
								FunctionName = item.functionName
							except:
								FunctionName = ''
							for Attribute in item.defectStateAttributeValues:
								if Attribute.attributeDefinitionId.name == 'DefectStatus':
									Status = Attribute.attributeValueId.name
									coverity_all[CID] = [CID,Type,Impact,Status,Files]
									break
					defect_list = page[1]
				else:
					if not totalNumberOfRecords:
						totalNumberOfRecords = page[1]
						print(new_snapid+ "Total detected CIDs number is: ", totalNumberOfRecords)
		startIndex += len(defect_list)
		if startIndex >= totalNumberOfRecords:
			break

	return coverity_all

def __get_cov_triage_history(cid,triage_store_name = pkt_cov_config.TRIAGE_STORE):
	merge_defect = CWS.DefServiceClient.factory.create("mergedDefectIdDataObj")
	merge_defect.cid = cid
	merge_defect.mergeKey = cid
	triage_store = CWS.DefServiceClient.factory.create("triageStoreIdDataObj")
	triage_store.name = triage_store_name

	retries_left = 10
	while retries_left:
		try:
			triage_history = CWS.DefServiceClient.service.getTriageHistory(mergedDefectIdDataObj=merge_defect,
																			triageStoreIds=triage_store)
			break
		except Exception as e:
			__log.error("%s", str(e))
			retries_left -= 1
			if retries_left:
				__log.error("%d retries left", retries_left)
				time.sleep(3)
			else:
				raise e

	triage_history_info = {}
	for history in triage_history:
		for category in history.attributes:
			if category.attributeDefinitionId.name not in triage_history_info:
				triage_history_info[category.attributeDefinitionId.name] = [category.attributeValueId.name]
			else:
				triage_history_info[category.attributeDefinitionId.name].insert(0,category.attributeValueId.name)
				triage_history_info[category.attributeDefinitionId.name].insert(1,'-->')
	return triage_history_info


def __scan_ref_no_bl(argv):
	project = argv[0]
	stream = argv[1]
	ref = argv[2]
	arch = argv[3]

	global g_objProject

	__init_project_repos(project, stream, ref)

	with pushd(g_objProject.repo.scmdir):
		try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
		__reset_to_master_and_pull()
		try_shell_command(__git, [ "checkout", ref ] )
		if arch == 'x86_64':
			config_file = "x86_64_defconfig"
		elif arch == 'arm64':
			config_file = "defconfig"
		else:
			raise ValueError("Invalid arch type "+arch)
		__scan_build([ project, stream , ref, config_file ], arch = arch)
		__reset_to_master_and_pull()


def __scan_ref(argv):
	project = argv[0]
	stream = argv[1]
	ref = argv[2]

	global g_objProject

	__init_project_repos(project, stream, ref)

	if stream == ref:
		__log.info("Creating Baseline Scan for %s", ref)
		with pushd(g_objProject.repo.scmdir):
			try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
			__reset_to_master_and_pull()
			if not __stored_baseline_exists([ ref ]):
				try_shell_command(__git, [ "checkout", ref ] )
				config_ref, config_file = __get_config(project, ref)
				__scan_build([ project, stream , ref, config_file ], commit = False)
				__store_baseline([ stream, ref ])
				__reset_to_master_and_pull()
		return

	__log.info ( "Stream %s Snapshot %s", stream, ref)
	__setup_stream([ project, stream ])
	baseline = None
	snapshots = __get_snapshots_for_stream([ stream ])
	for s in snapshots.keys():
		if snapshots[s] == ref:
			__log.info("Stream %s Snapshot %s Already Scanned", stream, ref)
			return

	with pushd(g_objProject.repo.scmdir):
		if len(snapshots.keys()) == 0:		# No baseline
			__log.info("Creating Baseline Scan for %s", stream)
			try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
			__reset_to_master_and_pull()
			baseline = __get_baseline([ ref ])
			if not baseline:
				raise Exception("Baseline for "+ref+" cannot be found")
			if __stored_baseline_exists([ baseline ]):
				__retrieve_stored_baseline([ stream, baseline ])
				__commit_stored_baseline([ stream, baseline ])
				__clear_upstream_defects([ stream ])
			else:
				try_shell_command(__git, [ "checkout", baseline ] )
#				config_ref, config_file = __get_config(project, baseline)
				config_file = 'arch/x86/configs/x86_64_defconfig'
				__scan_build([ project, stream , baseline, config_file ])
				__clear_upstream_defects([ stream ])
				__store_baseline([ stream, baseline ])
			__reset_to_master_and_pull()

		if ref != baseline:
			__log.info("Creating Snapshot Scan for %s (%s)", stream, ref)
			try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
			__reset_to_master_and_pull()
			try_shell_command(__git, [ "checkout", ref ] )
			config_ref, config_file = __get_config(project, ref)
			__scan_build([ project, stream , ref, config_file ])
			__reset_to_master_and_pull()


def __get_stream_for(argv):

	snapshot = argv[0]
	arch = argv[1]
	if len(argv) > 2:
		new_method = argv[2]
	else:
		new_method = None

	match = re.search(r"v?(\d+\.\d+)(\.\d+)?(-rc\d+)?(-rt\d+)?", snapshot)
	if match:
		baseline = match.group(0)
	else:
		raise ValueError(f"Cannot determine baseline for {snapshot} : no upstream tag found in ref name")

	if 'mainline-tracking' in snapshot or 'iotg-next' in snapshot:
		project = 'NEX_kernel_MLT'
	else:
		match = re.search(r"v?(\d+\.\d+)", baseline)
		if match:
			base_kernel = match.group(1)
			print(f"Base kernel = {base_kernel}")
			project = "NEX_kernel_"+re.sub("\.", "_", base_kernel)
	stream = f'{baseline}_{arch}'
	if new_method:
		# FIXME This should not be hardcoded
		if 'xenomai' in snapshot:
			stream += '-xenomai'
		# FIXME This should not be hardcoded
		stream += '_partial'

	return project, stream, baseline


def __scan_ref_3(argv):
	ref = argv[0]
	arch = argv[1]

	global g_objProject

	project, stream, baseline = __get_stream_for([ ref,  arch ])

	__init_project_repos(project, stream, ref)

	__log.info ( "Stream %s Baseline %s", stream, baseline)
	__setup_stream([ project, stream ])
	baseline_found = False
	snapshots = __get_snapshots_for_stream([ stream ])
	for s in snapshots.keys():
		print(snapshots[s])
		if snapshots[s] == ref:
			__log.info("Stream %s Snapshot %s Already Scanned", stream, ref)
			return
		if snapshots[s] == baseline:
			__log.info("Stream %s Baseline %s Already Scanned", stream, baseline)
			baseline_found = True

	with pushd(g_objProject.repo.scmdir):
		if not baseline_found:
			__log.info("Creating Baseline Scan for %s", stream)
			try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
			__reset_to_master_and_pull()
			if arch == 'x86_64':
				config_file = "arch/x86/configs/x86_64_defconfig"
			elif arch == 'arm64':
				config_file = "arch/arm64/configs/defconfig"
			else:
				raise ValueError("Invalid arch type "+arch)
			try_shell_command(__git, [ "checkout", baseline ] )
			__scan_build([ project, stream , baseline, config_file , arch ])
			__clear_upstream_defects([ stream ])
			__reset_to_master_and_pull()

		__log.info("Creating Snapshot Scan for %s (%s)", stream, ref)
		try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
		__reset_to_master_and_pull()
		try_shell_command(__git, [ "checkout", ref ] )
		config_ref, config_file = __get_config(project, ref)
		__scan_build([ project, stream , ref, config_file, arch ])
		__reset_to_master_and_pull()



def __get_cov_config(project, snapshot):

	global g_objProject

	staging_number = re.sub('.+([0-9]{6}[-T][0-9]{4,6}Z{0,1})$', '\\1', snapshot)
	with pushd(g_objProject.config_repo.scmdir):
		__reset_to_master_and_pull()
		branches = __git('--no-pager', 'branch', '-a', '--no-color').stdout.decode().strip().split("\n")
		for line in branches:
			match = re.search(r''+staging_number+'$', line)
			if match:
				ref = re.sub('  remotes/', '', line)
				__git.checkout(ref)
				config_files = __git('--no-pager', 'ls-files').stdout.strip().decode().split('\n')
				for config in defconfig_priority:
					if config in config_files:
						print('Using Branch {} Kconfig {} from {}'.format(ref, config, config_dir))
						return ref, config
	raise ValueError('No Config Branch or Tag found for '+snapshot)

'''
def __get_cov_config_2(project, __ref, arch):

	global g_objProject

	with pushd(g_objProject.config_repo.scmdir):
		__reset_to_master_and_pull()
		match = re.search = re.sub('.+([0-9]{6}[-T][0-9]{4,6}Z{0,1})$', __ref)
		if match:
		
		branches = __git('--no-pager', 'branch', '-a', '--no-color').stdout.decode().strip().split("\n")
		for line in branches:
			match = re.search(r''+staging_number+'$', line)
			if match:
				ref = re.sub('  remotes/', '', line)
				__git.checkout(ref)
				config_files = __git('--no-pager', 'ls-files').stdout.strip().decode().split('\n')
				for config in defconfig_priority:
					if config in config_files:
						print('Using Branch {} Kconfig {} from {}'.format(ref, config, config_dir))
						return ref, config
	raise ValueError('No Config Branch or Tag found for '+ref)
'''

def __get_cov_config_2(project, __ref, arch):
	if arch == 'x86_64':
		return __ref, 'x86_64_defconfig'
	else:
		return __ref, 'defconfig'


def __scan_ref_2(argv):
	project = argv[0]
	stream = argv[1]
	ref = argv[2]
	arch = argv[3]

	global g_objProject

	__init_project_repos(project, stream, ref)

	__log.info ( "Stream %s Snapshot %s", stream, ref)
	__setup_stream([ project, stream ])

	snapshots = __get_snapshots_for_stream([ stream ])
	for s in snapshots.keys():
		if snapshots[s] == ref:
			__log.info("Stream %s Snapshot %s Already Scanned", stream, ref)
			return

	with pushd(g_objProject.repo.scmdir):
		__log.info("Creating Snapshot Scan for %s (%s)", stream, ref)
		try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
		__reset_to_master_and_pull()
		try_shell_command(__git, [ "checkout", ref ] )
		config_ref, config_file = __get_cov_config_2(project, ref, arch)
		__log.info("Config File: "+config_file)
		__scan_build([ project, stream , ref , config_file ], arch = arch)
		__reset_to_master_and_pull()


def __setup_stream(argv):
	project = argv[0]
	stream = argv[1]

#	if not __project_exists([ project ]):
#		__log.info ("Creating Project %s", project)
#		__create_project([ project ])
#	else:
#		__log.info ("Project %s Exists", project)

	if not __stream_exists( [ stream ] ):
		__log.info ("Creating Stream %s", stream )
		if project == 'NEX_kernel_NEXT':
			project = 'NEX_kernel_MLT'
		__create_stream([ project, stream ])
	else:
		__log.info ("Stream %s Exists", stream )


ignore_model = '/tmp/ignore.xmldb'
ignore_source = '/tmp/my_printk.c'


def __build_ignore_model(argv):
	try:
		os.unlink(ignore_model)
	except OSError:	# equivalent to rm -f
		pass
	model_source = '\n\
int _raw_spin_trylock(void **l) {\n\
	int result;\n\
	if (result == 0) {\n\
		return result;\n\
	}\n\
	__coverity_recursive_lock_acquire__(*l);\n\
	return result;\n\
}\n\
int __raw_spin_trylock(void **l) { return _raw_spin_trylock(l); }'
	with open(ignore_source, "w") as outfile:
		outfile.write(model_source)
	try_shell_command(__cov_make_library, ['--concurrency', '--security', '--output-file',  ignore_model, ignore_source])


def _triage_new_defects(defect_list, staging_ref, arch = 'x86_64', fix=False, upstream_repo = None):


	# Private function to Generate a reformatted string representation
	# of a tag location to help with version comparisons
	def __gen_compare_string(versionstr):

		version_regexp = r"v?(\d+)(?:\.)(\d+)(?:\.)?(\d+)?(-rc\d+)?(-rt\d+)?"
		match = re.match(version_regexp, versionstr)
		if not match:
			print('<'+versionstr+'>')
			return "009009009"
		bl_list = list(match.groups())
		bl_list[0] = int(bl_list[0])
		bl_list[1] = int(bl_list[1])
		if bl_list[2] is None:
			bl_list[2] = '0'
		if bl_list[3] is not None:
			bl_list[2] = bl_list[3]
		if not bl_list[2].isdigit():
			fmtstr = "%03d%03d%s"
		else:
			fmtstr = "%03d%03d%03d"
			bl_list[2] = int(bl_list[2])
		return  fmtstr % (bl_list[0], bl_list[1], bl_list[2])

	global g_objProject

	project, stream, baseline = __get_stream_for( [ staging_ref, arch ])
	__init_project_repos(project, stream, staging_ref)

	try:
		os.chdir(g_objProject.repo.scmdir)
		__git("fetch" , "--all", "--tags", "--force")
	except Exception as e:
		print(e.stderr.decode())
		return False

	try:
		if '/' in staging_ref:
			baseline_tag = __git("describe", "--match", 'v[23456789]*' , 'origin/'+staging_ref).stdout.decode().strip()
		else:
			baseline_tag = __git("describe", "--match", 'v[23456789]*' , staging_ref).stdout.decode().strip()
		baseline_tag = re.sub('(-rc[0-9]+){0,1}-.*$','\\1', baseline_tag)
		print("BASELINE:", baseline_tag)
	except Exception as e:
		print(e.args)
		print("FATAL ERROR: Cannot determine upstream baseline for {}".format(staging_ref))
		return False

	cids_to_dismiss = set()
	cids_to_triage = set()
	ANSI_RED =  "\033[31m"
	ANSI_YELLOW  = "\033[33m"
	ANSI_OFF = "\033[0m"

	for defect in defect_list:
		if defect['cid'] in cids_to_triage:
			# Don't bother looking, we already know it won't be dismissed
			continue
		__git("checkout", staging_ref)

		#FIXME Need more robust way to truncate full paths stored in Coverity defects
		kernel_TLDs = [ 'android', 'arch', 'block', 'certs', 'crypto', 'Documentation', 'drivers', 'firmware', 'fs', 'include', 'init', 'io_uring', 'ipc', 'kernel', 'lib', 'mm', 'net', 'samples', 'scripts', 'security', 'rust', 'sound', 'tools', 'usr', 'virt' ]
		tld = defect["filePathname"][:defect["filePathname"].index('/')]
		regexp = '^.*?/{0,1}('+"|".join(tld for tld in kernel_TLDs)+')'
		relpath = re.sub(regexp, '\\1', defect["filePathname"])
		# 2nd pass to remove any leftover *.kernel.* path elements
		relpath = re.sub('^kernel\..+?/', '', relpath)

		if relpath != defect["filePathname"]:
			print(f"CID: {str(defect['cid'])} WARNING: TRUNCATING {defect['filePathname']} TO {relpath}")
			defect["filePathname"] = relpath
		#FIXME
		if defect["filePathname"].startswith("build/"):
			print(ANSI_YELLOW+"CID: {} COVERITY BUG: Bogus Defect created from build directory, {} AUTO-DISMISS ".format(str(defect["cid"]), defect["filePathname"])+ANSI_OFF)
			cids_to_dismiss.add(defect["cid"])
			continue
		datestr = None
		commit = None
		email = None
		commit_location = None
		try:
			# Get the MD5 if the file as it is in the current index and see if it matches
			# the MD5 from the defect dict.
			hexdigest = md5(open(defect["filePathname"]).read().encode()).hexdigest()
#			if hexdigest != defect["contentsMD5"]:
#				continue
			try:
				cmd = __git("blame", "-l", "--show-email", "-L", str(defect["lineNumber"])+','+str(defect["lineNumber"]), defect["filePathname"], _tty_out=None).wait()
				output = cmd.stdout.decode().strip('\b\r\n')
				# NOTE: Different 'git blame' layouts exist depending on hosting site (e.g. TeamForge v. GitLab):
				# ca0054092b508 (<gmar@google.com> 2015-01-07 15:47:37 -0800 1605)        return err;
				# c1e888a600d9c (<kan.liang@linux.intel.com> 2020-02-06 08:15:27 -0800 1108)      addr = (resource_size_t)(mch_bar + TGL_UNCORE_MMIO_IMC_MEM_OFFSET * pmu->pmu_idx);
				# dc93a70cc7f92 drivers/media/video/v4l2-dev.c (<hverkuil@xs4all.nl> 2008-12-19 21:28:27 -0300 1024)    device_unregister(&vdev->dev);'
				match = re.search("^\^{0,1}([0-9abcdef]+) (?:\S+ ){0,1}\(<([^>]+)> ([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})", output)
				if match:
					commit = match.group(1)
					email = match.group(2)
					datestr = match.group(3)

#					print(f"COMMIT={commit} EMAIL={email} DATE={datestr}")
					# CHECK #1 - is the defect Intel-authored?
					if not re.search("@(?:linux\.){0,1}intel.com$", email):
						print("CID: {} File: {} Line: {}, {} NON-INTEL-AUTHORED: {}".format(str(defect["cid"]), defect["filePathname"], str(defect["lineNumber"]), defect["contentsMD5"], email))
						cids_to_dismiss.add(defect["cid"])
						continue

					# CHECK #2 - Is the defect already upstream ?
					commit_location = None
					try:
						commit_location = __git("describe", "--match", 'v[23456789].*' , commit).stdout.decode().strip()
						cmp0 = __gen_compare_string(commit_location)
						cmp1 = __gen_compare_string(baseline_tag)
						if cmp0 < cmp1:
							print("CID: {} File: {}, Line: {}, {} AUTHOR {} UPSTREAM AT {}".format(str(defect["cid"]), defect["filePathname"], str(defect["lineNumber"]), defect["contentsMD5"], email, commit_location))
							cids_to_dismiss.add(defect["cid"])
							continue
					except Exception as e:
							print('CID: {} WARNING: {}'.format(str(defect["cid"]), re.sub('\n', '', e.stderr.decode())))
							pass
				else:
					# Something went wrong in 'git blame'
					print("ERROR: no regex match for {}".format(output))
			except Exception as e:
				print('CID: {} WARNING: {}'.format(str(defect["cid"]), defect["filePathname"], "line", str(defect["lineNumber"]), re.sub('\n', '', e.stderr.decode())))
		except Exception as e:
			print('WARNING -------------------- CID', defect["cid"], defect["filePathname"] , 'Line', defect["lineNumber"], e.args, '--------------------' )


		# Check the kernel.org stable repo to see if the patch exists upstream
		with pushd(upstream_repo):
			# get all commits in upstream work tree that include this file
			cmd = __git("log", "--format=%H", "--", defect["filePathname"], _tty_out=None).wait()
			output = cmd.stdout.decode().strip('\b\r\n')
			revlist = output.split('\n')
			defect_found = False
			for commit in revlist:
				if not commit:  # skip empty strings
					continue
				# scan all commits for the offending line until it is found
				try:
					cmd = __git("blame", "-l", "--show-email", "-L", str(defect["lineNumber"])+','+str(defect["lineNumber"]), commit, "--", defect["filePathname"], _tty_out=None).wait()
					output = cmd.stdout.decode().strip('\b\r\n')
					match = re.search("^\^{0,1}([0-9abcdef]+) (?:\S+ ){0,1}\(<([^>]+)> ([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})", output)
					if match:
						commit = match.group(1)
						email = match.group(2)
						datestr = match.group(3)
						commit_location = __git("describe", "--match", 'v[23456789].*' , commit).stdout.decode().strip()
						print(ANSI_YELLOW+"CID: {} File: {}, Line: {}, {} AUTHOR {} UPSTREAM AT {}".format(str(defect["cid"]), defect["filePathname"], str(defect["lineNumber"]), defect["contentsMD5"], email, commit_location)+ANSI_OFF)
						cids_to_dismiss.add(defect["cid"])
						defect_found = True
						break
				except Exception as e:
					print('CID: {} WARNING: {}'.format(str(defect["cid"]), re.sub('\n', '', e.stderr.decode())), "at commit", commit)
					pass
			if defect_found:
				continue

		# CHECK #3 - If all other checks fail, and the defect patch is very old (e.g. 4+ years),
		# we assume it's already upstream somewhere...
		if datestr:
			timestamp = datetime.datetime.timestamp(datetime.datetime.strptime(datestr,"%Y-%m-%d %H:%M:%S"))
			now = time.time()
			if (now - timestamp) > 3600*24*365*4: # older than 4 years?
				print("CID: {} OLD PATCH: {}".format(str(defect["cid"]), datestr))
				cids_to_dismiss.add(defect["cid"])
				continue

		# CHECK #4 - a NON-old patch that can't be found in its current path in ANY repo
		if not email and not datestr and not commit and not commit_location:
			print(ANSI_YELLOW+"CID: {} File: {} Line: {} AUTHOR: {} DATE {} LOCATION {} Cannot be found in any staging or upstream location".format(str(defect["cid"]), defect["filePathname"], str(defect["lineNumber"])+ANSI_OFF, email,datestr,commit_location))
			cids_to_dismiss.add(defect["cid"])
			continue

		# Note the defect needs a closer look by COE or DM
		print(ANSI_RED+"CID: {} File: {} Line: {} AUTHOR: {} DATE {} LOCATION {} NEEDS TRIAGE".format(str(defect["cid"]), defect["filePathname"], str(defect["lineNumber"])+ANSI_OFF, email,datestr,commit_location))
		# Remove from set of CIDs to Dismiss, if it was previously placed there
		cids_to_triage.add(defect["cid"])

	# Dismiss CIDs that don't have an issue we need to triage
	if fix:
		print("\nDismissing CIDs Eligible for Dismissal...")
		for cid in cids_to_dismiss:
			if cid in cids_to_triage:
				print("CID: {} NEEDS TRIAGE".format(cid))
				continue
			else:
				__update_triage_for_cid( [ pkt_cov_config.TRIAGE_STORE, cid ] )
				print("CID: {} DISMISSED".format(cid))
	else:
		print ("Re-run this script with -f to dismiss eligible defects listed above.")

	return True

def __init_project_repos(project, stream, ref):

	global g_objProject

	g_objProject = CoverityProject.objects.get(cov_project = project)
	g_objProject.repo.initialize(scmdir=os.path.join(pkt_cov_config.REPO_BASE,g_objProject.repo.project), _verbose=True)
	g_objProject.config_repo.initialize(scmdir=os.path.join(pkt_cov_config.REPO_BASE,g_objProject.config_repo.project), _verbose=True)
	#FIXME - Handle these corner cases in the database somehow
	if 'iotg-next' in stream or 'bullpen' in ref:
		g_objProject.repo = Repository.objects.get(project = 'intel-innersource/os.linux.kernel.kernel-staging', repotype__repotype = 'src')
		g_objProject.repo.initialize(scmdir=os.path.join(pkt_cov_config.REPO_BASE,g_objProject.repo.project), _verbose=True)
	#FIXME


# Initilalize commands to no-op here
# Actually command values are set in customize_cov_config()
__cov_build = sh.Command('/bin/echo')
__cov_analyze = sh.Command('/bin/echo')
__cov_manage_emit = sh.Command('/bin/echo')
__cov_commit_defects = sh.Command('/bin/echo')
__cov_import_scm = sh.Command("/bin/echo")
__cov_configure = sh.Command("/bin/echo")
__cov_make_library = sh.Command("/bin/echo")

def customize_cov_config():
	# get coverity version from server.   
	versionDataObj = __get_version()
	if versionDataObj is None:
		__log.error("cannot get coverity server version.")
		cov_version = "unknown"
		sys.exit(1)	# No use continuing from here - fail the run
	else:
		cov_version = versionDataObj.externalVersion

	# construct the directory 
	pkt_cov_config.BUILD_DIR = os.path.join(pkt_cov_config.BASE_BUILD_DIR, cov_version)
	pkt_cov_config.CONFIG_FILE = os.path.join(pkt_cov_config.BASE_CONFIG_DIR, cov_version, "coverity_config.xml")
	pkt_cov_config.COV_IDIR = os.path.join(pkt_cov_config.BASE_COV_IDIR, cov_version)
	pkt_cov_config.BASELINE_IDIR = os.path.join(os.sep, "coverity", cov_version, "cov_idir_baseline")

	__log.info("coverity version: {}".format(cov_version))
	__log.info("build direcotry: {}".format(pkt_cov_config.BUILD_DIR))
	__log.info("config file: {}".format(pkt_cov_config.CONFIG_FILE))
	__log.info("coverity idir: {}".format(pkt_cov_config.COV_IDIR))
	__log.info("baseline idir: {}".format(pkt_cov_config.BASELINE_IDIR))

	# Create directory if necessary
	if not os.path.exists(pkt_cov_config.BASELINE_IDIR):
		__log.info("create {}".format(pkt_cov_config.BASELINE_IDIR))
		os.makedirs(pkt_cov_config.BASELINE_IDIR)

	cov_path = pkt_cov_config.COV_PATH_TEMPLATE.format(cov_version)

	global __cov_build
	global __cov_analyze
	global __cov_manage_emit
	global __cov_commit_defects
	global __cov_import_scm
	global __cov_configure
	global __cov_make_library

	if not __dry_run:
		__cov_build = sh.Command(os.path.join(cov_path,'cov-build'))
		__cov_analyze = sh.Command(os.path.join(cov_path,'cov-analyze'))
		__cov_manage_emit = sh.Command(os.path.join(cov_path,'cov-manage-emit'))
		__cov_commit_defects = sh.Command(os.path.join(cov_path,'cov-commit-defects'))
		__cov_import_scm = sh.Command(os.path.join(cov_path,"cov-import-scm"))
		__cov_configure = sh.Command(os.path.join(cov_path,"cov-configure"))
		__cov_make_library = sh.Command(os.path.join(cov_path,"cov-make-library"))

def __scan_baseline(argv):
	project = argv[0]
	stream = argv[1]
	ref = argv[2]
	arch = argv[3]

	global g_objProject

	__init_project_repos(project, stream, ref)

	__log.info ( "Stream %s REF %s", stream, ref)
	__setup_stream([ project, stream ])

	snapshots = __get_snapshots_for_stream([ stream ])
	for s in snapshots.keys():
		if snapshots[s] == ref:
			__log.info("Stream %s Baseline %s Already Scanned", stream, ref)
			return

	with pushd(g_objProject.repo.scmdir):
		__log.info("Creating BASELINE Scan for %s (%s)", stream, ref)
		try_shell_command(__git, [ "clean", "-xdf" , "--exclude="+pkt_cov_config.BASE_BUILD_DIR, "--exclude="+pkt_cov_config.BASE_CONFIG_DIR, "--exclude="+pkt_cov_config.BASE_COV_IDIR ])
		__reset_to_master_and_pull()
		try_shell_command(__git, [ "checkout", ref ] )
		config_ref, config_file = __get_cov_config_2(project, ref, arch)
		__log.info("Config File: "+config_file)
		__scan_build([ project, stream , ref , config_file ], arch = arch)
		__clear_upstream_defects([ stream ])
		__reset_to_master_and_pull()

if __name__ == '__main__':
	assert(os.path.exists(os.environ["WORKSPACE"]))
	assert(os.path.exists(pkt_cov_config.REPO_BASE))
	customize_cov_config()
	try:
		if len(sys.argv) > 2:
			ret = globals()[sys.argv[1]](sys.argv[2:])
		else:
			ret = globals()[sys.argv[1]]()
		if ret is not None:
			print(ret)
	except Exception as e:
		__log.error(traceback.format_exc())
		sys.exit(1)
	sys.exit(0)


