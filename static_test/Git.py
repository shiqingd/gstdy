#!/usr/bin/python
'''
@author: pjnozisk
'''

from __future__ import print_function
import os
import sh
import re
import sys
import traceback
import inspect
import json

class Git(object):

	__git = sh.Command('/usr/bin/git')

	## Class constructor
	def __init__(self, url):
		self.stdout = sys.stdout
		self.stderr = sys.stderr
		self.cwdstack = []
		self.verbose = False
		match = re.search('([a-z]+)://([a-z0-9\-_.:]+)/(.+)',  url)
		if match:
			self.protocol = match.group(1)
			self.host = match.group(2)
			self.project = match.group(3).split('.git')[0]
			self.basedir = os.path.basename(self.project)
		else:
			raise LookupError(url + " Not found")

	## private method to push directory
	# @param dirr directory to push
	def __pushdir(self, dirr):
		self.cwdstack.append(os.getcwd())
		os.chdir(dirr)

	## public method to push project root directory
	def pushd(self):
		self.__pushdir(self.basedir)

	## private method to pop directory
	def __popdir(self):
		try:
			popdir = self.cwdstack.pop()
			os.chdir(popdir)
		except Exception as e:
			pass
	## public method to pop directory
	def popd(self):
		self.__popdir()

	def clone(self, *args):
		git_params = [ "clone" ] + list(args) + [ self.protocol + '://' + self.host + '/' + self.project ]
		output = self._Git__git(git_params, _ok_code=range(0,130)).wait()
		return output

	def __str__(self):
		return self.url

def __make_method_0(methodname):
	def _method(self, *args):
		git_params = [methodname] + list(args)
		try:
			output = self._Git__git(git_params).wait()
		except Exception as e:
			print(traceback.format_exc())
			raise
		finally:
			pass
		return output
	return _method

def __make_method(methodname):
	def _method(self, *args, **kwargs):
		self._Git__pushdir(self.basedir)
		git_params = [methodname.replace("_","-")] + list(args)
		if self.verbose:
			print(git_params, kwargs)
		if "_in" in kwargs:
			output = self._Git__git(git_params, _ok_code=range(0,130), _tty_out=False, _in=kwargs["_in"]).wait()
		else:
			output = self._Git__git(git_params, _ok_code=range(0,130), _tty_out=False).wait()
		self._Git__popdir()
		print(output)
		return output
	return _method

git_commands = [ 'add','config','get_tar_commit_id','merge_recursive','remote','show_ref',
'add__interactive','count_objects','grep','merge_resolve','remote_ext','stage',
'am','credential','hash_object','merge_subtree','remote_fd','stash',
'annotate','credential_cache','help','merge_tree','remote_ftp','status',
'apply','credential_cache__daemon','http_backend','mergetool','remote_ftps','stripspace',
'archive','credential_store','http_fetch','mktag','remote_http','submodule',
'bisect','daemon','http_push','mktree','remote_https','subtree',
'bisect__helper','describe','imap_send','mv','remote_testsvn','symbolic_ref',
'blame','diff','index_pack','name_rev','repack','tag',
'branch','diff_files','init','notes','replace','unpack_file',
'bundle','diff_index','init_db','p4','request_pull','unpack_objects',
'cat_file','diff_tree','instaweb','pack_objects','rerere','update_index',
'check_attr','difftool','log','pack_redundant','reset','update_ref',
'check_ignore','difftool__helper','ls_files','pack_refs','rev_list','update_server_info',
'check_mailmap','fast_export','ls_remote','patch_id','rev_parse','upload_archive',
'check_ref_format','fast_import','ls_tree','prune','revert','upload_pack',
'checkout','fetch','mailinfo','prune_packed','rm','var',
'checkout_index','fetch_pack','mailsplit','pull','send_email','verify_pack',
'cherry','filter_branch','merge','push','send_pack','verify_tag',
'cherry_pick','fmt_merge_msg','merge_base','quiltimport','sh_i18n__envsubst','web__browse',
'clean','for_each_ref','merge_file','read_tree','shell','whatchanged',
'format_patch','merge_index','rebase','shortlog','write_tree',
'column','fsck','merge_octopus','receive_pack','show',
'commit','fsck_objects','merge_one_file','reflog','show_branch',
'commit_tree','gc','merge_ours','relink','show_index','range_diff' ]

for methodname in git_commands:
	_method = __make_method(methodname)
	setattr(Git, methodname, _method)


