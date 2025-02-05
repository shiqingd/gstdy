#!/bin/bash -ex
mydir="$(cd $(dirname $0); pwd)"

exit_usage() {
        cat <<EOF >&2

USAGE:
	$0 -b <branch_name> [-p <yocto_release>] [-r]

	b = staging branch name - this provides the kernel version.
	p = Poky/Yocto project release name (zeus, rocko, sumo, master (default))
	r = build Preempt-RT Version
	s = SOC to build default target is bxt, additional supported (elkhart-lake)
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
	git remote prune $remote
	git fetch --all --tags
	git clean -ffdx
	check_branch_exist $remote $scmbranch branch_to_checkout
	git checkout $scmbranch -b $branch_to_checkout || \
			git checkout $scmbranch
	git reset --hard $scmbranch
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
while getopts "b:p:rs:h?" OPTION; do
	case $OPTION in
		b)
			branch=${OPTARG}
			;;
		p)
			yocto_release=${OPTARG}
			;;
		r)
			linux_intel=linux-intel-dev-rt
			;;
		s)
			soc=${OPTARG}
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

if ! [ "$linux_intel" ] ; then
	linux_intel=linux-intel-dev
fi

if ! [ "$soc" ] ; then
	soc=default
fi

if ! [ "$WORKSPACE" ] ; then
	WORKSPACE=$mydir
fi

set --

export TOP=$WORKSPACE
WORK=$TOP/poky/build
configbranch=$(echo $branch | sed -e 's/yocto-//')

remotes=(origin origin origin origin origin origin)
scms=(git://git.yoctoproject.org/poky.git \
	git://git.yoctoproject.org/meta-intel \
	https://github.com/intel-innersource/os.linux.kernel.kernel-meta-intel-dev.git \
	https://github.com/intel-innersource/os.linux.kernel.kernel-staging.git \
	https://github.com/intel-innersource/os.linux.kernel.test.cases.git
	git://git.openembedded.org/meta-openembedded)
scmdirs=($TOP/poky $TOP/poky/meta-intel $TOP/poky/kernel-meta-intel-dev $TOP/kernel-staging $TOP/otc_kernel_team-test_case $TOP/poky/meta-openembedded)
mirrordirs=(poky meta-intel kernel-meta-intel-dev kernel-staging otc_kernel_team-test_case meta-openembedded)
scmbranches=($yocto_release $yocto_release $yocto_release $branch master $yocto_release)

for (( i=0 ; i < ${#remotes[@]} ; i++ )) ; do
	remote=${remotes[$i]}
	scm=${scms[$i]}
	scmdir=${scmdirs[$i]}
	mirrordir=${mirrordirs[$i]}
	scmbranch=${scmbranches[$i]}
	gitproject
done

#pushd $TOP/poky/kernel-meta-intel-dev
#git reset --hard origin/zeus
#the two SHA1 doesn't exist in gitlab/innersource repo
#git cherry-pick ec4c6ca36127c2444c3fb64d48928dbf1be962cd 5ff2bae70bdb19bcdfb2a6c96d81dc2e2b899fe9
#popd

sed -i 's/kernel-lts-staging/kernel-staging/g' $TOP/poky/kernel-meta-intel-dev/recipes-kernel/linux/linux-intel-dev.inc

#fix errors about LIC_FILES_CHKSUM SHA1 changed from d7810fa... to 6bc538e...
sed -i 's/d7810fab7487fb0aad327b76f1be7cd7/6bc538ed5bd9a7fc9398086aedcd7e46/' $TOP/poky/scripts/lib/recipetool/create.py
sed -i 's/d7810fab7487fb0aad327b76f1be7cd7/6bc538ed5bd9a7fc9398086aedcd7e46/' $TOP/poky/meta-openembedded/meta-oe/recipes-kernel/linux/linux.inc
sed -i 's/d7810fab7487fb0aad327b76f1be7cd7/6bc538ed5bd9a7fc9398086aedcd7e46/' $TOP/poky/meta/recipes-kernel/linux/linux-yocto.inc

cd $TOP/poky
rm -rf $TOP/poky/build ||:
source oe-init-build-env
bitbake-layers add-layer "$TOP/poky/meta-intel"
bitbake-layers add-layer "$TOP/poky/kernel-meta-intel-dev"
bitbake-layers add-layer "$TOP/poky/meta-openembedded/meta-oe"

# build_site_conf

echo "require conf/multilib.conf" >> conf/local.conf
echo "MULTILIBS = \"\"" >> conf/local.conf
echo "IMAGE_ROOTFS_EXTRA_SPACE = \"2097152\"" >> conf/local.conf

echo "MACHINE = \"intel-corei7-64\"" >> conf/auto.conf
echo "PREFERRED_PROVIDER_virtual/kernel = \"$linux_intel\"" >> conf/auto.conf
#Get the Linux Version.  To do so, need have a clone of kernel-staging
pushd $WORKSPACE/kernel-staging
#Get the Linux version
linux_version=$(make kernelversion)
echo $linux_version
popd
echo "EXTRA_IMAGE_FEATURES_append = \" ssh-server-openssh\"" >> $WORK/conf/auto.conf
echo "KERNEL_MODULE_AUTOLOAD += \"snd_hda_intel\"" >> $WORK/conf/auto.conf
echo "CORE_IMAGE_EXTRA_INSTALL_append = \" file procps quota sudo glibc-utils coreutils ltp rt-tests keyutils numactl lvm2 bc\"" >> $WORK/conf/auto.conf
if [ "$soc" != "default" ] ; then
	echo "BSP_SUBTYPE = \"$soc\"" >> $WORK/conf/auto.conf
fi

#add custom kernel lines to auto.conf file
kernel_line_1='KBRANCH_pn-'"$linux_intel"' = "'"$branch"'"'
kernel_line_2='SRCREV_machine_pn-'"$linux_intel"' = "${AUTOREV}"'
kernel_line_3='LINUX_VERSION_pn-'"$linux_intel"' = "'"$linux_version"'"'
kernel_line_4='KCONFIGBRANCH_pn-'"$linux_intel"' = "'"$configbranch"'"'

kernel_line_5='APPEND += "processor.max_cstate=1 intel_idle.max_cstate=0 intel_idle.max_cstate=0 tsc=reliable nmi_watchdog=0 nosoftlockup intel_pstate=disable idle=poll noht i915.enable_rc6=0 i915.enable_dc=0 i915.disable_power_well=0 hugepages=1024 mce=off hpet=disable numa_balancing=disable clocksource=tsc"'
echo "$kernel_line_1" >> $WORK/conf/auto.conf
echo "$kernel_line_2" >> $WORK/conf/auto.conf
echo "$kernel_line_3" >> $WORK/conf/auto.conf
echo "$kernel_line_4" >> $WORK/conf/auto.conf
echo "$kernel_line_5" >> $WORK/conf/auto.conf
echo "INHERIT += \"rootfsdebugfiles\"" >> $WORK/conf/auto.conf
rootfs_line='ROOTFS_DEBUG_FILES += "'"$TOP"'/otc_kernel_team-test_case/yocto_bat_case/scripts/io.sh ${IMAGE_ROOTFS}/bin/io.sh ;"'
echo "$rootfs_line" >> $WORK/conf/auto.conf

#build image
bitbake core-image-sato

pushd $TOP/poky/kernel-meta-intel-dev
git reset --hard origin/zeus
popd
