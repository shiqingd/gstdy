#!/bin/bash

#
# Common code used by the lts kernel update scripts.
#
lts_version="4.9"	# Default LTS kernel version


## validate_lts_version
#
# Validate the lts_version parameter. Note that a default value
# for lts_version may be assigned in lts_common.sh
#
validate_lts_version() {
	declare lts_version=$1

	if [ "$lts_version" == "4.9" ]; then
		echo "Processing the 4.9 LTS Production Kernel"
		source $mydir/lts_4.9_common.sh
	elif [ "$lts_version" == "4.14" ]; then
		echo "Processing the 4.14 LTS Production Kernel"
		source $mydir/lts_4.14_common.sh
	else
		die "LTS kernel version $lts_version is not supported" \
		    "Please specify a valid version using -l"
		    "Supported versions include 4.9"
	fi
}


## assert_kernel_consistency
#
# Assert that the rebasing and non-rebasing branches match. Exit
# with an error if that is not the case.
#
assert_kernel_consistency() {
	declare lts_version=$1

	pushd $working_dir/kernel-lts-staging || \
		die "Unable to cd to $working_dir/kernel-lts-staging"

	if [ "$lts_version" == "4.9" ]; then
		git diff --exit-code 4.9/base rebasing/$lts_version/base || \
			die "Initial 4.9/base and " \
				"rebasing/$lts_version/base do not match!"
		git diff --exit-code 4.9/android  \
			rebasing/$lts_version/android ||
			die "Initial 4.9/android and " \
				"rebasing/$lts_version/android do not match!"
		git diff --exit-code 4.9/yocto rebasing/$lts_version/yocto || \
			die "Initial 4.9/yocto and " \
				"rebasing/$lts_version/yocto do not match!"

	elif [ "$lts_version" == "4.14" ]; then
		git diff --exit-code 4.14/base rebasing/$lts_version/base || \
			die "Initial 4.14/base and " \
				"rebasing/$lts_version/base do not match!"
		git diff --exit-code 4.14/yocto rebasing/$lts_version/yocto || \
			die "Initial 4.14/yocto and " \
				"rebasing/$lts_version/yocto do not match!"
	else
		die "LTS kernel version $lts_version is not supported" \
		    "Please specify a valid version using -l"
		    "Supported versions include 4.9"
	fi


	popd || die "assert_kernel_consistency: popd failure"
}


## test_lts_compile
#
# Test that each of the kernels compile correctly with allyesconfig,
# allnoconfig, allmodconfig. For android, test the proposed config
# files
#
test_lts_compile() {
	declare working_dir=$1
	declare lts_version=$2
	declare ret_base=0
	declare ret_yocto=0
	declare ret_yocto_rt=0
	declare ret_android_bxt=0
	declare ret_android_kbl=0
	declare ret_sos=0
	declare ret_usos=0
	declare ret_uos=0
	declare ret_yp=0

	pushd $working_dir/kernel-config || \
		die "Unable to cd to $working_dir/kernel-config"
#	checkout_local ${lts_version}/config
	if [ "$lts_version" == "4.9" ]; then
		checkout_local 4.9/config
	fi
	if [ "$lts_version" == "4.14" ]; then
		checkout_local 4.14/config
	fi

	pushd $working_dir/kernel-lts-staging || \
		die "Unable to cd to $working_dir/kernel-lts-staging"
	set +e
#	check_build $lts_version/base base x86_64 "" "" ""
	if [ "$lts_version" == "4.9" ]; then
		check_build 4.9/base base x86_64 "" "" ""
	fi
	if [ "$lts_version" == "4.14" ]; then
		check_build 4.14/base base x86_64 "" "" ""
	fi


	ret_base=$?
	if [ ! git diff --quiet $lts_version/base $lts_version/yocto ]; then
		#check_build $lts_version/yocto yocto x86_64 "" "" ""
	if [ "$lts_version" == "4.9" ]; then
		check_build 4.9/yocto yocto x86_64 "" "" ""
	fi
	if [ "$lts_version" == "4.14" ]; then
		check_build 4.14/yocto yocto x86_64 "" "" ""
	fi


		ret_yocto=$?
	fi
	if [ "$lts_version" == "4.9" ]; then
		#check_build $lts_version/android android x86_64 \
		check_build 4.9/android android x86_64 \
		$working_dir/kernel-config/bxt/android/x86_64_defconfig \
		$working_dir/kernel-config/bxt/android/debug_diffconfig \
		$working_dir/kernel-config/bxt/android/eng_diffconfig
		ret_android_bxt=$?
	fi
	set -e

	if [ $ret_base -ne 0 ] || [ $ret_yocto -ne 0 ] || [ $ret_usos -ne 0 ] || \
	   [ $ret_sos -ne 0 ] || [ $ret_uos -ne 0 ] || [ $ret_yp -ne 0 ] || \
	   [ $ret_android_bxt -ne 0 ] || [ $ret_android_kbl -ne 0 ] || \
           [ $ret_preempt_rt -ne 0 ]; then
		die "test_lts_compile: build failure"
	fi
	popd || die "test_lts_compile: popd failure"
}


