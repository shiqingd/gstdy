#!/bin/bash
working_dir=$PWD
datestring=$(date -u)
datetime=$(date -d "$datestring" -u +%g%m%dT%H%M%SZ)
rm -f build.log build.err || :

#
# Common code used by the kernel update scripts. Please see
# the bottom of this file for common code unconditionally executed.
#

#setup_android
# Configurable Variables
#

SUBSEP=','
# Specify patches that need to be cherry-picked for android build
# Please modify the patch list here if there is any update
declare -A CHERRYPICK_PATCHES=(
    [devbkc,all,omr1]=''
    [devbkc,gordon_peak,omr1]='630995'
    [devbkc,kbl_rvp,omr1]=''
    [devbkc,ehl_presi,omr1]='641222 642681'
    [devbkc,iot_joule,omr1]='595813'
    [devbkc,icl_presi,omr1]='615635'
    [devbkc,icl_presi_kbl]='627568'
    [devbkc,icl_presi_apl,omr1]='615118'
    [devbkc,tgl_presi,omr1]='621047'
    [devbkc,yocto]=''
    [devbkc,all,p]='638768'
    [devbkc,gordon_peak,p]='628712'
    [devbkc,gordon_peak_acrn,p]='628712'
    [mainlinetracking,gordon_peak,p]='628712 648537'
    [mainlinetracking,gordon_peak_acrn,p]='628712 648537'
    [4.19lts,gordon_peak_acrn,p]=''
    [4.19lts,gordon_peak_acrn,pmr0]='693173'
    [4.19lts,gordon_peak,p]='693114'
    [4.19lts,clk,p]=''
    [4.19lts,gordon_peak,q]='664292 699298 698547'
    [4.19lts,gordon_peak,r]=''
    [devbkc,kbl_rvp,p]=''
    [devbkc,ehl_presi,p]='633074'
    [devbkc,icl_presi,p]='615635'
    [devbkc,icl_presi_kbl,p]='627568'
    [devbkc,icl_presi_apl,p]='615118'
    [devbkc,tgl_presi,p]='621047'
    [4.9bkc,all,omr1]=''
    [4.9bkc,gordon_peak,omr1]=''
    [4.9bkc,yocto]=''
    [4.14bkc,all,omr1]=''
    [4.14bkc,gordon_peak,omr1]='635550 633649 630995 630096'
    [4.14bkc,icl_presi_kbl,omr1]='615635 620156'
    [4.14bkc,kbl_rvp,omr1]=''
    [4.14bkc,all,p]=''
    [4.14bkc,gordon_peak,p]='645780 647218'
    [4.14bkc,icl_presi_kbl,p]='615635 620156'
    [4.14bkc,kbl_rvp,p]=''
)

declare -A PK_MAPTO_ANDROID_BRANCHES=(
    [devbkc,gordon_peak,omr1]='omr1'
    [devbkc,kbl_rvp,omr1]='omr1'
    [devbkc,ehl_presi,omr1]='omr1'
    [devbkc,icl_presi,omr1]='omr1'
    [devbkc,icl_presi_kbl,omr1]='omr1'
    [devbkc,icl_presi_apl,omr1]='omr1'
    [devbkc,tgl_presi,omr1]='omr1'
    [devbkc,gordon_peak,p]='master'
    [devbkc,gordon_peak_acrn,p]='master'
    [mainlinetracking,gordon_peak,p]='master'
    [mainlinetracking,gordon_peak_acrn,p]='master'
    [4.19lts,gordon_peak,p]='master'
    [4.19lts,clk,p]='master_celadon'
    [4.19lts,gordon_peak,q]='masterq'
    [4.19lts,gordon_peak,r]='masterr'
    [4.19lts,gordon_peak,s]='masters'
    [4.19lts,gordon_peak,t]='mastert'
    [4.19lts,gordon_peak_acrn,p]='pmr0_bxtp_ivi_acrn_stable'
    [4.19lts,gordon_peak_acrn,pmr0]='pmr0_bxtp_ivi_acrn_stable'
    [devbkc,kbl_rvp,p]='master'
    [devbkc,ehl_presi,p]='master'
    [devbkc,icl_presi,p]='master'
    [devbkc,icl_presi_kbl,p]='master'
    [devbkc,icl_presi_apl,p]='master'
    [devbkc,tgl_presi,p]='master'
    [4.9bkc,gordon_peak,omr1]='omr1_bxtp_ivi_stable'
    [4.9bkc,iot_joule,omr1]='brillo'
    [4.14bkc,gordon_peak,omr1]='omr1'
    [4.14bkc,icl_presi_kbl,omr1]='master'
    [4.14bkc,kbl_rvp,omr1]='omr1'
    [4.14bkc,gordon_peak,p]='master'
    [4.14bkc,icl_presi_kbl,p]='master'
    [4.14bkc,kbl_rvp,p]='master'
)

declare -A ANDROID_REPO_BRANCHES=(
    [masterr]='android/r/bxtp_ivi/master'
    [masters]='android/s/bxtp_ivi/master'
    [mastert]='android/t/bxtp_ivi/master'
    [masterq]='android/q/mr0/stable/bxtp_ivi/master'
    [master]='android/p/mr0/stable/bxtp_ivi/master'
    [master_celadon]='android/celadon'
    [brillo]='brillo/o/mr1/master'
    [omr1]='android/o/mr1/master'
    [omr1_bxtp_ivi_stable]='android/o/mr1/maint/bxtp_ivi'
    [pmr0_bxtp_ivi_acrn_stable]='android/p/mr0/stable/bxtp_ivi_acrn'
)

declare -A ANDROID_INIT_MANIFEST=(
    [masterr]='r1'
    [masters]='r1'
    [masterq]='r1'
    [master]='r1'
    [master_celadon]='celadon'
    [brillo]=''
    [omr1]='r0'
    [omr1_bxtp_ivi_stable]='bxtp_ivi'
    [pmr0_bxtp_ivi_acrn_stable]='bxtp_ivi_acrn'
)

declare -A ANDROID_KERNEL=(
    [devbkc,gordon_peak]='kernel/dev'
    [devbkc,gordon_peak_acrn]='kernel/dev'
    [mainlinetracking,gordon_peak]='kernel/mainline-tracking'
    [mainlinetracking,gordon_peak_acrn]='kernel/mainline-tracking'
    [4.19lts,gordon_peak]='kernel/lts2018'
    [4.19lts,clk]='kernel/project-celadon'
    [4.19lts,gordon_peak_acrn]='kernel/lts2018'
    [devbkc,kbl_rvp]='kernel/dev'
    [devbkc,ehl_presi]='kernel/dev'
    [devbkc,iot_joule]='hardware/bsp/kernel/intel/broxton-v4.9'
    [devbkc,icl_presi]='kernel/icl'
    [devbkc,icl_presi_kbl]='kernel/icl'
    [devbkc,icl_presi_apl]='kernel/icl'
    [devbkc,tgl_presi]='kernel/dev'
    [4.9bkc,gordon_peak]='kernel/bxt'
    [4.9bkc,iot_joule]='hardware/bsp/kernel/intel/broxton-v4.9'
    [4.14bkc,gordon_peak]='kernel/4.14'
    [4.14bkc,icl_presi_kbl]='kernel/4.14'
    [4.14bkc,kbl_rvp]='kernel/4.14'
)

declare -A ANDROID_CONFIG=(
    [mainlinetracking]='kernel/config-mainline-tracking'
    [4.19lts]='kernel/config-lts/lts2018'
    [devbkc]='kernel/config'
    [4.9bkc]='kernel/config-lts/v4.9'
    [4.14bkc]='kernel/config-lts/v4.14'
)

declare -A PK_CONFIG_DIR_ANDROID=(
    [devbkc,gordon_peak]="/out/target/product/gordon_peak/obj/kernel/"
    [devbkc,gordon_peak_acrn]="/out/target/product/gordon_peak_acrn/obj/kernel/"
    [mainlinetracking,gordon_peak]="/out/target/product/gordon_peak/obj/kernel/"
    [mainlinetracking,gordon_peak_acrn]="/out/target/product/gordon_peak_acrn/obj/kernel/"
    [4.19lts,gordon_peak]="/out/target/product/gordon_peak/obj/kernel/"
    [4.19lts,gordon_peak_acrn]="/out/target/product/gordon_peak_acrn/obj/kernel/"
    [4.19lts,clk]="out/target/product/clk/obj/kernel"
    [devbkc,ehl_presi]="/out/target/product/ehl_presi/obj/kernel/"
    [4.9bkc,gordon_peak]="/out/target/product/gordon_peak/obj/kernel/"
    [4.14bkc,gordon_peak]="/out/target/product/gordon_peak/obj/kernel/"
)

