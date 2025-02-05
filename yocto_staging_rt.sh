#!/bin/bash -ex
mydir="$(cd $(dirname $0); pwd)"

exit_usage() {
        cat <<EOF >&2

USAGE:
	$0 [-p <yocto_release>] [-m <meta-intel>] [-o <meta-openembeded>] -r <kernel_repo_name> -t <tag> [-y <meta-intel-ikt-rt>] [-i <image_type>] 

	p = Poky/Yocto project release branch (zeus, rocko, sumo, master (default))
	m = meta-intel project branch name (hardknott)
	o = meta-openembedded project branch name (hardknott)
	t = tag -  this porvides the kernel tag
	r = Repo name - this provides the kernel repo address
	y = rt_bkc_branch name (hardknott/yocto)
	i = image_type - poky build image type bitbake core-image-sato (or core-image-minimal)
	d = debug_flag - RT kernl with debug configs will be built when add this debug flag
	g = remove_cmd_i915_flag - remove i915 related cmdline when add this flag
	h|? = help (this screen)

	The yocto_staging script will build the kernel from the branch named on
	the commandline with various version of Poky.  It will always use the
	dev-bkc repo.
EOF
exit 1
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
	git fetch --all --tags -f
	git clean -ffdx
	git checkout origin/$scmbranch -B $scmbranch || \
		git checkout $scmbranch
	git reset --hard origin/$scmbranch || \
		git reset --hard $scmbranch
	popd
}

# main
while getopts "p:m:o:t:r:y:i:dgh?" OPTION; do
	case $OPTION in
		p)
			yocto_release=${OPTARG}
			;;
		m)
			meta_intel_release=${OPTARG}
			;;
		o)
			meta_openembeded_release=${OPTARG}
			;;
		t)
			tag=${OPTARG}
			;;
		r)
			Repo=${OPTARG}
			;;
		y)
			rt_bkc_branch=${OPTARG}
			;;
		i)
			image_type=${OPTARG}
			;;
		d)
			debug_tag=1
			;;
		g)
			cmd_i915_tag=1
			;;
		h|?)
			exit_usage
			;;
	esac
done

if ! [ "$yocto_release" ] ; then
	yocto_release="master"
fi
if ! [ "$meta_intel_release" ] ; then
	meta_intel_release="master"
fi
if ! [ "$meta_openembeded_release" ] ; then
	meta_openembeded_release="master"
fi
if ! [ "$rt_bkc_branch" ] ; then
	rt_bkc_branch="hardknott/yocto"
fi
if ! [ "$image_type" ] ; then
	image_type="core-image-sato"
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
	https://github.com/intel-innersource/os.linux.kernel.ikt-rt-bkc.git)
scmdirs=($TOP/yocto_project $TOP/yocto_project/meta-intel $TOP/yocto_project/meta-openembedded $TOP/yocto_project/meta-intel-ikt-rt)
mirrordirs=(yocto_project meta-intel meta-openembedded meta-intel-ikt-rt)
scmbranches=($yocto_release $meta_intel_release $meta_openembeded_release $rt_bkc_branch)

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
echo 'SRC_URI = "http://ikt.bj.intel.com/downloads/sshpass/sshpass-1.05.tar.gz"' >> $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass.inc
sed -i '/SRC_URI/d' $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass_1.05.bb
echo 'BB_STRICT_CHECKSUM = "0"' >> $TOP/yocto_project/meta-intel-ikt-rt/recipes-connectivity/sshpass/sshpass_1.05.bb

#to fix error about LIC_FILES_CHKSUM
if [[ "$tag" == *mainline-tracking* ]]; then
    sed -i 's/d7810fab7487fb0aad327b76f1be7cd7/6bc538ed5bd9a7fc9398086aedcd7e46/' $TOP/yocto_project/scripts/lib/recipetool/create.py
    sed -i 's/d7810fab7487fb0aad327b76f1be7cd7/6bc538ed5bd9a7fc9398086aedcd7e46/' $TOP/yocto_project/meta/recipes-kernel/linux/linux-yocto.inc
    sed -i 's/d7810fab7487fb0aad327b76f1be7cd7/6bc538ed5bd9a7fc9398086aedcd7e46/' $TOP/yocto_project/meta-openembedded/meta-oe/recipes-kernel/linux/linux.inc