## update_config_files
#
# Check the android and IOT config files with olddefconfig and update
# them if necessary. Push updates to the ${lts_verison}/lts-next branch.
#
update_config_files() {
	declare working_dir=$1
	declare lts_version=$2

	pushd $working_dir/kernel-config || \
		die "Unable to cd to $working_dir/kernel-config"
#	checkout_local ${lts_version}/lts-next
	if [ "$lts_version" == "4.9" ]; then
		checkout_local 4.9/config
	elif [ "$lts_version" == "4.14" ]; then
		checkout_local 4.14/config
	else
		die "checkout_local_config dir: lts checkout failure"
	fi
	
	pushd $working_dir/kernel-lts-staging || \
		die "Unable to cd to $working_dir/kernel-lts-staging"
	if [ "$lts_version" == "4.9" ]; then
#		checkout_local 4.9/android
		checkout_local 4.9/android
		update_config x86_64 \
		  $working_dir/kernel-config/bxt/android/x86_64_defconfig
		update_config x86_64 \
		  $working_dir/kernel-config/bxt/iot/joule.kconfig
	elif [ "$lts_version" == "4.14" ]; then
#		checkout_local 4.14/yocto
		checkout_local 4.14/yocto
		update_config x86_64 \
		  $working_dir/kernel-config/bxt/yocto/x86_64_defconfig
#		checkout_local 4.14/base
		checkout_local 4.14/base
		update_config x86_64 \
		  $working_dir/kernel-config/bxt/linux/x86_64_defconfig
		update_config x86_64 \
		  $working_dir/kernel-config/bxt/service_os/x86_64_defconfig
		update_config x86_64 \
		  $working_dir/kernel-config/bxt/service_os/uefi_x86_64_defconfig
	else
		die "update_config_files: popd failure"
	fi
	popd || die "update_config_files: popd failure(1)"

	commit_local "x86: config: update for kernel change $datetime"
#	push_remote origin ${lts_version}/lts-next staging/$lts_version/$datetime
	if [ "$lts_version" == "4.9" ]; then
		push_remote origin 4.9/config staging/$lts_version/$datetime
	fi
	if [ "$lts_version" == "4.14" ]; then
		push_remote origin 4.14/config staging/$lts_version/$datetime
		push_remote origin 4.14/config staging/$lts_version/base-$datetime
	fi
	popd || die "update_config_files: popd failure(2)"
}


## push_staging_branches
#
# Push the new kernel source to the staging branches. This includes
# the non-rebasing branches (which we release) and the rebasing branches
# (which we do not release)
#
push_staging_branches() {
	declare working_dir=$1
	declare lts_version=$2

	# Update the config files and push the config staging branch
	update_config_files $working_dir $lts_version

	# Push the rebasing versions of the staging branches
	pushd $working_dir/kernel-lts-staging || \
		die "Unable to cd to $working_dir/kernel-lts-staging"
	push_remote origin rebasing/$lts_version/yocto \
		staging/rebasing/$lts_version/yocto-$datetime
	if [ "$lts_version" == "4.9" ]; then
		push_remote origin rebasing/$lts_version/android \
			staging/rebasing/$lts_version/android-$datetime
	fi
	push_remote origin rebasing/$lts_version/base \
		staging/rebasing/$lts_version/base-$datetime
	# Push the non-rebasing kernels to the staging branches

	if [ "$lts_version" == "4.9" ]; then
		push_remote origin 4.9/yocto \
			staging/$lts_version/yocto-$datetime
		push_remote origin 4.9/android \
			staging/$lts_version/android-$datetime
		push_remote origin 4.9/base \
			staging/$lts_version/base-$datetime
	elif [ "$lts_version" == "4.14" ]; then
		push_remote origin 4.14/yocto \
			staging/$lts_version/yocto-$datetime
		push_remote origin 4.14/base \
			staging/$lts_version/base-$datetime
	else
		die "push_staging_branches: staging creating failure"
	fi
	popd || die "push_staging_branches: popd failure"
}
