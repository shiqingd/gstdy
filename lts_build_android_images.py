#!/usr/bin/env python3
import os
import sh
import sys
import lsb_release
import re
import shutil
import subprocess
import argparse
import tracers

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError
from django.db.models import Q
from django.utils import timezone

from framework.models import *

import lib.utils
from lib.pushd import pushd

def __main(args):
	dm_build = False

	try:
		kernel = Kernel.objects.get(name = args.kernel)
		cpu = Platform.objects.get(name = args.cpu)
		target = Target.objects.get(name = args.dessert)
		build = Build.objects.get(kernel = kernel, cpu = cpu, target = target)
		repo = KernelRepoSet.objects.get(kernel = kernel, repo__repotype__repotype = 'source').repo
		kernelroot = KernelRoot.objects.get(kernel = kernel, cpu = cpu)
		configdir = ConfigPath.objects.get(build__kernel = kernel, build__cpu = cpu, build__target = target)
		configroot = AndroidConfig.objects.get(kernel = kernel)
		mixindir = MixinConfigDir.objects.get(kernel = kernel, cpu = cpu)
		maketarget = MakeTarget.objects.get(build = build)
		manifest_type = args.manifest_type
		# And a whole bunch more variables! Yay!
		manifest_xml = "{}/android/{}-manifest.xml".format(os.getcwd(), args.kernel)
		configbranch = re.sub((args.kernel == '4.19lts' and '/android' or 'android-'), "", str(args.branch))
		android_root = "{}/android".format(os.getcwd())
		kernel_root = "{}/{}".format(android_root, kernelroot.kernel_root)
		config_root = "{}/{}".format(android_root, configroot.config_root)
		config_dir = "{}/{}".format(config_root, configdir.config_dir)
		config_dir_in_mixin = "{}/{}".format(android_root, mixindir.config_dir_in_mixin)
		lib.utils.setup_android(args.kernel, args.cpu, manifest_type, android_root, args.dessert, "")
	except IndexError as e:
		print(e)
		return False

	# Checking to see if $branch includes "staging-testing" inside it.
	if "staging-testing" in args.branch:
		dm_build = True
		print("Email:{}".format(os.environ["DM_EMAIL"]))
		print("Branch:{}".format(os.environ["BRANCH"]))

	# If we're on Ubuntu 16.04, it looks like the `ld` utility inside android_root
	# is not the one that we want to use. So, it instead copies `ld.gold` from
	# `/usr/bin` to `android_root`.
	# It turns out that lsb_release is actually written in Python...
	if lsb_release.get_lsb_information()["RELEASE"] == "16.04":
		builddir = "{}/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.15-4.8/x86_64-linux/bin/".format(android_root)
		with pushd(builddir):
			shutil.move("{}/ld".format(builddir), "{}/ld.bak".format(builddir))
			os.symlink("/usr/bin/ld.gold", "{}/ld".format(builddir))

	# And if args.baseline is false... we do a whole bunch of stuff with git. Hoo boy.
	if not args.baseline:
		with pushd(kernel_root):
			#TODO FIX THIS PART
			if dm_build:
				Repository.objects.filter(project='kernel-coe-tracker')[0].git_remote_add_and_fetch('tracker')
				checkout("tracker/{}".format(args.branch), args.branch)
			else:
				repo.git_remote_add_and_fetch("z_bkc")
				sh.git.fetch("z_bkc")
				lib.utils.checkout("z_bkc/{}".format(args.branch), args.branch)
		config_repo = KernelRepoSet.objects.get(kernel = kernel, repo__repotype__repotype = 'config').repo
		if not os.path.isdir(config_root):
			config_repo.initialize(config_root, "master")

		with pushd(config_root):
			config_repo.git_remote_add_and_fetch("z_config")
			sh.git.fetch("z_config")
			lib.utils.checkout("z_config/{}".format(configbranch), configbranch)

		# get_sha in the Bash version sets `sha1` as the variable, so we're keeping it.
		sha1 = lib.utils.get_sha_last_commit(kernel_root)
		# Similarly, linux_version is what get_kernelversion sets.
		linux_version = kernelroot.get_kernelversion(kernel_root)

	# add extra patches
	with pushd(android_root):
		build._cherrypick()
		lib.utils._repo(["manifest", "-r", "-o", manifest_xml])

	if not args.baseline:
		if config_dir != config_dir_in_mixin:
			config_files = [f for f in os.listdir(config_dir)
					if os.path.isfile("{}/{}".format(config_dir, f))]
			for f in config_files:
				shutil.copy("{}/{}".format(config_dir, f),
					    "{}/{}".format(config_dir_in_mixin, f))

		kernel_version_file = "{}/{}".format(config_dir_in_mixin, cpu.config_file)

		with open(kernel_version_file, "r") as f:
			lines = f.readlines()
		with open(kernel_version_file, "w") as f:
			for line in lines:
				if line.startswith("CONFIG_LOCALVERSION"):
					line = re.sub("CONFIG_LOCALVERSION=.*",
						"CONFIG_LOCALVERSION=\"-PKT-{}\"".format(sha1), line)
				f.write(line)

		with pushd(config_dir_in_mixin):
			sh.git.add("*")
			sh.git.commit(["-s", "-m", "x86: config: Change kernel string"])

	# special care for iot_joule
	if args.cpu == "iot_joule":
		with pushd("{}/device/google/iot/kconfig".format(android_root)):
			# We're changing the second occurrence of \.[0-9]//. Gross.
			directory_path = re.sub(r"(\.[0-9])(.*)(\.[0-9])", r"\1\2", linux_version)
			subprocess.run(["rsync", "-avz", "4.9/", directory_path])

	with pushd(android_root):
		# setup build enviornment
		# source build/envsetup.sh
		if args.cpu != "iot_joule":
			os.system("./device/intel/mixins/mixin-update")

		sh.git.lfs(["install"])
		sh.git.lfs(["install", "--skip-smudge"])

		make_targets = MakeTarget.objects.get(build = build).make_targets
		# We have to run envsetup.sh to define lunch.
		make_clean_command="make clean"
		make_command="make -j32 {}".format(make_targets)
		build_cmd="/bin/bash", "-i", "-c", ". build/envsetup.sh;" "lunch {}-userdebug;{};{}".format(args.cpu,make_clean_command,make_command)
		subprocess.run(build_cmd)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=sys.argv[0])
	parser.add_argument('--baseline', '-c', action='store_true', help='Use Baseline')
	parser.add_argument('--branch', '-b', required=True, type=str, help='Branch to build')
	parser.add_argument('--dessert', '-d', default='p', type=str, help='Android Version (dessert) to build')
	parser.add_argument('--cpu', '-s', type=CPU.validate, help="CPU Type - valid values: "+CPU.list())
	parser.add_argument('--manifest-type', '-m', type=AndroidManifest.validate, help="Manifest Type :"+AndroidManifest.list())
	parser.add_argument('--kernel', '-p', type=Kernel.validate, default='devbkc', help=Kernel.list())
	parser.add_argument('--debug', '-X', dest='lib.dry_run.dry_run', action='store_true', help="Show Debugging Information")
	parser.add_argument('--dry_run', dest='lib.dry_run.dry_run', action='store_true', help="Do not actually do anything; just print what would happen")
	args = parser.parse_args()
	sys.settrace(tracers.trace_function_calls)
	tracers.trace_module('lib.utils')
	tracers.trace_module('lib.pushd')
	assert("WORKSPACE" in os.environ)
	__main(args)
