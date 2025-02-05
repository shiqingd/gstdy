#!/usr/bin/env python3
from django.db import models
from django.db.models import Q, CharField, TextField, ForeignKey, IntegerField, DateTimeField, BooleanField, OneToOneField
from django.contrib.postgres.fields.array import ArrayField
from argparse import ArgumentTypeError

import os
import sys
import sh
import re
import subprocess
import shutil
import ast
import json
from subprocess import PIPE
from lib.utils import log_run_cmd, cmd, cal_cpu_num, is_branch
from lib.dry_run import dryrunnable, traceable
from lib.pushd import pushd

_git = sh.Command("/usr/bin/git")

@dryrunnable()
def _dryrunnable_git(*args):
	_git(args)

@traceable()
def _traceable_git(*args):
	_git(args)

############################## FUNDAMENTAL MODELS ##############################

class ApplicationType(models.Model):
	name =  models.CharField(max_length=64, null=False, unique=True, blank=False)
	description = models.TextField()

	def __str__(self):
		return "ApplicationType {}".format(self.name)

	def __repr__(self):
		return str(self.__dict__)

class ArtifactPattern(models.Model):
	flat = BooleanField(default=True)
	pattern = models.CharField(max_length=256, null=False)

	def __str__(self):
		return "{} {} {}".format(self.__class__.__name__, self.flat, self.pattern)

	def __repr__(self):
		return str(self.__dict__)

class ArtifactTarget(models.Model):
	target = models.CharField(max_length=256, null=False)

	def __str__(self):
		return "{} {}".format(self.__class__.__name__, self.target)

	def __repr__(self):
		return str(self.__dict__)

class CredentialType(models.Model):
	type = models.CharField(max_length=32, null=False, blank=False)

	def __str__(self):
		return "CredentialType {}".format(self.type)

	def __repr__(self):
		return str(self.__dict__)

class JenkinsHost(models.Model):
	"""
	Hosts running a Jenkins instance

	:ivar name: Jenkins host name
	:vartype name: str
	:ivar url: URL of Jenkins host
	:vartype url: str
	:ivar jenkins_user: User name under which jobs run
	:vartype jenkins_user: str
	:ivar jenkins_token: Jenkins authentication token
	:vartype jenkins_token: str

	"""
	name = CharField(max_length=255)
	url = CharField(max_length=255)
	jenkins_user = CharField(max_length=255)
	jenkins_token = CharField(max_length=255)

	def __str__(self):
		return '{} --> {}'.format(self.name, self.url)

	def __repr__(self):
		return self.__str__()

class Kernel(models.Model):
	'''
	PKT DevOps Upstream Version Base Class

	A Kernel Object corresponds to a kernel version,
	and the upstream Repository it is sourced from.

	.. todo:: Define required methods
	'''
	name = CharField(max_length=255,unique=True)
	description = TextField()
	current_baseline = CharField(max_length=32)
	base_kernel = CharField(max_length=32)
	category = CharField(max_length=16, null=True, default=None)
	flags = IntegerField(default=0)
	alt_name = CharField(max_length=32)

	# flags bit values
	UNKNOWN_LEGACY_FLAG =      0x00000001
	PUSH_CONFIGS_FOR_STAGING = 0x00000002
	NO_CVE_PATCHES           = 0x00000004
	HAS_BULLPEN              = 0x00000008
	OBSOLETE_KERNEL          = 0x00000010
	ADD_CVE_PATCHES_TO_QUILT = 0x00000020
	BUILD_UBUNTU_OVERLAY     = 0x00010000
	BUILD_CENTOS_OVERLAY     = 0x00020000

	@classmethod
	def validate(cls, value):
		'''
		Check whether Kernel Type is valid (by name)
		'''
		try:
			query = cls.objects.get(name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value

	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all().order_by('name')
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files


		:returns: Readable String Representation of Object
		'''
		return "{} baseline".format(self.__class__.__name__, self.current_baseline)

	def __repr__(self):
		'''
		Serialized String Representation of Class,
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure


		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str(self.__dict__)

	def __del__(self):
		'''
		Class Destructor


		'''
		pass

class KTemplate(models.Model):
	template = models.CharField(max_length=1023, unique=True, null=False)

	class Meta:
		verbose_name = "Kernel Template"

	def __str__(self):
		return "{} ID {}: {}".format(self.__class__.__name__, str(self.id), self.template)

	def __repr__(self):
		return str(self.__dict__)


class Platform(models.Model):
	'''
	PKT Supported Platform (CPU Architechture or SoC) Base Class(es)

	.. todo:: Define required methods / attributes

	'''
	architecture = CharField(max_length=255)
	name = CharField(max_length=255,unique=True)
	description = TextField()
	config_file = CharField(max_length=255)
	flags = IntegerField(default=1)

	class Meta:
		db_table = 'framework_cpu'
		verbose_name = "CPU (Platform)"
		verbose_name_plural = "CPUs (Platforms)"

	@classmethod
	def validate(cls, value):
		'''
		Check whether Platform Type is valid (by name)
		This method is primarily used for argument parsing

		:param value: The value to test
		:type param: str
		:returns: True or False
		:rtype: boolean
		'''
		try:
			query = cls.objects.get(name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value

	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files


		:returns: Readable String Representation of Object
		'''
		return self.__class__.__name__ + ": " + self.description

	def __repr__(self):
		'''
		Serialized String Representation of Class,
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure


		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str(self.__dict__)

	def __del__(self):
		'''
		Class Destructor


		'''
		pass

class RegExp(models.Model):
	"""
	A Regular expression used somewhere in DevOps processing

	:ivar name: symbolic name of regular expression
	:vartype name: str
	:ivar description: description of where the regulare expression is used
	:vartype description: str
	:ivar pattern: Regular expression in Python syntax
	:vartype pattern: str
	"""
	name = CharField(max_length=255, default='---')
	description = CharField(max_length=255)
	pattern = CharField(max_length=255, unique=True)

	def __str__(self):
		return '{} : {}'.format(self.name, self.pattern)

	def __repr__(self):
		return str({ "name" : self.name, "description" : self.description , "pattern" : self.pattern })

class Release(models.Model):
	'''
	PKT DevOps Release Class

	A Release object contains many of the same
	attributes as a Build Object (Repo, Branch, Target)
	along with possibly Reporting and CI data.

	.. todo:: Define required methods / attributes

	:ivar name: Name of Release
	:vartype name: str

	'''
	name = CharField(max_length=64, unique=True)

	@classmethod
	def validate(cls, value):
		'''
		Check whether Release Type is valid (by name)
		'''
		try:
			query = cls.objects.get(name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value
	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files

		:returns: Readable String Representation of Object
		:rtype: str
		'''
		return self.name and self.name or "<no name>"

	def __repr__(self):
		'''
		Serialized String Representation of Object
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure

		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "name" : self.name })

	def __del__(self):
		'''
		Class Destructor

		'''
		pass

class RepoType(models.Model):
	'''
	PKT Repository Type

	A RepoType object represents a category of Repository that
	requires a specific type of handling

	.. todo:: Define required methods / attributes
	'''
	repotype = CharField(max_length=16, null=True)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files

		:returns: Readable String Representation of Object
		'''
		return self.repotype

	def __repr__(self):
		'''
		Serialized String Representation of Object
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure

		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "repotype" : self.repotype })