declare -A PK_CONFIG_DIR=(
    [devbkc,gordon_peak]="${ANDROID_CONFIG[devbkc]}/bxt/android/embargoed"
    [devbkc,gordon_peak_acrn]="${ANDROID_CONFIG[devbkc]}/bxt/android/embargoed"
    #[mainlinetracking,gordon_peak]="${ANDROID_CONFIG[mainlinetracking]}/bxt/android/non-embargoed"
    #[mainlinetracking,gordon_peak_acrn]="${ANDROID_CONFIG[mainlinetracking]}/bxt/android/non-embargoed"
    [mainlinetracking,gordon_peak]="${ANDROID_CONFIG[mainlinetracking]}/bxt/android"
    [mainlinetracking,gordon_peak_acrn]="${ANDROID_CONFIG[mainlinetracking]}/bxt/android"
    [4.19lts,gordon_peak]="${ANDROID_CONFIG[4.19lts]}/bxt/android/non-embargoed"
    [4.19lts,gordon_peak_acrn]="${ANDROID_CONFIG[4.19lts]}/bxt/android/non-embargoed"
    [4.19lts,clk]=""
    [devbkc,kbl_rvp]="${ANDROID_CONFIG[devbkc]}/kbl/android/embargoed"
    [devbkc,ehl_presi]="${ANDROID_CONFIG[devbkc]}/ehl/android/embargoed"
    [devbkc,iot_joule]="${ANDROID_CONFIG[devbkc]}/bxt/iot/embargoed"
    [devbkc,icl_presi]="${ANDROID_CONFIG[devbkc]}/icl/android/embargoed"
    [devbkc,icl_presi_kbl]="${ANDROID_CONFIG[devbkc]}/icl/android/embargoed"
    [devbkc,icl_presi_apl]="${ANDROID_CONFIG[devbkc]}/bxt/android/embargoed"
    [devbkc,tgl_presi]="${ANDROID_CONFIG[devbkc]}/tgl/android/embargoed"
    [4.9bkc,gordon_peak]="${ANDROID_CONFIG[4.9bkc]}/bxt/android"
    [4.9bkc,iot_joule]="${ANDROID_CONFIG[4.9bkc]}/bxt/iot"
    [4.14bkc,gordon_peak]="${ANDROID_CONFIG[4.14bkc]}/bxt/android"
    [4.14bkc,icl_presi_kbl]="${ANDROID_CONFIG[4.14bkc]}/kbl/android"
    [4.14bkc,kbl_rvp]="${ANDROID_CONFIG[4.14bkc]}/kbl/android"
)

declare -A ANDROID_CONFIG_DIR_IN_MIXIN=(
    [devbkc,gordon_peak]='kernel/config/bxt/android/embargoed'
    [devbkc,gordon_peak_acrn]='kernel/config/bxt/android/embargoed'
    #[mainlinetracking,gordon_peak]='kernel/config/bxt/android/non-embargoed'
    #[mainlinetracking,gordon_peak_acrn]='kernel/config/bxt/android/non-embargoed'
    [mainlinetracking,gordon_peak]="${ANDROID_CONFIG[mainlinetracking]}/bxt/android"
    [mainlinetracking,gordon_peak_acrn]="${ANDROID_CONFIG[mainlinetracking]}/bxt/android"
    [4.19lts,gordon_peak]='kernel/config-lts/lts2018/bxt/android/non-embargoed'
    [4.19lts,gordon_peak_acrn]='kernel/config-lts/lts2018/bxt/android/non-embargoed'
    [4.19lts,clk]=''
    [devbkc,kbl_rvp]='kernel/config/kbl/android/embargoed'
    [devbkc,ehl_presi]='kernel/config/ehl/android/embargoed'
    [devbkc,iot_joule]='device/intel/joule'
    [devbkc,icl_presi]='kernel/config/icl/android/embargoed'
    [devbkc,icl_presi_kbl]='kernel/config/icl/android/embargoed'
    [devbkc,icl_presi_apl]='kernel/config/bxt/android/embargoed'
    [devbkc,tgl_presi]='kernel/config/tgl/android/embargoed'
    [4.9bkc,gordon_peak]='kernel/config-lts/v4.9/bxt/android'
    [4.9bkc,iot_joule]='device/intel/joule'
    [4.14bkc,gordon_peak]='kernel/config-lts/v4.14/bxt/android'
    [4.14bkc,icl_presi_kbl]='kernel/config-lts/v4.14/kbl/android'
    [4.14bkc,kbl_rvp]='kernel/config-lts/v4.14/kbl/android'
)

declare -A ANDROID_CONFIG_FILE=(
    [gordon_peak]='x86_64_defconfig'
    [gordon_peak_acrn]='x86_64_defconfig'
    [clear_linux_bm]='x86_64_defconfig'
    [clear_linux_laag]='x86_64_defconfig'
    [clear_linux_sos]='x86_64_defconfig'
    [gordon_peak_omr1]='x86_64_defconfig'
    [ehl_presi]='x86_64_defconfig'
    [iot_joule]='joule.kconf'
    [icl_presi]='x86_64_defconfig'
    [icl_presi_kbl]='x86_64_defconfig'
    [kbl_rvp]='x86_64_defconfig'
    [icl_presi_apl]='x86_64_defconfig'
    [tgl_presi]='x86_64_defconfig'
    [clk]=''
)

declare -A ANDROID_SUPPORTED=(
    [devbkc,gordon_peak]=true
    [devbkc,gordon_peak_acrn]=true
    [mainlinetracking,gordon_peak]=true
    [mainlinetracking,gordon_peak_acrn]=true
    [4.19lts,gordon_peak]=true
    [4.19lts,gordon_peak_acrn]=true
    [4.19lts,clk]=true
    [devbkc,kbl_rvp]=true
    [devbkc,ehl_presi]=true
    [devbkc,iot_joule]=true
    [devbkc,icl_presi]=true
    [devbkc,icl_presi_kbl]=true
    [devbkc,icl_presi_apl]=true
    [devbkc,tgl_presi]=true
    [4.9bkc,gordon_peak]=true
    [4.9bkc,iot_joule]=true
    [4.14bkc,gordon_peak]=true
    [4.14bkc,icl_presi_kbl]=true
    [4.14bkc,kbl_rvp]=true
)

declare -A ANDROID_MAKE_TARGETS=(
    [mainlinetracking,gordon_peak]='droid dist'
    [mainlinetracking,gordon_peak_acrn]='acrn_image'
    [4.19lts,gordon_peak]='droid dist'
    [4.19lts,gordon_peak_acrn]='acrn_image'
    [4.19lts,clk]='SPARSE_IMG=true KERNELFLINGER_SUPPORT_USB_STORAGE=true'
    [devbkc,gordon_peak]='droid dist DEV_BKC_KERNEL=true'
    [devbkc,gordon_peak_acrn]='acrn_image'
    [devbkc,kbl_rvp]='droid dist DEV_BKC_KERNEL=true'
    [devbkc,ehl_presi]='droid dist'
    [devbkc,iot_joule]='dist'
    [devbkc,icl_presi]='gptimage'
    [devbkc,icl_presi_kbl]='droid dist publish_ci'
    [devbkc,icl_presi_apl]='droid dist publish_ci'
    [devbkc,tgl_presi]='gptimage'
    [4.9bkc,gordon_peak]='droid dist'
    [4.9bkc,iot_joule]='dist'
    [4.14bkc,gordon_peak]='droid dist K414_KERNEL=true'
    [4.14bkc,icl_presi_kbl]='droid dist publish_ci K414_KERNEL=true'
    [4.14bkc,kbl_rvp]='droid dist K414_KERNEL=true'
)

ANDROID_ARTIFACTORY_BASE="https://mcg-depot.intel.com/artifactory/cactus-absp-jf/build/eng-builds"

