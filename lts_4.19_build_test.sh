#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions
#look for android or base and do if for base check or android check
branch=$STAGING_REV
declare android_type=$(echo $branch | grep -c android)
declare base_type=$(echo $branch | grep -c base)

if [ ${base_type} == '1' ] ; then
	declare configbranch=$(echo $branch | sed -e 's/\/base//')
elif [ ${android_type} == '1' ] ; then
	declare configbranch=$(echo $branch | sed -e 's/\/android//')
fi


init_kernel_lts_staging

pushd $mydir/kernel-config
	git checkout ${configbranch}
popd

# Check build of local branches
pushd kernel-lts-staging
	[[ $- =~ e ]] ; errexit=$? # save error exit state restore later
	set +e

	check_build $branch base x86_64
	ret_base=$?

	if [ ${android_type} == '1' ] ; then
		check_build $branch android x86_64 \
			$working_dir/kernel-config/bxt/android/non-embargoed/x86_64_defconfig \
			$working_dir/kernel-config/bxt/android/non-embargoed/debug_diffconfig
		ret_android_bxt=$?
	fi

	if [ ${base_type} == '1' ] ; then
		check_build $branch base x86_64 \
			$working_dir/kernel-config/bxt/clear/linux_guest/non-embargoed/x86_64_defconfig
		ret_clear_linux_guest=$?

		check_build $branch base x86_64 \
			$working_dir/kernel-config/bxt/clear/service_os/non-embargoed/x86_64_defconfig
		ret_clear_service_os=$?

		check_build $branch base x86_64 \
			$working_dir/kernel-config/bxt/clear/bare_metal/non-embargoed/x86_64_defconfig
		ret_clear_bare_metal=$?
	fi
	eval "$saved_options" &> /dev/null
	(( $errexit )) && set +e
popd

if [ ${android_type} == '1' ] ; then
	if [ $ret_base -ne 0 ] || [ $ret_android_bxt -ne 0 ] ; then
		echo -e "\033[0;31m\t*** Android Failed ***\nCheck build.err for issues building \033[00m"
		echo -e "Error in build.  Please check." > $working_dir/message.txt
		exit 1
	fi
fi

if [ ${base_type} == '1' ] ; then
	if [ $ret_base -ne 0 ] || [ $ret_clear_bare_metal -ne 0 ] || \
		[ $ret_clear_service_os -ne 0 ] || [ $ret_clear_linux_guest -ne 0 ] ; then
		echo -e "\033[0;31m\t*** Base Failed ***\nCheck build.err for issues building \033[00m"
		echo -e "Error in build.  Please check." > $working_dir/message.txt
		exit 1
	fi
fi