class Repository(models.Model):
	'''
	PKT Repository Base Class

	A Repository object represents a SCM store,
	in our case, a Git repository.

	.. todo:: Define required methods
	'''

	protocol = CharField(max_length=16, null=True)
	host = CharField(max_length=255, null=True)
	project = CharField(max_length=255, null=True)
	repotype = ForeignKey(RepoType, on_delete=models.CASCADE)
	external = BooleanField(default=False)
	ext_project_id = IntegerField(null=True) # Gitlab / GitHub / whatever....
	ext_group_id = IntegerField(null=True) # Gitlab / GitHub / whatever....
	flags = IntegerField(default=0)	# Bit Field

	# flags bit values
	NO_MIRROR_TAGS = 0x00000001

	def default_branch(self):

		import requests
		from framework.models import Application, Credential

		cred = Credential.objects.get(username = 'sys-oak', app__name = 'github_api')
		headers = {
			'Authorization' : 'token '+cred.credential,
			'Accept' : 'application/vnd.github.v3-preview+json'
		}
		resp = requests.get('https://api.github.com/repos/'+self.project, headers=headers, proxies= { 'https' : os.environ["HTTPS_PROXY"] })
		j = json.loads(resp.text)
		if not "default_branch" in j:
			return "master"
		return j["default_branch"]

	def initialize(self, scmdir=None, branch='master', _verbose=False):
		''' Clone and/or update given repo.

		:param scm: ???
		:param scmdir: ???
		:param branch: ???
		:returns: None
		'''
		scm = self.protocol + "://" + self.host + "/" + self.project
		self.scmdir = scmdir
		if self.scmdir == None:
			self.scmdir = os.path.join(os.getcwd(), self.project)
		if _verbose:
			print ("scm ", scm)
		if _verbose:
			print ("scmdir ", self.scmdir)

		if not os.path.exists(self.scmdir):
			os.makedirs(self.scmdir, exist_ok = True)

		if not os.path.exists(os.path.join(self.scmdir, '.git')):
			try:
				_traceable_git("clone", scm, scmdir)
			except Exception as e:
				if _verbose:
					print ("Unable to clone ", scm, "to", scmdir, ":", e.args[0].strip().split('\n')[-1])
				pass
		with pushd(scmdir, _verbose=True):
			remotes = _git.remote().strip()
			remotes = re.split(r"[\s]+", remotes)
			if _verbose:
				print ("remotes:", remotes)
			for r in remotes:
				_traceable_git("remote", "prune", r)
			try:
				_traceable_git("fetch", "--all", "--tags", "--force")
			except Exception as e:
				# To ignore duplicate tags
				print(e, file=sys.stderr)
				pass
			_traceable_git("reset", "--hard")
			try:
				_traceable_git("checkout", "origin/"+branch, "-b", branch)
			except Exception:
				_traceable_git("checkout", self.default_branch())
		return _git

	def git_remote_add_and_fetch(self, remote):
		''' add a remote and fetch

		:param remote: ???
		:param remote_scm: ???
		:returns: None
		'''
		remote_scm = self.protocol + "://" + self.host + "/" + self.project
		try:
			# Check if remote already exists
			remotes = _git.remote().strip()
			if not remote in remotes:
				_traceable_git("remote", "add", remote, remote_scm )
				_traceable_git("fetch", "remote", "--tags", "--force")
		except sh.ErrorReturnCode:
			pass

	def current_branch(self):
		return _git("rev-parse", "--abbrev-ref", "HEAD")

	@classmethod
	def list(cls):
		'''
		List all repo entries
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files

		:returns: Readable String Representation of Object
		'''
		return str(self.protocol) + "://" + str(self.host) + '/' + str(self.project)

	def __repr__(self):
		'''
		Serialized String Representation of Object
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure

		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "protocol" : self.protocol,
			 "host" : self.host,
			 "project" : self.project,
			 "repotype" : self.repotype })

	def url(self):
		'''
		Returns full URL for the repository
		Suitable for commands like 'git clone'

		:returns: full URL for the repository
		:rtype: str
		'''

		return str(self.protocol) + "://" + str(self.host) + '/' + str(self.project)

	def __del__(self):
		'''
		Class Destructor

		'''
		pass

class Subdomain(models.Model):

	"""
	Subsets of Domain objects

	:ivar name: - sub-domain name
	:vartype label: str
	:ivar description - optional description - useful as Web tooltip
	:vartype description: str
	:ivar domain - domain that this subdomain applies to
	:vartype description: Domain
	:ivar last_updated - date / time this record was created / updated
	:vartype description: date

	"""
	name = models.CharField(max_length=64, null=False, blank=False)
	description = models.CharField(max_length=255)
	last_updated = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ( 'name', 'domain' )

	@classmethod
	def validate(cls, value):
		'''
		Check whether Type Value is valid (by name)
		'''
		try:
			query = cls.objects.get(name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value

	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		return "Subdomain {}".format(self.name)

	def __repr__(self):
		return str(self.__dict__)

class User(models.Model):
	'''
	PKT DevOps User

	A User object is comprised of the ordered tuple of
	(IDSID, full name, email) plus other TBD attributes.

	'''
	idsid = CharField(max_length=255, unique=True)
	firstname = CharField(max_length=255)
	lastname = CharField(max_length=255)
	email = CharField(max_length=255)
	ldap_domain = CharField(max_length=8)

	@classmethod
	def validate(cls, value):
		'''
		Check whether Object Type is valid (by idsid)
		'''
		try:
			query = cls.objects.get(idsid = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s %s" % (cls.__name__ , value ) )
		return value

	@classmethod
	def list(cls):
		'''
		Return a list of valid entries (by idsid)
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.idsid)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files

		:returns: Readable String Representation of Object
		:rtype: str
		'''
		return (self.idsid and self.idsid or "<no name>") + " " + self.email

	def __repr__(self):
		'''
		Serialized String Representation of Object
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure

		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "idsid" : self.idsid ,
			"firstname" : self.firstname,
			"lastname" : self.lastname,
			"email" : self.email,
			"ldap_domain" : self.ldap_domain } )
		pass

