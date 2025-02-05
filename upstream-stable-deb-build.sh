#!/bin/bash -ex
mydir="$(cd $(dirname $0); pwd)"

exit_usage() {
        cat <<EOF >&2
USAGE:
	$0 -r <kernel_repo_name> -t <tag> -c <kernel-config> -x <xenomai_repo> -b <xenomai_branch>
	r = Repo name - this provides the kernel repo address
	t = Branch/tag -  this porvides the kernel branch or kernel tag
	c = Config - this provides the kernel config address
	x = Xenomai Repo name - this provides the xenomai hacker space repo address
	b = Xenomai Branch/tag - this provides the xenomai repo branch or tag
	i = Build id -  this provides the num of Jenkins build job
	h|? = help (this screen)
	The upstream-stable-deb-build script will build deb package of
        the kernel from the branch named on the commandline.
EOF
exit 1
}
# main
while getopts "r:t:c:x:b:i:h?" OPTION; do
	case $OPTION in
		r)
			repo=${OPTARG}
			;;
		t)
			tag=${OPTARG}
			;;
		c)
			config=${OPTARG}
			;;
		x)
			xenomai_repo=${OPTARG}
			;;
		b)
			xenomai_barnch=${OPTARG}
			;;
		i)
			build_id=${OPTARG}
			;;
		h|?)
			exit_usage
			;;
	esac
done

if ! [ "$repo" ] ;  then
	echo -e "ERROR: Please add repo url to build kernel deb by using '-r #repo_url'"
	exit 1
fi
if ! [ "$tag" ] ;  then
	echo -e "ERROR: Please add tag/branch to build kernel deb by using '-t #tag/#branch'"
	exit 1
fi

search=`git ls-remote --tags --heads $repo | grep -i $tag`
if ! [[ "$search" ]] ; then
	echo -e "ERROR: Kernel branch/tag doesn't exist: ${tag}"
	exit 1
else
        echo -e "${tag} exists and kernel build continues"
fi

if ! [ "$WORKSPACE" ] ; then
	WORKSPACE=$mydir
fi
set --

export TOP=$WORKSPACE

ARCH=x86_64
rm -rf "$TOP/upstream-rt-stable"
rm -rf "$TOP/deb-package-out"
git clone $repo "$TOP/upstream-rt-stable"
pushd "$TOP/upstream-rt-stable"
for r in $(git remote) ; do
	git remote prune $r
done
git fetch --all --tags -f
git clean -fdx
git checkout origin/$tag -B $tag || \
	git checkout $tag
git reset --hard origin/$tag || \
	git reset --hard $tag

if [ "$config" ] ;  then
	wget $config -O ./.config
	if [[ $? != 0 ]] ; then
		echo -e "ERROR: wget config from ${config} failed"
		exit 1
	fi