fi

source oe-init-build-env
bitbake-layers add-layer "$TOP/yocto_project/meta-intel"
bitbake-layers add-layer "$TOP/yocto_project/meta-openembedded/meta-oe"
bitbake-layers add-layer "$TOP/yocto_project/meta-intel-ikt-rt"

echo "PWD=$PWD"

echo "IMAGE_FSTYPES = \"wic.bz2  tar\"" >> conf/local.conf
echo "require conf/multilib.conf" >> conf/local.conf
echo "MULTILIBS = \"\"" >> conf/local.conf
echo "IMAGE_ROOTFS_EXTRA_SPACE = \"2097152\"" >> conf/local.conf

echo "MACHINE = \"intel-corei7-64\"" >> conf/auto.conf
echo "PREFERRED_PROVIDER_virtual/kernel = \"$linux_intel\"" >> conf/auto.conf

if [ "$Repo" != "none" ] ; then
	echo "K_REPO = \"git://github.com/intel-innersource/os.linux.kernel.$Repo.git\"" >> conf/auto.conf
else
	echo "ERROR: Kernel repo address is empty, need kernel repo info"
	exit 1
fi
if [ "$tag" != "none" ] ; then
	echo "K_TAG =\"${tag}\"" >> conf/auto.conf
else
	echo "ERROR: Kernel tag is empty, need kernel tag to checkout"
        exit 1
fi
search="$(git ls-remote --tags --heads git://github.com/intel-innersource/os.linux.kernel.$Repo.git $tag)"
if [[ "$search" != *tags/$tag ]] && [[ "$search" != *heads/$tag ]] ; then
	echo "ERROR: branch/tag doesn't exist: ${tag}"
	exit 1
else
        echo "${tag} exists and yocto build continues"
fi

if [ "$debug_tag" == "1" ] ; then
	echo 'K_DEBUG_CONFIG = "1"' >> conf/local.conf
fi
if [ "$cmd_i915_tag" != "1" ] ; then
        echo "APPEND += \"i915.force_probe=* i915.enable_guc=7\"" >> conf/local.conf
fi

kernel_version=`echo $tag | grep -oP '\d*\.\d+' | head -n 1`
#remove perf module
sed -i '/IMAGE_INSTALL/d' $TOP/yocto_project/meta-intel-ikt-rt/recipes-rt/images/core-image-sato.bbappend
echo 'IMAGE_INSTALL += "rt-tests lvm2 bc keyutils numactl libva-utils stress"' >> $TOP/yocto_project/meta-intel-ikt-rt/recipes-rt/images/core-image-sato.bbappend

echo "LINUX_VERSION = \"${kernel_version}\"" >> conf/auto.conf
echo "K_PROTOCOL = \"https\"" >> conf/auto.conf
echo "PREFERRED_PROVIDER_virtual/kernel = \"linux-intel-ikt-rt\"" >> conf/auto.conf
echo "KBRANCH_pn-linux-intel-ikt-rt = \"${tag}\"" >> conf/auto.conf
echo "SRCREV_machine_pn-linux-intel-ikt-rt = \"\${AUTOREV}\"" >> conf/auto.conf
sed -i 's/tag=${K_TAG};//' ../meta-intel-ikt-rt/recipes-kernel/linux/linux-intel-ikt.inc
sed -i 's/branch=${K_BRANCH}/nobranch=1/g' ../meta-intel-ikt-rt/recipes-kernel/linux/linux-intel-ikt.inc

#echo "CORE_IMAGE_EXTRA_INSTALL_append = \" file procps quota sudo glibc-utils coreutils ltp rt-tests\"" >> $WORK/conf/auto.conf
echo "CORE_IMAGE_EXTRA_INSTALL_append = \" file procps quota sudo glibc-utils coreutils ltp rt-tests keyutils numactl lvm2 bc\"" >> conf/auto.conf

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