############################## CORE MODELS ##############################

class Application(models.Model):
	name =  models.CharField(max_length=64, null=False, unique=True, blank=False)
	apptype = models.ForeignKey(ApplicationType, on_delete=models.CASCADE)
	url = models.TextField()

	def __str__(self):
		return "{} {}".format(self.__class__.__name__,self.name)

	def __repr__(self):
		return str(self.__dict__)

class BranchTemplate(models.Model):
	"""
	A set of branch templates used in remote repositories

	:ivar name: reference name of templase
	:vartype name: str
	:ivar kernel: Kernel object this template  applies to
	:vartype kernel: Kernel
	:ivar template: branch template
	:vartype template: str

	"""
	name = CharField(max_length=64)
	kernel = ForeignKey(Kernel, null=True, default=None, on_delete=models.CASCADE)
	release = ForeignKey(Release, null=True, default=None, on_delete=models.CASCADE)
	template = ForeignKey(KTemplate, on_delete=models.PROTECT)

	class Meta:
		unique_together = ( 'name', 'kernel', 'release' )

	def __str__(self):
		return self.kernel.name + '(' + self.name + ')' + ' --> ' + self.template.template

	def __repr__(self):
		return str ( { 'name' : self.name, 'kernel' : self.kernel.name, "release" : self.release, "template" : self.template  } )

class CoverityProject(models.Model):
	repo = models.ForeignKey(Repository, related_name='repo', null=False, on_delete=models.CASCADE)
	config_repo = models.ForeignKey(Repository, related_name='config_repo', null=False, on_delete=models.CASCADE)
	cov_project =  models.CharField(max_length=128, null=False)

	def __str__(self):
		return "CoverityProject {}".format(self.cov_project)

	def __repr__(self):
		return str(self.__dict__)

class Credential(models.Model):
	app = models.ForeignKey(Application, on_delete=models.CASCADE)
	username = models.CharField(max_length=64, null=False, blank=False)
	credential = models.TextField(null=False)
	credential_type = models.ForeignKey(CredentialType, on_delete=models.CASCADE)

	class Meta:
		unique_together = ( 'app', 'username' )

	def __str__(self):
		return "Credential : user {} app {}".format(self.username, self.app)

	def __repr__(self):
		return str(self.__dict__)

class Domain(models.Model):
	'''
	PKT Domain Base Class

	Domain objects refer to one of the many Domains withing
	the Prodction Kernel system.

	.. todo:: Define required methods / attributes

	'''
	name = CharField(max_length=64, unique=True)
	rfu_0 = IntegerField(null=True,default=None) #FIXME rename to 'flags'
	label_name = CharField(max_length=8, unique=True)
	kernels = models.ManyToManyField(Kernel, db_table="framework_domainkernel")
	subdomains = models.ManyToManyField(Subdomain, db_table="framework_domain_subdomain")

	@classmethod
	def validate(cls, value):
		'''
		Check whether Type Value is valid (by name)
		'''
		try:
			query = cls.objects.get(label_name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value

	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all().order_by('label_name')
		for row in query:
			result.append(row.label_name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files


		:returns: Readable String Representation of Object
		'''
		return self.name and self.name or "<no name>"

	def __repr__(self):
		'''
		Serialized String Representation of Class,
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure


		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "label" : self.label_name, "name" : self.name })

	def __del__(self):
		'''
		Class Destructor


		'''
		pass

class DomainOwner(models.Model):
	'''
	PKT DomainOwner Base Class

	Maps Domains to their respective owners
	the Prodction Kernel system.

	.. todo:: Define required methods / attributes

	'''
	idsid = models.CharField(max_length=16, null=True, blank=True)
	domain = models.ForeignKey(Domain, null=True, on_delete=models.CASCADE)
	prim = models.BooleanField(default=False)
	notify = models.BooleanField(default=True)
	last_updated = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.domain.name + ', ' + self.idsid