# for quiltdiff tracking tool
QUILTDIFF_URI="otcpkt.bj.intel.com:9000"
TRIGGER_QUILTDIFF_BASE_URL="http://${QUILTDIFF_URI}/trigger/qd/"
QUILTDIFF_CHGLST_BASE_URL="http://${QUILTDIFF_URI}/json/"

# for CI bridge jenkins job
CIB_JENKINS_BASE_URL="https://cbjenkins-ba.devtools.intel.com/teams-satg-aee-android-ci/job/satg-aee-android-ci/job"
CIB_JENKINS_USER="sys_oak"
CIB_JENKINS_TOKEN="$SYS_OAK_CRED_JENKINS_API"
declare -A ANDROID_TOKEN_PARAMS=(
    [4.19lts_t]="Auto_CI_merge_bridge_t"
    [4.19lts_s]="Auto_CI_merge_bridge_s"
)
declare -A CIB_JOBS=(
    [devbkc]="Auto_CI_merge_bridge_for_kernel_dev_bkc"
    [mainline-tracking]="Auto_CI_merge_bridge_for_kernel_mainline"
    [4.19lts]="Auto_CI_merge_bridge_for_kernel_lts_bkc_2018"
    [4.19lts_q]="Auto_CI_merge_bridge_for_kernel_lts_bkc_2018-android_q"
    [4.19lts_r]="Auto_CI_merge_bridge_for_kernel_lts_bkc_2018-android_r"
    [4.19lts_s]="Auto_CI_merge_bridge_for_kernel_lts_bkc_2018-android_s"
    [4.19lts_t]="Auto_CI_merge_bridge_for_kernel_lts_bkc_2018-android_t"
    [4.14bkc]="Auto_CI_merge_bridge_for_kernel_lts_bkc_4_14"
    [4.9bkc]="Auto_CI_merge_bridge_for_kernel_lts_bkc"
)
declare -A CIB_JOB_PARAMS=(
    [devbkc]="MASTER_DEP_CHANGE_IDS O_MR1_DEP_CHANGE_IDS"
    [mainline-tracking]="MASTER_DEP_CHANGE_IDS"
    [4.19lts]="MASTER_DEP_CHANGE_IDS PMR0_BXTP_IVI_STABLE_DEP_CHANGE_IDS PMR0_BXTP_IVI_ACRN_STABLE_DEP_CHANGE_IDS"
    [4.19lts_q]="MASTER_DEP_CHANGE_IDS"
    [4.19lts_r]="MASTER_DEP_CHANGE_IDS"
    [4.19lts_s]="MASTER_DEP_CHANGE_IDS"
    [4.19lts_t]="MASTER_DEP_CHANGE_IDS"
    [4.14bkc]="MASTER_DEP_CHANGE_IDS O_MR1_DEP_CHANGE_IDS"
    [4.9bkc]="OMR1_BXTP_IVI_MAINT_DEP_CHANGE_IDS"
)

# release tag kernel version pattern
RTAG_KV_PATTERN="v[0-9]*[0-9]"
# release tag timestamp pattern
RTAG_TS_PATTERN="[12][0-9][01][0-9][0-3][0-9]T"
RTAG_TS_PATTERN_FULL="[12][0-9][01][0-9][0-3][0-9]T[0-9]*Z"
# release tag glob patterns
declare -A RELTAG_PATTERNS=(
    [devbkc]="dev-bkc-${RTAG_KV_PATTERN}-android-embargoed-${RTAG_TS_PATTERN}"
    [mainline-tracking]="mainline-tracking-${RTAG_KV_PATTERN}-android-${RTAG_TS_PATTERN}"
    [4.19lts]="lts-v4.19*[0-9]-android-${RTAG_TS_PATTERN_FULL}"
    [4.19lts_q]="lts-v4.19*[0-9]-android_q-${RTAG_TS_PATTERN_FULL}"
    [4.19lts_r]="lts-v4.19*[0-9]-android_r-${RTAG_TS_PATTERN_FULL}"
    [4.19lts_s]="lts-v4.19*[0-9]-android_s-${RTAG_TS_PATTERN_FULL}"
    [4.19lts_t]="lts-v4.19*[0-9]-android_t-${RTAG_TS_PATTERN_FULL}"
    [4.14bkc]="lts-v4.14*[0-9]-android-${RTAG_TS_PATTERN}"
    [4.9bkc]="lts-v4.9*[0-9]-android-${RTAG_TS_PATTERN}"
)

declare -A REPO_REMOTES=(
    [tracker]="tracker"
    [kernel-bkc]="origin"
    [lts2018]="lts2018"
    [lts2019]="lts2019"
    [kernel-staging]="staging"
    [ikt-po]="ikt-po"
)

# kernel repo. urls
declare -A KERNEL_REPOS=(
    [tracker]="ssh://git-amr-4.devtools.intel.com/kernel-coe-tracker"
    [kernel-bkc]="ssh://git-amr-4.devtools.intel.com/kernel-bkc"
    [lts2018]="https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git"
    [lts2019]="https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git"
    [kernel-config]="https://github.com/intel-innersource/os.linux.kernel.kernel-config.git"
    [kernel-staging]="https://github.com/intel-innersource/os.linux.kernel.kernel-staging.git"
    [kernel-lts-staging]="https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git"
    [kernel-dev-quilt]="https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt.git"
    [kernel-lts-quilt]="https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt.git"
    [ikt-po]="ssh://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/ikt-yocto-poweron.git"
    [iotg-next]="https://github.com/intel-innersource/os.linux.kernel.iot-next.git"
)


#
# Functions
#

## die
#
# Print specified error messages and then exit with an exit code of 1
#
die() {
	echo >&2
	warn "$@"
	exit 1
}


## warn
#
# Print an error message to stderr
#
warn() {
	for line in "$@"; do
		echo "$line" >&2
	done
}

## git_project
#
# Clone and/or update given repo.
#
git_project() {
	declare scm=$1
	declare scmdir=$2
	declare branch=$3

	if ! [ -d $scmdir ] ; then
		mkdir -p $scmdir
		if [ -d /mirrors/$(basename $scm) ] ; then
			rsync -avzq /mirrors/$(basename $scm)/ $scmdir/
		else
			git clone $scm $scmdir
		fi
	fi
	pushd $scmdir
	for r in $(git remote) ; do
		git remote prune $r
	done
	git fetch --all --tags
	git reset --hard
	git checkout origin/$branch -b $branch  || \
		git checkout $branch
	git reset --hard origin/$branch
	git clean -xdff
	popd
}

git_project_tag() {
	declare scm=$1
	declare scmdir=$2
	declare tag=$3

	if ! [ -d $scmdir ] ; then
		mkdir -p $scmdir
		if [ -d /mirrors/$(basename $scm) ] ; then
			rsync -avzq /mirrors/$(basename $scm)/ $scmdir/
		else
			git clone $scm $scmdir
		fi
	fi
	pushd $scmdir
	for r in $(git remote) ; do
		git remote prune $r
	done
	git fetch --all --tags
	git reset --hard
	git clean -xdff
	git checkout $tag || \
	popd
}

## add_scm
#
# add a remote and fetch
#
add_scm() {
	declare remote=$1
	declare remote_scm=$2

	git remote add $remote $remote_scm || :
	git fetch $remote --tags --force --prune
}

## init_kernel_bkc
#
# Clone the kernel-bkc project and add the kernel-coe-tracker remote.
# Do a git-fetch for both remotes.
#
#
init_kernel_bkc() {
	git_project ssh://git-amr-4.devtools.intel.com/kernel-bkc \
		$working_dir/kernel-bkc master || \
		die "Unable to update kernel-bkc"
	git_project ssh://git-amr-4.devtools.intel.com/kernel-config \
		$working_dir/kernel-config master || \
		die "Unable to update kernel-config"
	git_project ssh://git-amr-4.devtools.intel.com/kernel-dev-quilt \
		$working_dir/kernel-dev-quilt mainline-tracking || \
		die "Unable to update kernel-dev-quilt"
}

