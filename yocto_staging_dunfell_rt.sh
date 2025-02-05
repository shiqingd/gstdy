#!/bin/bash -ex
mydir="$(cd $(dirname $0); pwd)"

exit_usage() {
        cat <<EOF >&2

USAGE:
	$0 -b <branch_name> [-p <yocto_release>] [-r]

	b = staging branch name - this provides the kernel version.
	p = Poky/Yocto project release name (zeus, rocko, sumo, master (default))
	tag = tag
	r = Repo name - this provides the kernel repo address
	image_type = poky build image type bitbake core-image-sato (or core-image-minimal)
	h|? = help (this screen)

	The yocto_staging script will build the kernel from the branch named on
	the commandline with various version of Poky.  It will always use the
	dev-bkc repo.
EOF
exit 1
}

check_branch_exist() {
		declare remote=${1}
		declare branch=${2}
		declare search="$(git ls-remote --tags --heads $remote $branch)"

		case "$search" in
				*tags/$branch)
						remote_branch=$branch
						;;
				*heads/$branch)
						remote_branch="origin/$branch"
						;;
				*)
				echo "ERROR: branch/tag doesn't exist: ${remote}/${branch}"
				exit 10
				;;
		esac

		test -n "$3" && eval "$3=\"$remote_branch\""
}

gitproject() {
	if [ ! -d $scmdir ] ; then
		rsync -avzq /mirrors/$mirrordir/ $scmdir/ || \
			git clone $scm $scmdir
	fi
	pushd $scmdir
	for r in $(git remote) ; do
		git remote prune $r
	done
	git fetch --all --tags
	git clean -ffdx
	git checkout origin/$scmbranch -b $scmbranch || \
		git checkout $scmbranch
	git reset --hard origin/$scmbranch
	popd
}

build_site_conf() {
	if [ ! -d "/yocto/$yocto_release/downloads" ] ; then
	      mkdir -p /yocto/$yocto_release/downloads
	fi
	if [ ! -d "/yocto/$yocto_release/sstate-cache" ] ; then
	      mkdir -p /yocto/$yocto_release/sstate-cache
	fi
	echo "SSTATE_MIRRORS = \"file://.* http://yocto-ab-master.jf.intel.com/sstate/PATH\"" >> $WORK/conf/site.conf
	echo "SSTATE_DIR ?= \"/yocto/$yocto_release/sstate-cache\"" >> $WORK/conf/site.conf

	echo "SOURCE_MIRROR_URL = \"http://yocto-ab-master.jf.intel.com/pub/sources/\"" >> $WORK/conf/site.conf
	echo "INHERIT += \"own-mirrors\"" >> $WORK/conf/site.conf
	echo "DL_DIR ?= \"/yocto/$yocto_release/downloads\"" >> $WORK/conf/site.conf
}

#########################
# main
while getopts "b:p:t:r:i:h?" OPTION; do
	case $OPTION in
		b)
			branch=${OPTARG}
			;;
		p)
			yocto_release=${OPTARG}
			;;
		t)
			tag=${OPTARG}
			;;
		r)
			Repo=${OPTARG}
			;;
		i)
			image_type=${OPTARG}
			;;
		h|?)
			exit_usage
			;;
	esac
done

if ! [ "$branch" ] ; then
	echo "Need a branch to build!"
	exit_usage
fi

if ! [ "$yocto_release" ] ; then
	yocto_release=master
fi

if ! [ "$WORKSPACE" ] ; then
	WORKSPACE=$mydir
fi

set --

export TOP=$WORKSPACE
#WORK=$TOP/poky/build
#configbranch=$(echo $branch | sed -e 's/yocto-//')