class JenkinsJob(models.Model):
	"""
	Jenkins jobs running on a Jenkins host

	:ivar host: JenkinsHost object
	:vartype name: JenkinsHost
	:ivar kernel: Kernel object this job applies to
	:vartype kernel:  Kernel
	:ivar jobname: job name
	:vartype jobname: str
	:ivar job_params: pickled list of job parameters
	:vartype job_params: str
	:ivar flags: integer bit-field used for miscellaneous checks
	:vartype flags: int

	"""

	host = ForeignKey(JenkinsHost, on_delete=models.CASCADE)
	kernel = ForeignKey(Kernel, on_delete=models.CASCADE)
	jobname = CharField(max_length=255)
	job_params = CharField(max_length=255)
	flags = IntegerField(default=0)

	def __str__(self):
		return '{} --> {} {}'.format(self.host.name, self.kernel.name, self.jobname)

	def url(self):
		return "%s/job/%s" % (self.host.url, self.jobname)

	def __repr__(self):
		return self.__str__()

class KernelRelease(models.Model):
	"""
	Table of Kernel objects associated with Release objects

	:ivar kernel: Kernel object this mapping applies to
	:vartype kernel: Kernel
	:ivar release: Release object this mapping applies to
	:vartype kernel: Release

	"""
	release = ForeignKey(Release, on_delete=models.CASCADE)
	kernel = ForeignKey(Kernel, on_delete=models.CASCADE)
	flags = IntegerField(default=0) # Bit Field
	cve_xform = ForeignKey(Release, db_column='cve_xform', null=True, blank=True, on_delete=models.SET_NULL)

	class Meta:
		unique_together = ( 'release', 'kernel' )

	def __str__(self):
		return '({} , {})'.format(self.kernel.name, self.release.name)

	def __repr__(self):
		return str({ "kernel" : self.kernel, "release" : self.release })

class KernelRepoSet(models.Model):
	"""
	A Table of Repository objects associated with Kernel objects

	:ivar kernel: Kernel object this mapping applies to
	:vartype kernel: Kernel
	:ivar repo: Repository object this mapping applies to
	:vartype kernel: Repository

	"""
	kernel = ForeignKey(Kernel, on_delete=models.CASCADE)
	repo = ForeignKey(Repository, on_delete=models.CASCADE)
	class Meta:
		unique_together = ('kernel', 'repo')

	def init_kernels(self):
		'''
		Clone the projects needed for this kernel.
		Do a git-fetch for both remotes.
		'''
		try:
			self.repo.initialize(os.path.join(os.environ["WORKSPACE"], self.repo.project), "master")
		except sh.ErrorReturnCode:
			die("Unable to update kernel-bkc")

	def __str__(self):
		return '{} : {}'.format(self.kernel.name, str(self.repo))

	def __repr__(self):
		return str({ "kernel": self.kernel, "repo" : str(self.repo) })

class TagTemplate(models.Model):
	"""
	A set of release tag creation templates

	:ivar kernel: Kernel object this template  applies to
	:vartype kernel: Kernel
	:ivar template: tag template
	:vartype template: str

	"""
	kernel = OneToOneField(Kernel, on_delete=models.CASCADE)
	template = ForeignKey(KTemplate, on_delete=models.PROTECT)

	def __str__(self):
		return '{} --> {}'.format(self.kernel.name, self.template)


	def __repr__(self):
		return str( { "kernel" : self.kernel.name, 
			"template" : self.template } )

class TrackerBranch(models.Model):
	"""
	COE TrackerBranches
	"""
	branch = CharField(max_length=255)
	kernel = ForeignKey(Kernel, on_delete=models.CASCADE)
	repo = ForeignKey(Repository, on_delete=models.CASCADE)
	domain = ForeignKey(Domain, on_delete=models.CASCADE)

	def __str__(self):
		return '{} --> {} {} {}'.format(self.kernel.name, self.branch, str(self.repo), self.domain)

	def get_tracker_branch(self):
		return "tracker/"+branch

############################## TASK MODELS ############################## 

class Artifacts(models.Model):
	job = ForeignKey(JenkinsJob, null=True, on_delete=models.CASCADE)
	kernel = ForeignKey(Kernel, on_delete=models.CASCADE)
	platform = ForeignKey(Platform, on_delete=models.CASCADE)
	target = ForeignKey(ArtifactTarget, on_delete=models.CASCADE)
	patterns = models.ManyToManyField(ArtifactPattern, db_table='framework_artifacts_patterns')

	def __str__(self):
		return "{} {} {} {}".format(self.__class__.__name__, self.job, self.kernel, self.platform)

	def __repr__(self):
		return str(self.__dict__)

class PathToDomain(models.Model):
	pattern = models.CharField(max_length=128, null=False, blank=False)
	domain = models.ForeignKey(Domain, on_delete=models.CASCADE)

	def __str__(self):
		return self.pattern + ' ==> ' + self.domain.name

class Remote(models.Model):
	"""
	A Set of remote repositories used for a particular kernel release

	:ivar remote_name: name of remote to create during release process
	:vartype remote_name: str
	:ivar kernelrelease: KernelRelease object
	:vartype kernelrelease: KernelRelease
	:ivar remote_repo:	Repository of remote to push to
	:vartype local_repo: Repository of staging branch/tag to push
	:ivar dst_repo: Destinaton repository of remote
	:vartype dst_repo: Repository
	:ivar remote_branch: Remote branch to push to
	:vartype remote_branch: str
	:ivar push_method: Python function to carry out push
	:vartype push_method: str
	:ivar force_push: Flag to perform force-push
	:vartype force_push: boolean

	"""
	remote_name = CharField(max_length=255)
	kernelrelease = ForeignKey(KernelRelease, on_delete=models.CASCADE)
	remote_repo = ForeignKey(Repository, related_name='remote_repo', on_delete=models.CASCADE)
	local_repo = ForeignKey(Repository, related_name='local_repo', on_delete=models.CASCADE)
	staging_template = ForeignKey(BranchTemplate, related_name='staging_tmpl', null=True, on_delete=models.SET_NULL)
	push_template = ForeignKey(BranchTemplate, related_name='push_tmpl', null=True, on_delete=models.SET_NULL)
	push_method = CharField(max_length=255)
	force_push  = BooleanField(default = False)

	def __str__(self):
		return "Remote: {} [{} --> {}] {}({}, {} force_push={})".format(
		self.kernelrelease, self.local_repo.project, self.remote_repo.project,self.push_method,
		self.remote_name, self.push_template and self.push_template.template or '<NO TEMPLATE>', self.force_push)

	def __repr__(self):
		return str({ "remote_name" : self.remote_name,
			"kernelrelease" : self.kernelrelease,
			"remote_repo" : self.remote_repo,
			"local_repo" : self.local_repo,
			"staging_template" : self.staging_template,
			"push_template" : self.push_template,
			"push_method" : self.push_method,
			"force_push" : self.force_push})