init_kernel_lts_staging() {
	git_project https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git \
		$working_dir/kernel-lts-staging master || \
		die "Unable to update kernel-lts-staging"
		#temp until config gets placed on source
	git_project https://github.com/intel-innersource/os.linux.kernel.kernel-config.git \
		$working_dir/kernel-config master || \
		die "Unable to update kernel-config"
	git_project https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt.git \
		$working_dir/kernel-dev-quilt lts-4.19/base || \
		die "Unable to update kernel-dev-quilt"
	git_project https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve.git \
        $working_dir/kernel-lts-cve 4.19 || \
        die "Unable to update kernel-lts-cve"
	git_project https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt.git \
        $working_dir/kernel-lts-quilt master || \
        die "Unable to update kernel-lts-quilt"
}

kernel_release_lts_staging() {
	git_project https://github.com/intel/linux-intel-quilt.git \
		$working_dir/linux-intel-quilt 4.19/base || \
		die "Unable to update linux-intel-quilt"

}



## base_version
#
# Capture the base kernel version for the $domain branch and verify
# it is the same as or a descendent of $kernel_verison. If so, return
# $domain_version.
#
base_version() {
	declare domain=$1
	declare stable_kernel=$2
	declare kernel_version=$3
	declare domain_version

	domain_version=$(git merge-base $domain $stable_kernel)
	if [ "$kernel_version" = "$domain_version" ] || \
		git merge-base --is-ancestor $domain_version $kernel_version
	then
		echo $domain_version
	fi
}

## git_diff
#
# Use git-diff to compare a merge branch with a rebasing/linear branch
# and verify that they are the same. If there are differences, drop
# into a subshell and allow the user to do some repair before exiting
# the subshell to continue.
#
git_diff() {
	if ! git diff --exit-code $1 $2 > /dev/null; then
		warn "$1 and $2 do not match!"
		warn "Please resolve diffs and exit shell to continue"
		bash_subshell "FIX DIFFS"
	fi
}

## checkout
#
# Check out a local (target) instance of a (source) branch.
#
checkout() {
	declare source=$1
	declare target=$2

	git checkout -B $target $source || \
		git checkout $source || \
		die "Unable to checkout $source"
	git reset --hard || \
		die "Unable to reset local branch"
}

## checkout_local
#
# Check out a local (target) branch.
#
checkout_local() {
	declare target=$1

	git checkout $target || die "Unable to checkout $target"
}

## checkout_remote
#
# Check out a remote (target) branch to detached HEAD
#
checkout_remote() {
	declare source=$1

	git checkout $source || die "Unable to checkout $source"
}

## reset_remote
#
# Hard reset to the source
#
reset_remote() {
	declare source=$1

	git reset --hard $source || die "Unable to reset $source"
}

## sha_of_tip
#
# Capture the SHA that is the tip of the specified branch.
# If the branch does not exist, we exit with an error message.
#
sha_of_tip() {
	declare branch=$1
	declare tip

	tip=`git rev-parse --verify $branch 2> /dev/null`
	if [ $? -ne 0 ]; then
		die "Invalid branch name: $branch"
	fi
	git log -n1 --format=%H $tip
}

## cherry_pick
#
# Cherry-pick the new patches to the rebasing branch.
#
cherry_pick() {
	declare rebasing_base=$1
	declare rebasing_kernel=$2
	declare count
	shift; shift

	# Initialize the branch to rebasing_base
	git checkout ${rebasing_kernel} || \
		die "Unable to checkout ${rebasing_kernel}"
	git reset --hard ${rebasing_base} || \
		die "Failed to reset ${rebasing_kernel} to ${rebasing_base}"

	# Abort of there is nothing to cherry-pick
	count=$(git rev-list -n 1 --count $1)
	if [ "$count" == "0" ]; then
		return
	fi

	# Cherry-pick the desired commits
	for commit in "$@"; do
		if ! git cherry-pick ${commit}; then
			warn "Failed to cherry-pick ${commit} to " \
				"${rebasing_kernel}"
			warn "Please resolve conflicts and exit shell " \
				"to continue"
			bash_subshell "FIX CHERRY-PICK"
		fi
	done
}

## resolve_conflicts
#
# Automatically resolve a merge conflict, when possible, by checking
# out the conflicted files from a reference branch. When it is not
# possible to resolve the conflict automatically, drop to a prompt
# and allow the user to take care of it.
#
resolve_conflicts() {
	declare reference=$1
	declare prompt=$2
	declare warning=$3
	declare files

	files=$(git status --porcelain | grep '^UU ' | sed 's/^UU //')
	if [ -n "$files" ]; then
		git checkout $reference $files
	fi
	if git status --porcelain | egrep -v '^[ACDMR] '; then
		warn "$warning"
		warn "Please resolve conflicts. Exit shell to continue"
		bash_subshell $prompt
	fi
	git commit --no-edit # In case we forget...
}

## merge_branch
#
# Merge the domain branch into the non-rebasing branch. Note that we
# merge to the merge_sha as determined by the last commit sha that
# is passed in the commits string. This accounts for the cases where
# we do not want to merge the entire branch (e.g. android-4.9.y).
#
merge_branch() {
	declare kernel=$1
	declare domain=$2
	declare merge_point=$3
	shift; shift; shift
	declare commits="$@"

	git checkout ${kernel} || die "Unable to checkout ${kernel}"
	if ! git merge --no-ff $merge_point --log -m \
	    "Merge ${domain} into ${kernel}"; then
	    resolve_conflicts "rebasing/${kernel}" "FIX MERGE" \
		"Failure to merge ${branch} into ${kernel}"
	fi
}