else
	echo -e "WARNING: Did not input Kernel config, will get reference config through kernel-config repo!"
	rm -rf "./kernel-config"
	git clone https://github.com/intel-innersource/os.linux.kernel.kernel-config.git "./kernel-config"
	cd "./kernel-config"
	git fetch --all --tags -f
	git clean -fdx
	if [ "$xenomai_repo" ] ; then
		if [[ "$tag" =~ "v5.15" ]] ; then
			git checkout origin/5.15/dovetail-xenomai -B 5.15/dovetail-xenomai
		elif [[ "$tag" =~ "v5.10" ]] ; then
			git checkout origin/5.10/xenomai-dovetail -B 5.10/xenomai-dovetail
		elif [[ "$tag" =~ "v6.1" ]] ; then
			git checkout origin/6.1/dovetail-xenomai -B 6.1/dovetail-xenomai
		elif [[ "$tag" =~ "v6.6" ]] ; then
			git checkout origin/6.6/dovetail-xenomai -B 6.6/dovetail-xenomai
		elif [[ "$tag" =~ "v6.12" ]] ; then
			git checkout origin/6.12/dovetail-xenomai -B 6.12/dovetail-xenomai
		else
			echo -e "ERROR: get xenomai kernel config failed, please check!"
			exit 1
		fi
	elif [[ "$tag" =~ "rt" ]] ; then
		if [[ "$tag" =~ "v5.15" ]] ; then
			git checkout origin/staging/5.15/preempt-rt -B staging/5.15/preempt-rt
		elif [[ "$tag" =~ "v5.10" ]] ; then
			git checkout origin/staging/5.10/preempt-rt -B staging/5.10/preempt-rt
		elif [[ "$tag" =~ "v6.1" ]] ; then
			git checkout origin/staging/6.1/preempt-rt -B staging/6.1/preempt-rt
		elif [[ "$tag" =~ "v6.6" ]] ; then
			git checkout origin/staging/6.6/preempt-rt -B staging/6.6/preempt-rt
		else
			echo -e "ERROR: get kernel config failed, please check!"
			exit 1
		fi
	else
		if [[ "$tag" =~ "v5.15" ]] ; then
			git checkout origin/staging/5.15/linux -B staging/5.15/linux
		elif [[ "$tag" =~ "v6.1" ]] ; then
			git checkout origin/staging/6.1/linux -B staging/6.1/linux
		elif [[ "$tag" =~ "v6.6" ]] ; then
			git checkout origin/staging/6.6/linux -B staging/6.6/linux
		else
			echo -e "ERROR: get kernel config failed, please check!"
			exit 1
		fi
	fi
	cp x86_64_defconfig ../.config
	if [[ $? != 0 ]] ; then
		echo -e "ERROR: get kernel config failed, please check!"
		exit 1
	else
		cd ..
	fi
fi

if [ "$xenomai_repo" ] ; then
	search_xeno=`git ls-remote --tags --heads $xenomai_repo | grep -i $xenomai_barnch`
	if ! [[ "$search_xeno" ]] ; then
		echo -e "ERROR: Xenoami branch/tag doesn't exist: ${xenomai_barnch}"
		exit 1
	else
		echo -e "${xenomai_barnch} exists and Xenomai kernel build continues"
	fi
	rm -rf "./xenomai-hacker-space"
	git clone $xenomai_repo "./xenomai-hacker-space"
	cd "./xenomai-hacker-space"
	git fetch --all --tags -f
	git clean -fdx
	git checkout origin/$xenomai_barnch -B $xenomai_barnch || \
		git checkout $xenomai_barnch
	git reset --hard origin/$xenomai_barnch || \
		git reset --hard $xenomai_barnch
	./scripts/prepare-kernel.sh --linux="$TOP/upstream-rt-stable" --dovetail= --arch=x86
	if [[ $? != 0 ]] ; then
		echo -e "ERROR: xenomai patches applied failed, please check!"
		exit 1
	else
		cd ..
	fi
fi

make olddefconfig
if [[ $? != 0 ]] ; then
        echo -e "ERROR: make olddefconfig failed"
        exit 1
fi
echo -e "Building deb package..."
if [[ "$xenomai_repo" && "$tag" != */* ]] ; then
	KSRC_UPSTREAM_TAG=${tag#*-v}
	timestamp=${KSRC_UPSTREAM_TAG#*xenomai-}
	KSRC_UPSTREAM_TAG=${KSRC_UPSTREAM_TAG%-xenomai*}
	#timestamp=`echo $tag|awk -F'-' '{print $NF}'`
	KERNELRELEASE=`make kernelversion`-xenomai-${timestamp,,}
	nice make -j`nproc` bindeb-pkg LOCALVERSION= KDEB_PKGVERSION=${KSRC_UPSTREAM_TAG:0}-$build_id KERNELRELEASE=`make kernelversion`-xenomai-${timestamp,,} KDEB_SOURCENAME=linux-${KERNELRELEASE}
else
	nice make -j`nproc` bindeb-pkg
fi
if [[ $? != 0 ]] ; then
        echo -e "ERROR: make -j`nproc` bindeb-pkg failed"
        exit 1
else
        echo -e "Built deb package successfully!"
fi
popd
mkdir "$TOP/deb-package-out"
mv *.deb "$TOP/deb-package-out"
mv *.changes "$TOP/deb-package-out"
exit 0