class ScmTrigger(models.Model):
	pattern =  models.CharField(max_length=255)
	_type =  models.CharField(max_length=64, null=False)
	preprocess = models.CharField(max_length=255)
	postprocess = models.CharField(max_length=255)
	repo = models.ForeignKey(Repository, related_name='repo', null=False, on_delete=models.CASCADE)
	last_updated = models.DateTimeField(auto_now=True)

	def __str__(self):
		return "ScmTrigger {}".format(self.pattern)

	def __repr__(self):
		return str(self.__dict__)

class ScmEvent(models.Model):
	repo = models.ForeignKey(Repository, related_name='repo', null=False, on_delete=models.CASCADE)
	event = models.CharField(max_length=9, null=False)
	action = models.CharField(max_length=64, null=False)
	ref = models.CharField(max_length=128, null=False)
	remote_ref = models.CharField(max_length=128, null=False)
	date = models.DateTimeField(auto_now=True)
	processed = BooleanField(default=False)

	def __str__(self):
		return "ScmEvent {} {} {}".format(self.event, self.ref, self.repo.project)

	def __repr__(self):
		return str(self.__dict__)


class YoctoBSP(models.Model):

	name = CharField(max_length=255,unique=True)
	bsp_repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
	bsp_rev_prefix = models.CharField(max_length=255, null=False, blank=False)
	init_opt = models.CharField(max_length=255, null=False, blank=False)
	sync_opt = models.CharField(max_length=255, null=False, blank=False)
	kernel_pp = models.CharField(max_length=255, null=False, blank=False)
	meta_dir = models.CharField(max_length=255, null=False, blank=False)
	conf_dir =  models.CharField(max_length=255, null=False, blank=False)
	mc_conf_dir =  models.CharField(max_length=255, null=False, blank=False)
	lcfg_fl =  models.CharField(max_length=255, null=False, blank=False)
	ccfg_fl =  models.CharField(max_length=255, null=False, blank=False)
	dcfg_fl =  models.CharField(max_length=255, null=False, blank=False)
	mcfg_fl =  models.CharField(max_length=255, null=False, blank=False)
	target_prefix =  models.CharField(max_length=255, null=False, blank=False)
	image_target =  models.CharField(max_length=255, null=False, blank=False)
	mini_target_prefix = models.CharField(max_length=255, null=False, blank=False)
	mini_image_target = models.CharField(max_length=255, null=False, blank=False)
	kernel_target =  models.CharField(max_length=255, null=False, blank=False)
	image_dir =  models.CharField(max_length=255, null=False, blank=False)
	image_name =  models.CharField(max_length=255, null=False, blank=False)
	log_dir =  models.CharField(max_length=255, null=False, blank=False)
	log_name =  models.CharField(max_length=255, null=False, blank=False)
	kernel_uri_var =  models.CharField(max_length=255, null=False, blank=False)
	emptied_files =  models.CharField(max_length=255, null=False, blank=False)
	compress_image = BooleanField(default=True)
	lfs_projects =  models.CharField(max_length=1024, null=False, blank=False)

	def __str__(self):
		return "YoctoBSP {}".format(self.name)

	def __repr__(self):
		return str(self.__dict__)