## check_merged
#
# Check to see if a branch has been fully merged. If it there
# are patches to be merged, return a list of commits that need
# to be cherry-picked.
#
# Note that check_merged uses the git-cherry command. The commit
# SHAs prefixed with -. Those prefixed with + do not - these are
# the ones we care about. This function filters them out and returns
# a list of SHAs for commits that are new and not included yet in
# the release.
#
check_merged() {
	declare base_branch=$1
	declare domain=$2
	declare domain_tip
	declare merge_base
	declare new_commits=
	declare all_commits=

	commits=`git cherry $base_branch $domain` || \
		die "Failed to run: git cherry $base_branch $domain"
	if [ -n "$commits" ]; then
		commits="$(echo $commits | tr '\n' ' ')"
		while [ -n "$commits" ]; do
			sign=${commits%% *}
			commits=${commits#* }
			commit=${commits%% *}
			commits=${commits#* }
			if [ -z "$all_commits" ]; then
				all_commits=$commit
			else
				all_commits="${all_commits} $commit"
			fi
			[ "$sign" = "+" ] || continue
			if [ -z "$new_commits" ]; then
				new_commits=$commit
			else
				new_commits="${new_commits} $commit"
			fi
		done
		echo "$new_commits"
	fi
}

log_run_cmd() {
	declare label=$1
	shift

	echo "($label) $@" >> $working_dir/build.log
	echo "($label) $@" >> $working_dir/build.err
	$@ 1> >(tee -a $working_dir/build.log) 2> >(tee -a $working_dir/build.err)
	result=$?
	if [[ $result != 0 ]];then
	    echo "there is error: please check build.log and build.err"
	    exit $result
	fi
	return $result
}

## check_build
#
# Check to see if a branch will build
#
check_build(){
	declare local_branch=$1
	declare os_type=$2
	declare arch_type=$3
	declare soc_config=$4
	shift; shift; shift;

	checkout_local $local_branch
	echo "check if it will build $os_type"

	if [ "$arch_type" == "arm64" ] ; then
		make_cmd="make ARCH=$arch_type CROSS_COMPILE=aarch64-linux-gnu-"
	else
		make_cmd="make ARCH=$arch_type CROSS_COMPILE=/opt/poky/2.4.2/sysroots/x86_64-pokysdk-linux/usr/bin/x86_64-poky-linux/x86_64-poky-linux-"
		[[ $local_branch == *android_r* ]] && make_cmd="make ARCH=$arch_type CC=/opt/clang/clang-r383902b/bin/clang"
		[[ $local_branch == *android_s* ]] && make_cmd="make ARCH=$arch_type CC=/opt/clang/clang-r416183b1/bin/clang"
		[[ $local_branch == *android_t* ]] && make_cmd="make ARCH=$arch_type CC=/opt/clang/clang-r450784d/bin/clang"
		[[ $local_branch == *android_u* ]] && make_cmd="make ARCH=$arch_type CC=/opt/clang/clang-r487747c/bin/clang"
	fi

	if [ -n "$soc_config" ] ; then
		# use merge_config to bring all fragments together
		# just merge, don't try to do any make *config updates
		echo "Merging $soc_config $@"
		log_run_cmd $local_branch $make_cmd distclean
		log_run_cmd $soc_config scripts/kconfig/merge_config.sh $soc_config $@
		[[ $- =~ e ]] ; errexit=$? # save error exit state restore later
		set +e
		log_run_cmd $local_branch $make_cmd -j $(nproc)
		ret=$?
		(( $errexit )) && set +e
	else
		for config in allyesconfig allmodconfig allnoconfig ; do
			log_run_cmd $local_branch $make_cmd distclean
			log_run_cmd $local_branch $make_cmd $config
			[[ $- =~ e ]] ; errexit=$? # save error exit state restore later
			set +e
			log_run_cmd $local_branch $make_cmd -j $(nproc)
			save_ret=$?
			(( $errexit )) && set +e
			if [ $save_ret -ne 0 ]; then
				ret=$save_ret
			fi
		done
	fi
	return $ret
}

## commit local
#
# commit all local changes to the config
# presumes we are on the correct local branch
#
commit_local(){
	declare msg=$1

	if [ "$(git diff --name-status)" ] ; then
		git commit -as -m "$msg"
	fi
}

commit_local_no_check(){
    declare msg=$1
    git add -A
    git commit -sm "$msg"
}

## update_config
#
# udpate the config
#
# presume we are on the correct kernel_dir branch
# and config_dir branch.
#
update_config(){
	declare arch_type=$1
	declare soc_config=$2

	if [ "$arch_type" == "arm64" ] ; then
		make_cmd="make ARCH=$arch_type CROSS_COMPILE=aarch64-linux-gnu-"
	else
		make_cmd="make ARCH=$arch_type CROSS_COMPILE=/opt/poky/2.4.2/sysroots/x86_64-pokysdk-linux/usr/bin/x86_64-poky-linux/x86_64-poky-linux-"
		#make_cmd="make ARCH=$arch_type"
	fi
	make_cmd_2="make mrproper"
	log_run_cmd $soc_config $make_cmd_2
	cp $soc_config .config
	log_run_cmd $soc_config $make_cmd olddefconfig
	cp .config $soc_config

}

update_android_config(){
    Android_config_loc=$1
    Kernel_config_loc=$2
    soc_name=$3
    cp $Android_config_loc.config $Kernel_config_loc/cov_$soc_name
}

update_config_timestamp(){
    declare arch_type=$1
    declare soc_config=$2
    declare local_branch=$3

    if [ "$arch_type" == "arm64" ] ; then
        make_cmd="make ARCH=$arch_type CROSS_COMPILE=aarch64-linux-gnu-"
    else
        make_cmd="make ARCH=$arch_type CROSS_COMPILE=/opt/poky/2.4.2/sysroots/x86_64-pokysdk-linux/usr/bin/x86_64-poky-linux/x86_64-poky-linux-"
        [[ $local_branch == *android_r* ]] && make_cmd="make ARCH=$arch_type CC=/opt/clang/clang-r383902b/bin/clang"
        [[ $local_branch == *android_s* ]] && make_cmd="make ARCH=$arch_type CC=/opt/clang/clang-r416183b1/bin/clang"
        [[ $local_branch == *android_t* ]] && make_cmd="make LLVM=1 ARCH=$arch_type CC=/opt/clang/clang-r450784d/bin/clang HOSTCC=/opt/clang/clang-r450784d/bin/clang"
    fi
    make_cmd_2="make mrproper"
    log_run_cmd $soc_config $make_cmd_2
    sed -i -e "/^CONFIG_LOCALVERSION/ s/CONFIG_LOCALVERSION=.*/CONFIG_LOCALVERSION=\"-$datetime\"/ " $soc_config 
    cp $soc_config .config
    log_run_cmd $soc_config $make_cmd olddefconfig
    cp .config $soc_config

}

## tag
#
# Tag the current HEAD
#
tag(){
	declare tag_name=$1
	declare msg=$2

	git tag -a $tag_name HEAD -m "$msg"
}

## push_remote
#
# Push to the remote branch
#
push_remote(){
	declare remote_name=$1
	declare local_branch=$2
	declare remote_branch=$3
	declare force_push=$4

	if [ "$force_push" == "" ] ; then
		git push $remote_name $local_branch:refs/heads/$remote_branch
		echo "RD: git push $remote_name $local_branch:refs/heads/$remote_branch"
	else
		git push -f $remote_name $local_branch:refs/heads/$remote_branch
		echo "RD: git push -f $remote_name $local_branch:refs/heads/$remote_branch"
	fi
}

## rebase_local_remote
#
# Rebase local to the remote branch
#
rebase_local_remote(){
	declare remote_name=$1
	declare local_branch=$2
	declare remote_branch=$3

	git rebase $remote_name/$remote_branch $local_branch
}

## push_tag
#
# Push tage to the remote
#
push_tag(){
	declare remote_name=$1
	declare tag_name=$2

	echo "RD: git push $remote_name $tag_name"
	git push $remote_name $tag_name
}

## date_stamp
#
# get the date string, week, and kernel version
#
# Return values
# $3=date_string
# $4=week.day
# $5=kernel_version
#
date_stamp(){
	declare remote_branch=$1
	declare major_kernel_version=$2

	#d=$(git log -1 --format=%cd --date=local)'+7days'
	git fetch -a
	d=$(git log -1 --format=%cd --date=local $remote_branch)
	eval "$3=$(date -d "$d" +%Yw%V.%w-%H%M%S)"
	eval "$4=$(date -d "$d" +w%V.%w)"
	if [ "$major_kernel_version" == "v4.9" ] ; then
		eval "$5=$(git describe --tags --match "v[0-9].*" $remote_branch | \
			sed -e 's/\(v[0-9]\.[0-9]\{1,2\}\.[0-9]\{1,3\}\).*/\1/')"
	elif [ "$major_kernel_version" == "v4.14" ] ; then
		eval "$5=$(git describe --tags --match "v[0-9].*" $remote_branch | \
			sed -e 's/\(v[0-9]\.[0-9]\{1,2\}\.[0-9]\{1,3\}\).*/\1/')"
	elif [ "$major_kernel_version" == "dev" ] ; then
		eval "$5=$(git describe --tags --match "v[0-9].*" $remote_branch | \
			sed -e 's/\(v[0-9]\.[0-9]\{1,2\}\(-rc[0-9]\{1,2\}\|\)\).*/\1/')"
	elif [ "$major_kernel_version" == "mainline-tracking" ] ; then
		eval "$5=$(git describe --tags --match "v[0-9].*" $remote_branch | \
			sed -e 's/\(v[0-9]\.[0-9]\{1,2\}\(-rc[0-9]\{1,2\}\|\)\).*/\1/')"
	elif [ "$major_kernel_version" == "4.19" ] ; then
		eval "$5=$(git describe --tags --match "*v[0-9].*" $remote_branch | \
			sed -e 's/lts-\(v[0-9]\.[0-9]\{1,2\}\.[0-9]\{1,3\}\).*/\1/')"
	else
		die "Need to update date_stamp for the major kernel release"
	fi
}

## get_kernel_ver
#
# get the upstream kernel version for a branch
#
# arg1: the remote branch from where we want to know the kernel version
# arg2: return variable of kernel version
# arg3: (optional) return variable of the sha1 of kernel version
#
get_kernel_ver() {
    declare tmpfl=/tmp/$(basename $0)-tags.txt
    git log --decorate=full --simplify-by-decoration --pretty=oneline $1 | \
      sed -rn 's/^([0-9a-f]+)\s+\(tag(:\s+|:\s+refs\/tags\/)(v[0-9]+\.[0-9\.rct-]*),*.*$/\3.\1/p' \
        > $tmpfl
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        die "ERROR: get kernel version failed: $1"
    fi
    # output sample:
    #   v4.17-rc7.commit
    #   v4.17-rc6.commit
    #   v4.17-rc5.commit
    #   v4.17-rc4.commit
    #   v4.17-rc3.commit
    #   v4.17-rc2.commit
    #   v4.17-rc1.commit
    #   v4.17.commit
    # or:
    #   v4.14-rc8.commit
    #   v4.14.55.commit
    #   v4.14.54.commit
    #   v4.14.53.commit
    #   v4.14.52.commit
    #   v4.14.51.commit
    #   v4.14.50.commit
    # strip '-rcN' and commit, then sort, the last one is the latest base
    declare kernel_ver
    declare kernel_ver_base=$(\
      sed -r -e 's/-rc[0-9]+//' -e 's/\.[0-9a-f]{4,}$//' $tmpfl | \
        sort -t'.' -k1.2,1n -k2,2n -k3,3n | tail -1)
    # disable errtrace here
    # check if official release(i.e. w/o -rcN) exists
    set +e
    kernel_ver=$(grep -E "^${kernel_ver_base}\.[0-9a-f]{4,}\$" $tmpfl)
    test -z "$kernel_ver" && \
      kernel_ver=$(grep -E "^${kernel_ver_base}-rc[0-9]+" $tmpfl | \
                     sort | tail -1)
    rm -f $tmpfl
    eval "$2=\"${kernel_ver%\.*}\""
    test -n "$3" && \
      eval "$3=\"${kernel_ver##*\.}\""
}

## _cherrypick
#
# private function for cherry-picking patches form gerrit
#
#   option:
#     -d: dryrun, just print patch list
#
#   arg1: <patch_id>[,<patch_id>...]
#   arg2: (optional) file to store cherry-picked patches
#
_cherrypick() {
    declare OPTIND
    declare opt_d
    while getopts "d" opt; do
      case $opt in
        d)
          opt_d=true
          ;;
      esac
    done
    shift $((OPTIND-1))

    test -z "$1" && return

    declare pids="$1"
    declare out=$2

    # gerry query patch information in json format, two constrains:
    #   1. by patch ids("pid1 OR pid2 OR pid3 OR ...")
    #   2. NOT is:closed - which means the patch is NOT merged and NOT
    #                      abandoned
    #
    # output contains types of rows, the first type of rows is the patch
    # info. and the second one(i.e. the last row) is the query summary,
    # which contains the info. such as rowCount
    #FIXME: validate patch id
    declare changes="$(ssh -p 29418 sys_oak@android.intel.com \
                         gerrit query \
                           --format=JSON \
                           --current-patch-set \
                           ${pids//${SUBSEP}/ OR } NOT is:closed 2>/dev/null)"
    if [ $? -ne 0 ]; then
        echo "Gerrit query failed" >&2
        exit 2
    fi
    declare -A projects=()
    declare -A patchsets=()
    while read prj pid pset pref ppnum; do
        test -z "$prj" && continue
        projects[$pid]="$prj"
        patchsets[$pid]="$pset"
        patchrefs[$pid]="$pref"
        parentnum[$pid]="$ppnum"
    done<<EO_DOC
`
python -c "\
import sys, json;\
changes = r\"\"\"${changes}\"\"\";\
patches = [json.loads(l) for l in changes.splitlines()];\
[ sys.stdout.write('%s %s %s %s %d\n' % \
                     (p['project'],\
                      p['number'],\
                      p['currentPatchSet']['number'],\
                      p['currentPatchSet']['ref'],\
                      len(p['currentPatchSet']['parents']) )) \
    for p in patches if 'project' in p ]"
`
EO_DOC

    # cherry-pick patch one by one
    test "$opt_d" != "true" -a -n "$out" && rm -f $out
    for p in ${pids//${SUBSEP}/ }; do
        if [ -z "${projects[$p]}" ]; then
            # skip if the patch is merged or doesn't exist
            test "$opt_d" != "true" && \
              echo "Patch $p doesn't exist or is merged, skipped"
            continue
        fi
        if [ "$opt_d" == "true" ]; then
            echo "${p}/${patchsets[$p]}"
        else
            test -n "$out" && echo "${p}/${patchsets[$p]}" >> $out
            if [ ${parentnum[$p]} -gt 1 ]; then
                # for merge commit
                dl_patch_cmd="/home/jenkins/bin/repo download -b ${projects[$p]} ${patchrefs[$p]}"
            else
                # for normal patch
                dl_patch_cmd="/home/jenkins/bin/repo download -c ${projects[$p]} ${p}/${patchsets[$p]}"
            fi
            echo "Cherry-pick/merge patch: $dl_patch_cmd"
            $dl_patch_cmd
            test $? -eq 0 || exit 3
        fi
    done
}


## cherrypick_patches
#
# cherry-pick android patches from gerrit
#
#   option:
#     -d: dryrun, just print patch list
#
#   arg1: product - devbkc|4.9bkc
#   arg2: soc
#   arg3: dessert
#   arg4: (optional) the file to store cherrypicked patches
#
cherrypick_patches() {
    declare OPTIND
    declare opt_d
    while getopts "d" opt; do
      case $opt in
        d)
          opt_d=true
          ;;
      esac
    done
    shift $((OPTIND-1))

    declare prd=$1
    declare soc=$2
    declare dessert=$3
    declare pids=""
    declare -A handled_patches=()

    patches="${CHERRYPICK_PATCHES[${prd}${SUBSEP}${soc}${SUBSEP}${dessert}]}"
    # iot_joule is for brillo, so no need to apply the patches in "all" list
    test "$soc" != "iot_joule" && \
      patches="${CHERRYPICK_PATCHES["${prd}${SUBSEP}all${SUBSEP}${dessert}"]} $patches"
    # generate the unique ordered patch list
    for p in $patches; do
        # if the patch is already check-picked, skip it
        test -n "${handled_patches[$p]}" && continue
        # add patch in the list, separated by ','
        pids="${pids}${p}${SUBSEP}"
        # register the handled patch to avoid duplication
        handled_patches[$p]=1
    done
    # strip the tailing ','
    pids=${pids%${SUBSEP}}
    test -z "$pids" && return

    # cherry-pick the patches
    if [ "$opt_d" == "true" ]; then
        _cherrypick -d $pids
    else
        _cherrypick $pids $3
    fi
}


## download_android_manifest
#
# download the latest Android manifest of builds
#
#   arg1: product - devbkc|4.9bkc
#   arg2: soc
#   arg3  Android manifest type - <daily|weekly>
#   arg4: output file
#   arg5: dessert
#
download_android_manifest() {
    declare prd=$1
    declare soc=$2
    declare mtype=$3
    declare out=$4
    declare dessert=$5
    declare pids=""

    declare android_branch=${PK_MAPTO_ANDROID_BRANCHES[${prd}${SUBSEP}${soc}${SUBSEP}${dessert}]}
    if [ -z "$android_branch" ]; then
        echo "No android branch is found for $prd $soc"
        exit 4
    fi

    declare manifest_nm
    case "$mtype" in
      weekly)
        if [ "$dessert" == "p"  ];then
           manifest_nm="manifest-generated-r1.xml"
        else
           manifest_nm="manifest-generated.xml"
        fi

        ;;
      daily)
        manifest_nm="manifest-original.xml"
        ;;
      *)
        echo "Please specify the correct manifest type - daily/weekly"
        exit 5
        ;;
    esac

    declare tmp_fl \
            build_base_url \
            latest_build \
            manifest_url
    tmp_fl=/tmp/download_android_manifest.$$
    build_base_url="$ANDROID_ARTIFACTORY_BASE/$android_branch/PSI/$mtype/"
    rm -f $tmp_fl
    wget --no-proxy $build_base_url -O $tmp_fl
    if [ $? -ne 0 ]; then
        echo "wget failed: $build_base_url"
        rm -f $tmp_fl
        exit 6
    fi
    latest_build="$(grep '<a href=\"[0-9]\{4\}' $tmp_fl | \
                      tail -1 | sed 's/^.*>\(.*\)<.*$/\1/')"
    manifest_url="$build_base_url/$latest_build/$manifest_nm"
    rm -f $tmp_fl
    rm -f $out
    mkdir -p ${out%/*}
    wget --no-proxy $manifest_url -O $out
    if [ $? -ne 0 ]; then
        echo "wget failed: $manifest_url"
        exit 6
    fi
}


## setup_android
#
# sync android repositories to the proper revision
#
#   arg1: product - devbkc|4.9bkc|4.14bkc
#   arg2: soc
#   arg3: android manifest type - <latest|daily|weekly>
#   arg4: android repo. root path
#   arg5: android dessert
#   arg6: (optional) manifest file passed to repo as -m <manifest>
#
setup_android() {
    declare prd=$1
    declare soc=$2
    declare mtype=$3
    declare and_root=$4
    declare dessert=$5
    declare manifest=$6
    declare reference=$7

    declare repo_brch="${ANDROID_REPO_BRANCHES[${PK_MAPTO_ANDROID_BRANCHES[${prd}${SUBSEP}${soc}${SUBSEP}${dessert}]}]}"
    if [ -z "$repo_brch" ]; then
        echo "No android repo branch is found for $prd $soc"
        exit 4
    fi

    # setup android tree
    mkdir -p $and_root

    declare repo_opt
    case "$mtype" in
      daily|weekly)
        declare ori_android_manifest="$and_root/.repo/manifests/android-manifest-original.xml"
        download_android_manifest $prd $soc $mtype $ori_android_manifest $dessert
        repo_opt="-m ${ori_android_manifest##*/}"
        ;;
      latest)
        if [ -n "$manifest" ]; then
            repo_opt="-m $manifest"
        else
            declare init_manifest="${ANDROID_INIT_MANIFEST[${PK_MAPTO_ANDROID_BRANCHES[${prd}${SUBSEP}${soc}${SUBSEP}${dessert}]}]}"
            test -n "$init_manifest" && repo_opt="-m $init_manifest"
        fi
        ;;
      *)
        echo "Please specify the correct manifest type - latest/daily/weekly"
        exit 5
        ;;
    esac

    # If we're syncing from a mirror, then add --reference=$reference to
    # $repo_opt.
    if [ $reference ]; then
        repo_opt="$repo_opt --reference=$reference"
    fi

    # clean up android tree
    pushd $and_root
    rm -rf * .repo
    rm -rf *.xml
    rm -rf *
    #/home/jenkins/bin/repo init -u https://github.com/intel-innersource/os.android.bsp-gordon-peak.manifests -b $repo_brch $repo_opt
    /home/jenkins/bin/repo.google init -u https://github.com/intel-innersource/os.android.bsp-gordon-peak.manifests -b $repo_brch $repo_opt --no-clone-bundle
    cp $WORKSPACE/manifests/${MANIFEST_FILE} .repo/manifests/
    /home/jenkins/bin/repo.google init -m ${MANIFEST_FILE} --no-clone-bundle
    #/home/jenkins/bin/repo.google sync -cq -j1 --fail-fast --force-sync
    /home/jenkins/bin/repo.google sync -cq --fail-fast --force-sync
    popd
}