remotes=(origin origin origin origin)
scms=(git://git.yoctoproject.org/poky.git \
	git://git.yoctoproject.org/meta-intel \
	https://git.openembedded.org/meta-openembedded \
	ssh://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/ikt_rt_bkc.git)
scmdirs=($TOP/yocto_project $TOP/yocto_project/meta-intel $TOP/yocto_project/meta-openembedded $TOP/yocto_project/meta-intel-ikt-rt)
mirrordirs=(yocto_project meta-intel meta-openembedded meta-intel-ikt-rt)
scmbranches=($yocto_release $yocto_release $yocto_release $branch)

for (( i=0 ; i < ${#remotes[@]} ; i++ )) ; do
	remote=${remotes[$i]}
	scm=${scms[$i]}
	scmdir=${scmdirs[$i]}
	mirrordir=${mirrordirs[$i]}
	scmbranch=${scmbranches[$i]}
	gitproject
done


cd $TOP/yocto_project
mv $TOP/yocto_project/build $TOP/yocto_project/build.$$ || :
ls -ld $TOP/yocto_project/build* || :
rm -rf $TOP/yocto_project/build.* &
sed -i '/SRC_URI/d' $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass.inc
echo 'SRC_URI = "http://otcpkt.bj.intel.com/tools/sshpass/sshpass-1.05.tar.gz"' >> $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass.inc
sed -i '/SRC_URI/d' $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass_1.05.bb
echo 'BB_STRICT_CHECKSUM = "0"' >> $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass_1.05.bb

source oe-init-build-env
bitbake-layers add-layer "$TOP/yocto_project/meta-intel"
bitbake-layers add-layer "$TOP/yocto_project/meta-openembedded/meta-oe"
bitbake-layers add-layer "$TOP/yocto_project/meta-intel-ikt-rt"

echo "PWD=$PWD"
# build_site_conf

echo "require conf/multilib.conf" >> conf/local.conf
echo "MULTILIBS = \"\"" >> conf/local.conf
echo "IMAGE_ROOTFS_EXTRA_SPACE = \"2097152\"" >> conf/local.conf

echo "MACHINE = \"intel-corei7-64\"" >> conf/auto.conf
echo "PREFERRED_PROVIDER_virtual/kernel = \"$linux_intel\"" >> conf/auto.conf

if [ "$tag" != "none" ] ; then
	echo "K_TAG =\"${tag}\"" >> conf/auto.conf
fi

if [ "$branch" == "5.4/yocto" ] ; then
	echo "K_BRANCH = \"5.4/preempt-rt\"" >> conf/auto.conf
	echo "K_REPO = \"git://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/$Repo.git\"" >> conf/auto.conf
elif [ "$branch" == "5.9/yocto" ] ; then
	echo "K_BRANCH = \"5.9/iotg-next-preempt-rt\"" >> conf/auto.conf
	echo "K_REPO = \"git://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/$Repo.git\"" >> conf/auto.conf
elif [ "$branch" == "5.10/yocto" ] ; then
	echo "K_BRANCH = \"5.10/preempt-rt\"" >> conf/auto.conf
	echo "K_REPO = \"git://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/$Repo.git\"" >> conf/auto.conf
	echo "LINUX_VERSION = \"5.10\"" >> conf/auto.conf
fi

echo "K_PROTOCOL = \"ssh\"" >> conf/auto.conf

if [ "$tag" != "none" ] ; then
	echo "PREFERRED_PROVIDER_virtual/kernel = \"linux-intel-ikt-rt\"" >> conf/auto.conf
	echo "KBRANCH_pn-linux-intel-ikt-rt = \"${tag}\"" >> conf/auto.conf
	echo "SRCREV_machine_pn-linux-intel-ikt-rt = \"\${AUTOREV}\"" >> conf/auto.conf
	sed -i 's/tag=${K_TAG};//' ../meta-intel-ikt-rt/recipes-kernel/linux/linux-intel-ikt.inc
	sed -i 's/branch=${K_BRANCH}/nobranch=1/g' ../meta-intel-ikt-rt/recipes-kernel/linux/linux-intel-ikt.inc
fi

#Get the Linux Version.  To do so, need have a clone of kernel-lts-staging
#pushd $WORKSPACE/kernel-lts-staging

#Get the Linux version
#linux_version=$(make kernelversion)
#echo $linux_version
#popd
#echo "EXTRA_IMAGE_FEATURES_append = \" ssh-server-openssh\"" >> $WORK/conf/auto.conf
#echo "CORE_IMAGE_EXTRA_INSTALL_append = \" file procps quota sudo glibc-utils coreutils ltp rt-tests\"" >> $WORK/conf/auto.conf
echo "CORE_IMAGE_EXTRA_INSTALL_append = \" file procps quota sudo glibc-utils coreutils ltp rt-tests keyutils numactl lvm2 bc\"" >> conf/auto.conf
#if [ "$soc" != "default" ] ; then
#	echo "BSP_SUBTYPE = \"$soc\"" >> $WORK/conf/auto.conf
#fi

#add custom kernel lines to auto.conf file
#kernel_line_1='KBRANCH_pn-'"$linux_intel"' = "'"$branch"'"'
#kernel_line_2='SRCREV_machine_pn-'"$linux_intel"' = "${AUTOREV}"'
#kernel_line_3='LINUX_VERSION_pn-'"$linux_intel"' = "'"$linux_version"'"'
#kernel_line_4='KCONFIGBRANCH_pn-'"$linux_intel"' = "'"$configbranch"'"'

#kernel_line_5='APPEND += "processor.max_cstate=1 intel_idle.max_cstate=0 intel_idle.max_cstate=0 tsc=reliable nmi_watchdog=0 nosoftlockup intel_pstate=disable idle=poll noht i915.enable_rc6=0 i915.enable_dc=0 i915.disable_power_well=0 hugepages=1024 mce=off hpet=disable numa_balancing=disable clocksource=tsc"'
#echo "$kernel_line_1" >> $WORK/conf/auto.conf
#echo "$kernel_line_2" >> $WORK/conf/auto.conf
#echo "$kernel_line_3" >> $WORK/conf/auto.conf
#echo "$kernel_line_4" >> $WORK/conf/auto.conf
#echo "$kernel_line_5" >> $WORK/conf/auto.conf
#echo "INHERIT += \"rootfsdebugfiles\"" >> $WORK/conf/auto.conf
#echo "IMAGE_ROOTFS_EXTRA_SPACE = \"524288\""
#rootfs_line='ROOTFS_DEBUG_FILES += "'"$TOP"'/otc_kernel_team-test_case/yocto_bat_case/scripts/io.sh ${IMAGE_ROOTFS}/bin/io.sh ;"'
#echo "$rootfs_line" >> $WORK/conf/auto.conf

#build image
if [ "$image_type" ] ; then
	bitbake ${image_type}
else
	echo "Need a image_type to build!"
	exit_usage
fi