class YoctoBuild(models.Model):

	kernel = models.ForeignKey(Kernel, on_delete=models.CASCADE)
	platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
	kernel_repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
	bsp = models.ForeignKey(YoctoBSP, on_delete=models.CASCADE)
	lic_chksum =  models.CharField(max_length=255)
	kernel_cmd =  models.CharField(max_length=255)
	bsp_confs = models.CharField(max_length=1024)
	bsp_patches = models.CharField(max_length=1024)
	bspcfg_post_lines = models.CharField(max_length=255)

	class Meta:
		unique_together = ( 'kernel', 'platform' )

	def __str__(self):
		return "YoctoBuild {},{}".format(self.kernel.name, self.platform.name)

	def __repr__(self):
		return str(self.__dict__)

	def add_cmdline_args(self, args):
		# variables defined in config file or database
		# the files that need to be cleaned up before build

		# variables passed from cmdline or build env.
		self.workspace = os.environ["WORKSPACE"]
		self.yocto_release = args.yocto_release
		self.staging_number = args.staging_number
		# add revision prefix(like refs/tags/) if necessary
		print('<'+self.bsp.bsp_rev_prefix+'>')
		if self.bsp.bsp_rev_prefix and not args.yocto_release.startswith(r'refs/'):
			self.yocto_release = self.bsp.bsp_rev_prefix + self.yocto_release
		self.job_num = cal_cpu_num()
		self.repo_mirror = args.repo_mirror
		self.dl_dir = args.dl_dir
		self.sstate_dir = args.sstate_dir
		if args.confs:
			self.confs = ast.literal_eval(args.confs)
		else:
			self.confs = []
		self.log_verbose = args.log_verbose
		if args.repo_cmd:
			self.repo_cmd = args.repo_cmd
		else:
			self.repo_cmd = os.path.join(os.environ["HOME"],'bin','repo.google')

		# variables updated/defined here
		self.image_path = os.path.join(self.bsp.image_dir, self.bsp.image_name)
		self.log_path = os.path.join(self.bsp.log_dir, self.bsp.log_name)
		self.build_dirname = 'yocto_build'
		self.build_branch = "%s_temp" % (self.build_dirname)
		self.build_top_dir = os.path.join(self.workspace, self.build_dirname)
		if self.repo_mirror:
			self.bsp.init_opt += " --reference %s" % self.repo_mirror
		self.build_opt = '-v' if self.log_verbose else ''
		self.confs.append(('BB_NUMBER_THREADS', self.job_num))
		self.local_confs = []
		if self.dl_dir:
			self.confs.append(('DL_DIR' , self.dl_dir ))
			self.local_confs.append(( 'DL_DIR', self.dl_dir ))
		if self.sstate_dir:
			self.confs.append( ('SSTATE_DIR' , self.sstate_dir ))
			self.local_confs.append( ( 'SSTATE_DIR', self.sstate_dir ))
		if self.lic_chksum:
			self.confs.append((
				"LIC_FILES_CHKSUM:pn-%s" % self.bsp.kernel_pp,
				"file://COPYING;md5=%s" % self.lic_chksum))

		if self.bsp_confs:
			bc = ast.literal_eval(self.bsp_confs)
			assert(type(bc) is tuple)
			self.confs.extend(bc)
		self.unset_confs = []

		self.is_branch = is_branch(self.kernel_repo.url().replace('git://', 'https://'),
					self.staging_number)

	def get_image_path(self):
		return os.path.join(self.build_dirname, self.image_path + '.bz2')

	def prepare_repo(self, sync_repo=True, exit_on_fail=True):
		if self.bsp_patches:
			patch_list = ast.literal_eval(self.bsp_patches)
			assert(type(patch_list) is tuple)
			bsp_patch_cmds = [ "\
			{repo} forall -vp {metaprj} -c git am {patch}".format(
			repo=self.repo_cmd,
			metaprj=p[0],
			patch=os.path.join(self.workspace, p[1])) \
				for p in patch_list ]
			bsp_patch_cmds = '\n'.join(bsp_patch_cmds)
		else:
			bsp_patch_cmds = ''

		# expand full path for those which use the local manifest snapshots
		init_opt = self.bsp.init_opt.replace(r'%%WORKSPACE%%', self.workspace)

		commands = r"""
			set -x

			{repo} abandon {build_branch}
			# remove previous build folder at the end of job
			test -d build && mv build build.pre.$(date '+%m%d%H%M%S')
			{repo} forall -pc 'git am --abort 2>/dev/null; \
							git rebase --abort 2>/dev/null; \
							git reset --hard ; \
							git clean -ffdx'
			{repo} init -u {repo_url} -b {yocto_rel_tag} {init_opt}
			cp .repo/repo/repo {repo} || :
			{repo} sync -c -j{job_num} {sync_opt}
			{repo} start {build_branch} --all
			{repo} forall -vp {lfs_projects} -c git lfs pull
			# apply extra bsp patch(es) if necessary
{bsppatchcmds}
				""".format(repo=self.repo_cmd,
							build_branch=self.build_branch,
							repo_url=self.bsp.bsp_repo.url(),
							yocto_rel_tag=self.yocto_release,
							init_opt=init_opt,
							job_num=self.job_num,
							sync_opt=self.bsp.sync_opt,
							lfs_projects=self.bsp.lfs_projects \
											if self.bsp.lfs_projects else '',
							bsppatchcmds=bsp_patch_cmds)

		cmd(commands, exit_on_fail=exit_on_fail)

		# clean up the files before starting the build
		# e.g. the kernel patches list
		if self.bsp.emptied_files:
			for f in json.loads(self.bsp.emptied_files):
				with open(f, 'w'): pass


	@staticmethod
	def _set_configs(cfg_fl, settings):
		if not settings:
			return

		# set conf variables in build/conf/local.conf
		# any variable set in local.conf overrides the one set elsewhere unless
		# that variable is hard-coded(e.g. by using '=' instead of '?=')

		# compose the re pattern to remove the old settings if exist
		re_ptn = r"^\s*(%s)\s*\??=.*$\n" % '|'.join([ c[0] for c in settings ])
		# compose lines of new settings
		new_cfg = '\n'.join([ "%s = \"%s\"" % (k, str(v)) \
								for (k, v) in settings ])
		new_cfg = "# Added by kernel script\n%s\n" % new_cfg 
		if os.path.isfile(cfg_fl) and os.path.getsize(cfg_fl) > 0:
			with open(cfg_fl, 'r+') as cf:
				cfg_text = cf.read()
				# remove the original settings
				cfg_text = re.sub(re_ptn, '', cfg_text, flags=re.M)
				# append new settings
				cfg_text += new_cfg
				# overwrite the conf file
				cf.seek(0)
				cf.write(cfg_text)
				cf.truncate()
		else:
			with open(cfg_fl, 'w') as cf:
				cf.write(new_cfg)


	def set_kernel_uri(self):
		# set kernel repo url and staging revision(branch or tag)
		srcrev_var = "SRCREV_machine:pn-%s" % self.bsp.kernel_pp
		kuri_var = "%s:pn-%s" % (self.bsp.kernel_uri_var, self.bsp.kernel_pp)
		if self.is_branch:
			# if revision is a branch
			self.confs.append((
				kuri_var,
				"%s;branch=%s;name=machine;protocol=ssh" % \
				(self.kernel_repo.url(), self.staging_number)))
			self.confs.append((srcrev_var, r'${AUTOREV}'))
		else:
			# if revision is a tag
			self.confs.append((
				kuri_var,
				"%s;nobranch=1;name=machine;protocol=https" % \
				self.kernel_repo.url().replace('https://', 'git://')))
			self.confs.append((srcrev_var, self.staging_number))

		self.confs.append(("KBRANCH:pn-%s" % self.bsp.kernel_pp,
						r'${%s}' % srcrev_var))


	def set_kernel_conf(self):
		# set build/conf/multiconfig/x86.conf
		#   PREFERRED_PROVIDER_virtual/kernel = "{kernel_pp}"
		#   KERNEL_SRC_URI:pn-{kernel_pp} = "{kernel_repo_url};nobranch=1;name=machine;protocol=ssh"
		#   SRCREV_machine:pn-{kernel_pp} = "{kernel_revision}"
		#   KERNEL_PACKAGE_NAME:pn-{kernel_pp} = "kernel"
		#   KERNEL_PROVIDERS_EXTRA_MODULES = ""
		#   KERNEL_PROVIDERS_EXTRA_MODULES_forcevariable = ""
		self.confs.append((
			'PREFERRED_PROVIDER_virtual/kernel', self.bsp.kernel_pp))
		# set kernel repo url and staging revision(branch or tag)
		self.set_kernel_uri()

		if not self.is_branch:
			self.confs.append(("LINUX_VERSION_EXTENSION:pn-%s" % self.bsp.kernel_pp , self.staging_number.replace('-preempt-rt', '').replace('sandbox-', ''),))


		self.confs.append((
			"KERNEL_PACKAGE_NAME:pn-%s" % self.bsp.kernel_pp, 'kernel'))
		#self.confs.append((
		#	"LINUX_KERNEL_TYPE:pn-%s" % self.bsp.kernel_pp,
		#	self.bsp.kernel_pp.split('-')[-1]))
		self.confs.append(('KERNEL_VERSION_SANITY_SKIP', '1'))
		# add unset variables
		self.unset_confs.append('KERNEL_PROVIDERS_EXTRA_MODULES')
		self.unset_confs.append('KERNEL_PROVIDERS_EXTRA_MODULES_forcevariable')


	def set_confs(self):
		conf_dir = self.bsp.mc_conf_dir or self.bsp.conf_dir

		#if self.bsp.dcfg_fl != self.bsp.ccfg_fl:
		#	def_cfg = os.path.join(self.build_top_dir, conf_dir, self.bsp.dcfg_fl)
		#	# change SELECTABLE_KERNEL_DEFAULT to customized config file
		#	with open(def_cfg, 'r+') as cf:
		#		cfg_text = cf.read()
		#		cfg_text = re.sub(
		#			r'^\s*SELECTABLE_KERNEL_DEFAULT\s*.?=.*$',
		#			'SELECTABLE_KERNEL_DEFAULT = "%s"' % self.bsp.ccfg_fl,
		#			cfg_text,
		#			flags=re.M)
		#		# overwrite the conf file
		#		cf.seek(0)
		#		cf.write(cfg_text)
		#		cf.truncate()

		# include customized conf file in the default conf file
		for dcf in (self.bsp.dcfg_fl, self.bsp.mcfg_fl,):
			if dcf and dcf != self.bsp.ccfg_fl:
				dcf_path = os.path.join(self.build_top_dir, conf_dir, dcf)
				with open(dcf_path, 'a') as cf:
					cf.write("\n# Added by Kernel script\ninclude ./%s\n" % \
							self.bsp.ccfg_fl)

		# unique variables in confs:
		# 1. if a variable is defined twice, the later overwrites the former
		# 2. the sequence of the variable depends on its first occurrence
		ckeys = []
		cdict = {}
		for (k, v) in self.confs:
			if k not in cdict:
				ckeys.append(k)
			cdict[k] = v
		confs = [ (k, cdict[k]) for k in ckeys ]
		# put all conf settings in the customized conf file
		cstm_cfg = os.path.join(self.build_top_dir, conf_dir, self.bsp.ccfg_fl)
		YoctoBuild._set_configs(cstm_cfg, confs)
		# add APPEND += <kernel_cmd> and unset variables in customized conf file
		cfg_txt = ""
		if self.kernel_cmd:
			cfg_txt += "APPEND += \"%s\"\n" % self.kernel_cmd
		if self.bspcfg_post_lines:
			cfg_txt += "%s\n" % '\n'.join(json.loads(self.bspcfg_post_lines))
		if self.unset_confs:
			cfg_txt += '\n'.join([ "unset %s" % c for c in self.unset_confs ])
			cfg_txt += '\n'
		if cfg_txt:
			with open(cstm_cfg, 'a') as cf:
				cf.write(cfg_txt)

		# add SSTATE_DIR, DL_DIR in conf/local.conf anyway
		if self.bsp.lcfg_fl != self.bsp.ccfg_fl:
			loc_cfg = os.path.join(
				self.build_top_dir, self.bsp.conf_dir, self.bsp.lcfg_fl)
			YoctoBuild._set_configs(loc_cfg, self.local_confs)

	def build(self, exit_on_fail=True):
		commands = r"""
			set -x
			cd build
			source ../{meta_dir}/oe-init-build-env .
			# just clean kernel's output and sstate so that:
			#   1. kernel's do_fetch can be triggered
			#   2. the rest of sstate cache can be reused
			bitbake -c do_cleanall {target_prefix}{kernel_target}
			source ../{meta_dir}/oe-init-build-env .
			bitbake {build_opt} {target_prefix}{image_target}
			test -f ../{img_path}
					""".format(meta_dir=self.bsp.meta_dir,
							target_prefix=self.bsp.target_prefix,
							kernel_target=self.bsp.kernel_target,
							build_opt=self.build_opt,
							image_target=self.bsp.image_target,
							mini_target_prefix=self.bsp.mini_target_prefix,
							mini_image_target=self.bsp.mini_image_target,
							img_path=self.image_path)
		cmd(commands, exit_on_fail=exit_on_fail)

	def post_build(self, exit_on_fail=True):
		commands = r"""
			set -x
			cp {log_path} {log_dir}/build.log
			test "{compress_image}" == "false" || bzip2 -zkf {img_path}
			bd_base=$(pwd)
			log_pre=/tmp/delete-build.pre
			rm -f ${{log_pre}}.*
			for d in $(ls | grep build.pre); do
				nohup sudo rm -rf $bd_base/$d > ${{log_pre}}.$d 2>&1 &
			done
					""".format(img_path=self.image_path,
							log_path=self.log_path,
							log_dir=self.bsp.log_dir,
							compress_image=self.bsp.compress_image)
		cmd(commands, exit_on_fail=exit_on_fail)

	def do_all(self):
		os.makedirs(self.build_top_dir, exist_ok=True)
		os.chdir(self.build_top_dir)
		self.logger.info("Prepare Yocto repository")
		self.prepare_repo()
		self.logger.info("Set kernel related conf")
		self.set_kernel_conf()
		self.logger.info("Set extra confs in conf file(s)")
		self.set_confs()
		self.logger.info("Start Yocto build")
		self.build()
		self.logger.info("Compress the image and rename the log")
		self.post_build()