## bash_subshell
#
# Create a subshell with a prompt so that the user can manually fix
# any conflicts that have occured. The "purpose" parameter becomes
# part of the prompt.
#
bash_subshell() {
	export purpose=$1
	bash --rcfile <(cat ~/.bashrc;
		echo 'PS1="\[\033[0;33m\]$purpose$ \[\033[00m\]"')
}

## push_github
#
# Push to gihub remote branch
push_github() {
	declare remote=$1
	declare local_branch=$2
	declare remote_branch=$3
expect << EOF
set timeout 10
set prompt "(%|#|\\$) $"
spawn git push $remote $local_branch:$remote_branch
expect {
	"*delta*" {send "\r";}
	"*done*" {send "\r";}
	"*date*" {send "\r";}
	"*Password for*" {send "${SYS_OAK_CRED_AD}\r";}
	"*Username for*" {send "sys-oak\r";exp_continue}
	}
expect eof
EOF
}

## push_tag_github
#
# Push tag to gihub remote branch
push_tag_github() {
	declare remote_name=$1
	declare tag_name=$2

expect << EOF
set timeout 10
set prompt "(%|#|\\$) $"
spawn git push $remote_name $tag_name
expect {
	"*delta*" {send "\r";}
	"*done*" {send "\r";}
	"*date*" {send "\r";}
	"*Password for*" {send "${SYS_OAK_CRED_AD}\r";}
	"*Username for*" {send "sys-oak\r";exp_continue}
	}
expect eof
EOF
}

