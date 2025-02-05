#!/usr/bin/env python3

import sys
import os
import argparse
import re
import logging
import shutil
import json
import inspect
import traceback
import sh

if not "DJANGO_SETTINGS_MODULE" in os.environ:
		os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
		import django
		django.setup()

from django.db.models import Q
from framework.models import *

from lib.pushd import pushd
import lib.dry_run
from lib.dry_run import dryrunnable_method
from lib.utils import sed_inplace, cmd

_git = sh.Command('/usr/bin/git')

if __name__ == '__main__':

	assert("WORKSPACE" in os.environ)

	WORKSPACE = os.environ["WORKSPACE"]

	parser = argparse.ArgumentParser(prog=sys.argv[0], epilog = """\
#The yocto_staging script will build the kernel from the branch named on
#the commandline with various version of Poky.  It will always use the
#dev-bkc repo.""")
	parser.add_argument("--kernel", "-k", required=True, type=Kernel.validate, help="Kernel product: "+Kernel.list())
	parser.add_argument("--yocto_release", "-p", help="Poky/Yocto project release branch (zeus, rocko, sumo, master)", default="master")
	parser.add_argument("--meta_intel_release", "-m", help="meta-intel project branch name (hardknott)", default="master")
	parser.add_argument("--meta_openembedded_release", "-o", help="meta-openembedded project branch name (hardknott)", default="master")
	parser.add_argument("--staging_tag", "-t", help="tag -  this porvides the kernel source staging tag", default='')
	parser.add_argument("--rt_bkc_branch", "-y", help="rt_bkc_branch name", default="hardknott/yocto")
	parser.add_argument("--image_type", "-i", help="image_type - poky build image type bitbake core-image-sato (or core-image-minimal)", default="core-image-sato")
	parser.add_argument("--debug_tag", "-d", action='store_true', default=False, help="RT kernel with debug configs will be built when add this debug flag")
	parser.add_argument("--cmd_i915_tag", "-g", action='store_true', default=False, help="remove i915 related cmdline when add this flag")
	args = parser.parse_args()

	# FIXME KLUDGE  - re-map worktrees per logic below
	# This should not be necessary
	alt_worktree = {
		"poky" : "yocto_project",
		"intel-innersource/os.linux.kernel.ikt-rt-bkc" : "meta-intel-ikt-rt"
	}

	# FIXME - Because these values do not change often,
	# FIXME - Toolchain and metalayer releases should be modeled in the database
	alt_branch = {
		"poky" : args.yocto_release,
		"meta-intel" : args.meta_intel_release,
		"meta-openembedded" : args.meta_openembedded_release,
		"intel-innersource/os.linux.kernel.ikt-rt-bkc" : args.rt_bkc_branch
	}

	lib.dry_run.verbose(True)	# trace dryrunnable methods even if dry_run = False

	os.chdir(WORKSPACE)

	# Get Poky Toolchain
	poky_repo = Repository.objects.get(project = 'poky', repotype__repotype = 'toolchain')
	if poky_repo.project in alt_worktree:
		poky_repo.initialize(scmdir=alt_worktree[poky_repo.project])
	else:
		poky_repo.initialize(scmdir=poky_repo.project)
	with pushd(poky_repo.scmdir, _verbose=True):
		dryrunnable_method(_git, 'clean', '-xdff')
		dryrunnable_method(_git, 'checkout', alt_branch[poky_repo.project])

	topdir = os.path.join(WORKSPACE, poky_repo.scmdir)

	with pushd(topdir, _verbose=True):

		# Get meta-layers
		metalayer_repos = Repository.objects.filter(repotype__repotype = 'metalayer')
		for repo in metalayer_repos:
			if repo.project in alt_worktree:
				repo.initialize(scmdir=alt_worktree[repo.project])
			else:
				repo.initialize(scmdir=repo.project)
			with pushd(repo.scmdir, _verbose=True):
				dryrunnable_method(_git, 'clean', '-xdff')
				dryrunnable_method(_git, 'checkout', alt_branch[repo.project])

		os.environ["PATH"] += ":"+os.path.join(os.getcwd(), 'bitbake', 'bin')

		sh.rm("-rf", "./build.*")

		logger = logging.getLogger()
		logger.setLevel(logging.DEBUG)
		handler = logging.StreamHandler(sys.stdout)
		handler.setLevel(logging.DEBUG)
		formatter = logging.Formatter('%(message)s')
		handler.setFormatter(formatter)
		logger.addHandler(handler)

		sshpassincname = os.path.join(topdir, 'meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass.inc')
		sshpassbbname = os.path.join(topdir, 'meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass_1.05.bb')
		dryrunnable_method(sed_inplace, cmd='d', pattern='SRC_URI', filename=sshpassincname)
		with open(sshpassincname, "a") as f:
			print('SRC_URI = "http://ikt.bj.intel.com:8010/downloads/sshpass/sshpass-1.05.tar.gz"', file=f)
		dryrunnable_method(sed_inplace, cmd='d', pattern='SRC_URI', filename=sshpassbbname)
		with open(sshpassbbname, 'a') as f:
			print('BB_STRICT_CHECKSUM = "0"', file=f)

		commands="""
			set -x
			source oe-init-build-env
			bitbake-layers add-layer {meta_intel}
			bitbake-layers add-layer {meta_openembedded}
			bitbake-layers add-layer {meta_intel_ikt_rt}
			""".format(meta_intel=os.path.join(topdir, "meta-intel"),
			meta_openembedded=os.path.join(topdir, "meta-openembedded/meta-oe"),
			meta_intel_ikt_rt=os.path.join(topdir, "meta-intel-ikt-rt"))

		cmd(commands, exit_on_fail=False)
	
		with pushd('./build', _verbose=True):

			local_conf = open("conf/local.conf", "a")
			auto_conf = open("conf/auto.conf", "a")

			print("IMAGE_FSTYPES = \"wic.bz2  tar\"", file=local_conf)
			print("require conf/multilib.conf", file=local_conf)
			print("MULTILIBS = \"\"", file=local_conf)
			print("IMAGE_ROOTFS_EXTRA_SPACE = \"2097152\"", file=local_conf)
			if args.debug_tag:
				print('K_DEBUG_CONFIG = "1"', file=local_conf)
			if not args.cmd_i915_tag:
				print("APPEND += \"i915.force_probe=* i915.enable_guc=7\"", file=local_conf)

			print("MACHINE = \"intel-corei7-64\"", file=auto_conf)

			kernel = Kernel.objects.get(name = args.kernel)
			tb = TrackerBranch.objects.get(kernel = kernel)
			src_url = re.sub('https://', 'git://', tb.repo.url())
			print("SRC_URL", src_url)
			print("K_BRANCH = \""+tb.branch+"\"", file=auto_conf)
			print("K_REPO = \""+src_url+"\"", file=auto_conf)
			print("LINUX_VERSION = \""+kernel.base_kernel+"\"", file=auto_conf)

			if kernel.name == '4.19lts':
				bbappendfile = './meta-intel-ikt-rt/recipes-rt/images/core-image-sato.bbappend'
				sed_inplace(cmd='d', pattern='IMAGE_INSTALL', filename=os.path.join(TOP, bbappendfile))
				with open(bbappendfile, "a") as f:
					print( 'IMAGE_INSTALL += "rt-tests lvm2 bc keyutils numactl libva-utils stress"', file=f)

			print( "K_PROTOCOL = \"https\"", file=auto_conf)

			if args.staging_tag:
				print("K_TAG =\""+args.staging_tag+"\"", file=auto_conf)
				print( "PREFERRED_PROVIDER_virtual/kernel = \"linux-intel-ikt-rt\"" , file=auto_conf)
				print( "KBRANCH_pn-linux-intel-ikt-rt = \""+args.staging_tag+"\"", file=auto_conf)
				print( "SRCREV_machine_pn-linux-intel-ikt-rt = \"${AUTOREV}\"", file=auto_conf)
				inteliktincfile = os.path.join(topdir,'meta-intel-ikt-rt/recipes-kernel/linux/linux-intel-ikt.inc')
				sed_inplace(cmd='s', pattern='tag=\${K_TAG};', repl='', filename=inteliktincfile)
				sed_inplace(cmd='s', pattern='branch=\${K_BRANCH}', repl='nobranch=1', filename=inteliktincfile)
			else:
				print( "PREFERRED_PROVIDER_virtual/kernel = \"\"" , file=auto_conf)

			print("CORE_IMAGE_EXTRA_INSTALL_append = \" file procps quota sudo glibc-utils coreutils ltp rt-tests keyutils numactl lvm2 bc\"", file=auto_conf)

		commands="""
			set -x
			source oe-init-build-env
			bitbake {image_type}
			""".format(image_type=args.image_type)
	
		cmd(commands, exit_on_fail=True)