class StableKernel(models.Model):
#   Upstream Kernel patches
	commit_id = models.CharField(max_length=64, null=False, blank=False)
	payload_hash = models.CharField(max_length=64, null=False, blank=False)
	subject = models.CharField(max_length=256, null=False, blank=False)
	author = models.CharField(max_length=128, null=False )
	tag = models.CharField(max_length=64)
	date = models.DateTimeField()

	class Meta:
		unique_together = ( 'commit_id', 'payload_hash' )

	def __str__(self):
		return "Patch ID {} ({})".format(self.payload_hash, self.subject)

	def __repr__(self):
		return str(self.__dict__)

	def to_dict(self):
		return {
			"patch-id" : self.payload_hash,
			"commit_id" : self.commit_id,
			"tag" : self.tag,
			"author" : self.author,
			"subject" : self.subject,
			"date" : str(self.date) }

class ProductType(models.Model):
	'''
	Iotg Kernel Product Type

	:ivar name: Name of Product Type
	:vartype name: str

	'''
	name = CharField(max_length=64, unique=True)

	@classmethod
	def validate(cls, value):
		'''
		Check whether Release Type is valid (by name)
		'''
		try:
			query = cls.objects.get(name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value
	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files

		:returns: Readable String Representation of Object
		:rtype: str
		'''
		return self.name and self.name or "<no name>"

	def __repr__(self):
		'''
		Serialized String Representation of Object
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure

		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "name" : self.name })

	def __del__(self):
		'''
		Class Destructor

		'''
		pass