## get_sha
#
# get the sha of the last commit
get_sha() {
	# sha for changing kernel version
	# $1 - kernel dir to use
	pushd $1
	sha1=$(git log --pretty=format:%h -n1 --abbrev=8)
	if [ "$sha1" == "" ] ; then exit 1 ; fi
	popd
}

## get_kernelversion
#
# get the kernel version
get_kernelversion() {
	# kernel version
	# $1 - kernel dir to use
	pushd $1
	linux_version=$(make kernelversion)
	if [ "$linux_version" == "" ] ; then exit 1 ; fi
	popd
}

# get_kernel_version
#
# Given a branch, checkout the branch and run make kernelversion.
# Checkout the original branch afterward, making it side-effect free.
function get_kernel_version() {
        local test_branch=$1
        local current_branch_line="$(git branch | grep ^\*)"
	local tag_regex="^\* \(HEAD detached at (.*)\)$"
        # If it's a tag...
        if [[ $current_branch_line =~ $tag_regex ]]; then
                local current_branch=${BASH_REMATCH[1]}
        else
                local current_branch=$(echo $current_branch_line | cut -d ' ' -f2)
        fi
	git fetch -aq
        git checkout -q $test_branch
        make kernelversion
        git checkout -q $current_branch
}

## get_intel_ww
#
# return the intel work week from year, month, and day.
get_intel_ww() {
	declare _year=$1
	declare _month=$2
	declare _day=$3
	# return $4 the ww

	# Date %U option for work week is very close to what intel uses.
	# %U option start on 00 for some years and for other it starts on 01.
	# on the years it starts on 00 we need to add 1 to get the Intel work week.

	_ww=$(date -d "${_year}-${_month}-${_day}" +%U)
	_ww_begin_of_year=$(date -d "${_year}-01-01" +%U)
	_ww_begin_of_next_year=$(date -d "${_year}-01-01 +1years" +%U)

	if [[ "$_ww_begin_of_year" == "00" ]] ; then
		_ww=$(( 10#$_ww + 1 ))
	fi
	if ! [[ "$_ww_begin_of_next_year" == "01" ]] ; then
		_ww=$(( 10#$_ww % 53 ))
		if [[ $_ww -eq 0 ]] ; then
			_ww=01
		fi
	fi
	eval "$4=$(printf %02d $_ww)"
}

## get_ww_string
#
# return the work week string using the staging number
# return the release string using the work week string and staging number
get_ww_string() {
	declare staging_number=$1
	#return $2 date_string
	#return $3 release_string

	if [[ $1 =~ [0-9]{6}-[0-9]{4}$ ]] ; then
		_date=$(echo $staging_number | \
			sed -e 's/\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)-\([0-9]\{2\}\)/\1-\2-\3 \4:/')
	elif [[ $1 =~ [0-9]{6}-[0-9]{6}$ ]] ; then
		_date=$(echo $staging_number | \
			sed -e 's/\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)-\([0-9]\{2\}\)\([0-9]\{2\}\)/\1-\2-\3 \4:\5:/')
	elif [[ $1 =~ [0-9]{6}T[0-9]{6}Z$ ]] ; then
		_date=$(echo $staging_number | \
			sed -e 's/\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)T\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)Z/\1-\2-\3 \4:\5:\6/')
	else
		echo unsupported date format
		exit
	fi
	_year=$(date -d "$_date" +%Y)
	_month=$(date -d "$_date" +%m)
	_day=$(date -d "$_date" +%d)
	_dow=$(date -d "$_date" +%w)
	_time=$(date -d "$_date" +%H%M%S)

	get_intel_ww $_year $_month $_day _ww

	eval "$2=\"$(echo ${staging_number})\""
	eval "$3=\"$(echo ${staging_number} / ${_year}w${_ww}.${_dow}-${_time}/${_year:0:2}${_date})\""
}

## gen_quiltdiff_chglst
#
# trigger jenkins job to generate change list based on quiltdiff
#   arg1: release tag
#   arg2: var of change list url
#
gen_quiltdiff_chglst() {
    #curl -s -H 'Cache-Control: no-cache' ${TRIGGER_QUILTDIFF_BASE_URL}${1} || :
    curl -k -X POST https://oak-jenkins.ostc.intel.com/job/quiltdiff-for-bug-tracking/buildWithParameters --user sys_oak:$SYS_OAK_CRED_JENKINS_API -d kernel="" -d previous_release="" -d target_release=${1}
    sleep 500
    curl -k -X POST https://cbjenkins-fm.devtools.intel.com/teams-iotgdevops00/job/IKT_jobs/job/quiltdiff-for-bug-tracking/buildWithParameters --user sys_oak:$SYS_OAK_CRED_JENKINS_API -d kernel="" -d previous_release="" -d target_release=${1}
    eval "$2=\"${QUILTDIFF_CHGLST_BASE_URL}${1}\""
}

## get_cov_tag
#  Generate tag for regenrated kernel configs to be picked for Coverity scan
#  Return the tag generated
#  Example output: staging-lts-cov-gordon_peak-v4.19.46-android_q-190621T175219Z
#  arg1: build tag (staging-lts-v4.19.66-android_q-190816T214905Z)
#  arg2: soc name  (example gordon_peak)
#

get_cov_tag() {
	tag = $1
	soc = $2
	IFS='-' read -ra tag_elements <<< "$tag"
	kernel=${tag_elements[0]}-${tag_elements[1]}
	time_stamp=${tag_elements[-1]}
	for ((i=2; i<${#tag_elements[@]}-1; i++));do
        	sub_tag+=${tag_elements[i]}"-"
	done
	sub_tag+=$time_stamp
	cov_tag=$kernel-cov-$soc-$sub_tag
	echo $cov_tag


}

tag_sandbox() {
	arg_tagname=$1
	arg_sandbox=$2

	if [[ -z $arg_sandbox ]]
	then
	    tag $arg_tagname
	else
	    echo "Sandbox branch: tagging with sandbox."
	    tag ${arg_sandbox}-$arg_tagname
	fi
}

push_tag_sandbox() {
	arg_remotename=$1
	arg_tagname=$2
	arg_sandbox=$3

	if [[ -z $arg_sandbox ]]
	then
	    push_tag $arg_remotename $arg_tagname
	else
	    echo "Sandbox branch: pushing sandbox tag to remote."
	    push_tag $arg_remotename ${arg_sandbox}-$arg_tagname
	fi
}

# Check for tags that include "sandbox" in them. Returns 0 if it finds any.
# Returns 1 if it cannot.
check_sandbox_tags() {
    arg_datetime=$1
	if git tag | grep $arg_datetime | grep "sandbox" > /dev/null
	then
	    SANDBOX_TAG="sandbox"
	else
	    SANDBOX_TAG=""
	fi
}

# Inside a repository, gets the lexicographically last branch that satisfies a
# regex. This can be used to obtain the latest timestamp in a repo...
# Note that we trim both leading and trailing whitespace with tr because git
# branch --format doesn't seem to exist in Jenkins' version of git.
get_latest_branch() {
    arg_repo_dir=$1
    arg_regex=$2
    if [ -d $arg_repo_dir ]
    then
        pushd $arg_repo_dir > /dev/null
            git fetch --all > /dev/null
            LATEST_BRANCH=$(git branch -r | grep $arg_regex | tail -1 | tr -d '[:space:]')
        popd > /dev/null
    else
        LATEST_BRANCH=""
    fi
}


# Prepare a CVE release notes
# use the data from https://github.com/nluedtke/linux_kernel_cves github and generate a CVE status report
# Parameter 1 - series file from CVE patchset
# Parameter 2 - Link to Latest CVE information from nluedtke
# ex. https://github.com/nluedtke/linux_kernel_cves/blob/master/data/4.19/4.19_security.txt
Prepare_cve_release_note() {
	series_file=$1

	# get the security info file name
     	cve_info_file=$(echo $2 | awk -F "/" '{print $NF}')

	version_string=$3

     	# get security info file
	wget $2

	# Extract list of CVEs fixed in stable update
	sed -n '/Outstanding CVEs/q;p' $cve_info_file  >> Fixed_in_Stable_updates.txt

	# remove entries for stable updates that we have not caught up with ex. if we are
	# on 4.19.58 let us not mention that CVEs  that are fixed in 4.19.59 till we catch
	# up with that stable update
	# assumption we are not too behind. Max 10 stable updates behind

	# var1 is the minor revision ex. for 4.19.57 var1 = 57
	var1=$(echo $version_string | awk -F. '{print $3}')

	for ((i = 10 ; i > 0 ; i--)); do
        	var2=$((var1+$i))
		#var3 = increment kernel_version by $i .i.e if i=10 var3 = 4.19.67 for kernel_version = 4.19.57
        	var3=$(echo $version_string | awk 'BEGIN{FS=OFS="."} gsub('$var1', '$var2', $NF)')
        	#echo $var2 $var3
        	sed -n '/'$var3'/q;p' Fixed_in_Stable_updates.txt > temp2.txt #remove all entries with var3 (ex.4.19.67) and above
	done

	mv temp2.txt Fixed_in_Stable_updates.txt

	# Extract outstanding CVE list
	cat $cve_info_file | awk 'BEGIN{ found=0} /Outstanding CVEs/{found=1}  {if (found) print }' >> Outstanding_cves.txt
	while IFS= read -r line; do echo $"${line%%\:*}" | sed -e 's/^[ \t]*//' >> temp.txt; done < "Outstanding_cves.txt"

	# Look for CVEs in the outstanding CVE list and check if they are fixed by PKT in LTS release CVE patchset
	grep -oi -f temp.txt $series_file >> fixed_cves.txt

	# remove the fixed CVE from Outstanding CVE list
	while IFS= read -r line; do sed -i "/$line/d" ./Outstanding_cves.txt ; done < "fixed_cves.txt"

	# Prepare Release Notes
	echo "CVEs fixed through stable updates" >> CVE_Release_Notes.txt
	echo "=================================" >> CVE_Release_Notes.txt
	cat Fixed_in_Stable_updates.txt >> CVE_Release_Notes.txt
	echo " " >> CVE_Release_Notes.txt
	echo "CVEs Fixed in this $version_string LTS 4.19 release " >> CVE_Release_Notes.txt
	echo "====================================================" >> CVE_Release_Notes.txt
	cat $series_file >> CVE_Release_Notes.txt
	echo " " >> CVE_Release_Notes.txt
	echo "================" >> CVE_Release_Notes.txt
	#cat Outstanding_cves.txt >> CVE_Release_Notes.txt
	rm $cve_info_file temp.txt Outstanding_cves.txt fixed_cves.txt Fixed_in_Stable_updates.txt
}


#
# tag schema:
# {{ is staging/sandbox }}{{ is stable update }}\
# {{ iotg-next or mainline-tracking or lts }}-{{ kernel.current_baseline }}-\
# {{ is_project }}{{ is_milestone }}{{ release.name }}{{ is_cve or is_bullpen }}\
# {{ is_overlay }}{{ staging_number }}
# 
# release.name: linux/yocto/ubuntu/centos/android/android_X/rt/preempt-rt/xenomai
# 
# Note: is_su has not been approved, so disable this option.
#
# positional args:
#   kernel: kenrel name defined in framework.models.Kernel
#   base: upstream kernel version
#   timestamp: timestamp generated by build script
#   release name: see above
#   is_staging:
#   is_sandbox:
#   is_su:
#   prj:
#   ms:
#   is_cve:
#   is_overlay:
#   is_bp:
#
function gen_tagstr() {
    mydir=$(cd $(dirname $0); pwd)
    test "$5" == "true"  && \
      is_staging="True" || \
      is_staging="False"
    test "$6" == "true"  && \
      is_sandbox="True" || \
      is_sandbox="False"
    test "$7" == "true"  && \
      is_su="True" || \
      is_su="False"
    test -n "$8" && \
      prj="\"$8\"" || \
      prj="None"
    test -n "$9" && \
      ms="\"$9\"" || \
      ms="None"
    test "$10" == "true"  && \
      is_cve="True" || \
      is_cve="False"
    test "$11" == "true"  && \
      is_overlay="True" || \
      is_overlay="False"
    test "$12" == "true"  && \
      is_bp="True" || \
      is_bp="False"
    PYTHONPATH=$PYTHONPATH:$mydir python3 - << EOF_PYTHON
from lib.gitutils import generate_tagstr

tag = generate_tagstr("$1", "$2", "$3", "$4", $is_staging, $is_sandbox,
                      $is_su, $prj, $ms, $is_cve, $is_overlay, $is_bp)
print(tag)
EOF_PYTHON
}
