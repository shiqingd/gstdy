#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

exit_usage() {
        cat <<EOF >&2

USAGE:
	$0 -s soc -b branch_name [-m <daily|weekly>] [-c] [-d <dessert ver> ]

	b = staging branch name
	s = soc build name (${socs[*]})
        d = (optional) android version (p [default], omr1)
	m = (optional) 1A manifest type (daily, weekly)
	p = (optional) product to build (${products[*]})
	c = baseline build option.  Will not change to the staging kernel.
	h|? = help (this screen)

EOF
exit 1
}

#########################
# main
socs=(gordon_peak kbl_rvp iot_joule icl_presi icl_presi_kbl icl_presi_apl tgl_presi ehl_presi)
products=(devbkc 4.9bkc 4.14bkc mainlinetracking)

OPT_exit_only=false
OPT_baseline=false
repo_sync_enable=false
manifest_type=latest
product=devbkc
dessert=p
while getopts "t:crd:s:m:p:h?" OPTION; do
	case $OPTION in
		t)
			tag=${OPTARG}
			;;
		c)
			OPT_baseline=true
			;;
		r)
			repo_sync_enable=true
			;;
		d)	
			dessert=${OPTARG}
			;;
		s)
			soc=${OPTARG}
			;;
		m)
			manifest_type=${OPTARG}
			case "$manifest_type" in
				weekly|daily)
					:
					;;
				*)
					OPT_exit_only=true
					;;
			esac
			;;
		p)
			product="${OPTARG}"
			case "$product" in
				devbkc|4.9bkc|4.14bkc|mainlinetracking|4.19lts)
					:
					;;
				*)
					OPT_exit_only=true
					;;
			esac
			;;
		h|?)
			OPT_exit_only=true
			;;
	esac
done
$OPT_exit_only && exit_usage

declare prd_soc_key=${product}${SUBSEP}${soc}

# check options
if [ "${ANDROID_SUPPORTED[${prd_soc_key}]}" != "true" ] ; then
	echo Please provide correct product and soc
	exit_usage
fi

if ! [ "$tag" ] ; then
	echo "Need a tag to test!"
	exit_usage
fi


declare configbranch=$(echo $branch | sed -e 's/\/android//')
if [ "$repo_sync_enable" == "true" ] ; then
	declare android_root=$mydir/Android
else
	declare android_root=$mydir/android
fi
declare manifest_xml="${android_root}/${product}-manifest.xml"
declare cherrypick_list="${android_root}/cherrypick.txt"
declare mixins_root=${android_root}/device/intel/mixins
declare kernel_root=${android_root}/${ANDROID_KERNEL[${prd_soc_key}]}
declare config_root=${android_root}/${ANDROID_CONFIG[${product}]}
declare config_dir=${android_root}/${PK_CONFIG_DIR[${prd_soc_key}]}
declare android_config_dir=${android_root}/${PK_CONFIG_DIR_ANDROID[${prd_soc_key}]}
declare config_dir_in_mixin=${android_root}/${ANDROID_CONFIG_DIR_IN_MIXIN[${prd_soc_key}]}
set allowZip64=True
if [ "$repo_sync_enable" == "true" ] ; then
	setup_android $product $soc $manifest_type $android_root $dessert
	pushd $android_root
		cherrypick_patches $product $soc $dessert $cherrypick_list
		/home/jenkins/bin/repo.google manifest -r -o $manifest_xml
	popd
else
	# add extra patches
	pushd $android_root
		/home/jenkins/bin/repo.google checkout baseline || :
		/home/jenkins/bin/repo.google forall -vc "git reset --hard" || :
		/home/jenkins/bin/repo.google abandon ${soc}_temp || :
		/home/jenkins/bin/repo.google start ${soc}_temp --all || :
		rm -rf out/target/product/${soc}/obj/kernel || :
		rm -rf out/target/product/${soc}/obj/PACKAGING/target_files_intermediates || :
                rm -rf out/target/product/${soc}/obj/ETC/system_build_prop_intermediates/build.prop || :
                rm -rf out/target/product/${soc}/recovery/root/prop.default || :
                rm -rf out/target/product/${soc}/system/build.prop || :
		rm out/target/product/${soc}/ota_metadata || :
		rm out/target/product/${soc}/${soc}* || :
		rm out/target/product/${soc}/${soc}-* || :
		cherrypick_patches $product $soc $dessert $cherrypick_list
		/home/jenkins/bin/repo.google sync -c
		/home/jenkins/bin/repo.google manifest -r -o $manifest_xml
	popd