class ProductVariant(models.Model):
	'''
	Iotg Kernel Product Type

	:ivar name: Name of Product Type
	:vartype name: str

	'''
	name = CharField(max_length=64, unique=True)

	@classmethod
	def validate(cls, value):
		'''
		Check whether Variant is valid (by name)
		'''
		try:
			query = cls.objects.get(name = value)
		except cls.DoesNotExist as e:
			raise ArgumentTypeError("Invalid %s Type %s" % (cls.__name__ , value ) )
		return value
	@classmethod
	def list(cls):
		'''
		Return a list of valid entries
		'''
		result = []
		query = cls.objects.all()
		for row in query:
			result.append(row.name)
		return str(result)

	def __str__(self):
		'''
		Readable String Representation of Object
		Suitable for Human-Readability in Log Files

		:returns: Readable String Representation of Object
		:rtype: str
		'''
		return self.name and self.name or "<no name>"

	def __repr__(self):
		'''
		Serialized String Representation of Object
		Suitable For Persistent Storage or Pickling,
		Allowing for Restart In Case Of Failure

		:returns: JSON-formatted string representation of Object
		:rtype: JSON
		'''
		return str({ "name" : self.name })

	def __del__(self):
		'''
		Class Destructor

		'''
		pass

class KernelProduct(models.Model):

	kernel = ForeignKey(Kernel, on_delete=models.CASCADE)
	int_ext = models.CharField(max_length=1, null=False)
	producttype = ForeignKey(ProductType, on_delete=models.CASCADE)
	variant = ForeignKey(ProductVariant, on_delete=models.CASCADE)
	src_repo = ForeignKey(Repository, related_name = 'src_repo', on_delete=models.CASCADE)
	staging_repo = ForeignKey(Repository, related_name = 'staging_repo', on_delete=models.CASCADE)
	release_repo = ForeignKey(Repository, related_name = 'release_repo', on_delete=models.CASCADE)
	staging_branch_tmpl = ForeignKey(KTemplate, related_name = 'staging_branch_tmpl', on_delete=models.PROTECT)
	release_branch_tmpl = ForeignKey(KTemplate, related_name = 'release_branch_tmpl', on_delete=models.PROTECT)
	staging_tag_tmpl = ForeignKey(KTemplate, related_name = 'staging_tag_tmpl', on_delete=models.PROTECT)
	release_tag_tmpl = ForeignKey(KTemplate, related_name = 'release_tag_tmpl', on_delete=models.PROTECT)
	package_tmpl = ForeignKey(KTemplate, related_name = 'package_tmpl', on_delete=models.PROTECT)

	class Meta:
		unique_together = ( 'kernel',  'int_ext','producttype',  'variant')

	def stage(self, args):
		# Call staging method derived from (Kernel, ProductType, ProductVariant)
		pass

	# Each product type / product variant shall have its own concrete method
	def build(self, args):
		# Call build method derived from (Kernel, ProductType, ProductVariant)
		pass

	# Each product type / product variant shall have its own concrete method
	def release(self, args):
		# Call build method derived from (Kernel, ProductType, ProductVariant)
		pass

	def __str__(self):
		return "KernelProduct {} {} {} ({})".format(self.kernel.name, self.producttype, self.variant, self.kernel.alt_name)

	def __repr__(self):
		return str(self.__dict__)