fi

# change ld to use local if on ubuntu 16.04
if [ "$(lsb_release -a | grep Release | awk '{print $2}')" == "16.04" ] ; then
	pushd $android_root/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.15-4.8/x86_64-linux/bin/
	mv ld ld.bak
	ln -s /usr/bin/ld.gold ld
	popd
fi



if [ "$OPT_baseline" == "false" ] ; then
	pushd $kernel_root
		add_scm lts_bkc https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging
		git checkout $tag
	popd
	if ! [ -d $config_root ] ; then
		git_project https://github.com/intel-innersource/os.linux.kernel.kernel-config \
			$config_root master
	fi
	pushd $config_root
	add_scm z_config https://github.com/intel-innersource/os.linux.kernel.kernel-config
	git checkout $tag
	popd

	get_sha $kernel_root
	get_kernelversion $kernel_root
fi

if [ "$OPT_baseline" == "false" ] ; then
	# copy configs
	if [ "$config_dir" != "$config_dir_in_mixin" ]; then
		find $config_dir/ -maxdepth 1 -type f \
			-exec cp {} $config_dir_in_mixin/ \;
	fi

	# change kernel version
	STAGING_NUM=${STAGING_REV##*-}
	sed -i -e "/^CONFIG_LOCALVERSION/ s/CONFIG_LOCALVERSION=.*/CONFIG_LOCALVERSION=\"-$STAGING_NUM\"/" \
		${config_dir_in_mixin}/${ANDROID_CONFIG_FILE[${soc}]}

	pushd $config_dir_in_mixin
	git add *
	git commit --allow-empty -s -m "x86: config: Change kernel string"
	popd
fi

# special care for iot_joule
if [ "$soc" = "iot_joule" ] ; then
	pushd $android_root/device/google/iot/kconfig
	rsync -avz 4.9/ $(echo $linux_version | sed 's/\.[0-9]//2')/
	popd
fi

pushd $android_root

source build/envsetup.sh
export TARGET_PRODUCT=gordon_peak
lunch ${soc}-userdebug
#export ANDROID_CONSOLE=serial

/home/jenkins/bin/repo.google forall -r '.*google.*' -c 'git lfs fetch && git lfs checkout'
if [ "$soc" = "ehl_presi" ] ; then
	make flashfiles BOARD_FLASH_NVME=1 -j32 ${ANDROID_MAKE_TARGETS[${prd_soc_key}]}
	echo "Building for EHL Presi"
else
	make flashfiles
fi

#recorder kernel_code HEAD SHA1 value for testers' convenience
pushd kernel/lts2018/
  git log --oneline -1 > kernel_code_HEAD.txt
popd

# update and commit re-generated android config for coverity support.
# eachtime this script gets run it will push the generate config to a tag
# called cov-soc-staging-lts-kernelversion-OS_Dessert-timestamp
# Example: cov-gordon-peak-staging-lts-v4.19.46-android-190618T011631Z
# cov-gordon-peak-acrn-staging-lts-v4.19.46-android-190618T011631Z
# name of new config cov-soc_x86_64_defconfig per platform
if [ "$OPT_baseline" == "false" ] ; then
update_android_config $android_config_dir $config_dir $soc
	pushd $config_root
		commit_local_no_check "x86: config: update for kernel change in Android build with Tag:$tag"
		#cov_tag=cov-$soc-$tag
		cov_tag=$(get_cov_tag $tag $soc)
		tag_sandbox $cov_tag '' ||:
		push_tag_sandbox z_config $cov_tag '' ||:
	popd
fi
/home/jenkins/bin/repo.google checkout baseline ||:
/home/jenkins/bin/repo.google forall -vc "git reset --hard" || :
/home/jenkins/bin/repo.google abandon ${soc}_temp || :
popd

