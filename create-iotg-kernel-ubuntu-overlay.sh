#!/usr/bin/env bash
set -ex


#sudo apt-get -y install libcap-dev
#sudo apt -y install libpci-dev libdwarf-dev libunwind-dev libbfd-dev libnuma-dev \
#libperl-dev libpython3.8-dev libdw-dev lzma-dev lzma libzstd-dev gettext asciidoc
#sudo apt -y install btrfs-progs dmraid keyutils 

CUR_DIR=$(pwd)

KSRC_DIR=$CUR_DIR/ksrc_quilt
KCFG_DIR=$CUR_DIR/kernel-config
OVERLAY_DIR=$CUR_DIR/iotg-kernel-overlay

rm -rf $KSRC_DIR
rm -rf $KCFG_DIR
rm -rf $OVERLAY_DIR

STAGING_REV=$KERNEL_QUILT_TAG
overlay_branch=$OVERLAY_TARGET_BRANCH

echo "Clone the kernel config ..."
git clone $KERNEL_CONFIG_REPO $KCFG_DIR
pushd $KCFG_DIR
    git checkout $KERNEL_CONFIG_TAG
popd
echo "Clone the kernel config ... Done!"

echo "Clone the kernel quilt patches..."
git clone $KERNEL_QUILT_REPO $KSRC_DIR
pushd $KSRC_DIR
    git checkout $KERNEL_QUILT_TAG
    quilt_branch_info=$(git log --no-decorate --oneline -n1)
popd
echo "Clone the kernel quilt patches...Done!"

echo "Clone the kernel overlay..."
git clone $OVERLAY_REPO $OVERLAY_DIR
echo "Clone the kernel overlay...Done"

pushd $OVERLAY_DIR

# Switch to overlay branch
if [ $(git branch -r | grep -w "\borigin/$overlay_branch$") ]; then
    git checkout $overlay_branch
    git fetch origin --tags
    git pull
else
    git checkout -b $overlay_branch origin/$OVERLAY_TEMPLATE_TAG
fi

rm -fr $OVERLAY_DIR/kernel-config
mkdir -p $OVERLAY_DIR/kernel-config
# Get config files from kernel-config repo
if [ -d $KCFG_DIR/overlay/base-os -a -d $KCFG_DIR/overlay/features -a -d $KCFG_DIR/overlay/overlay ]; then
    cp -rf $KCFG_DIR/overlay/* $OVERLAY_DIR/kernel-config/
else
    echo "config for overlay does not exist, please checking ..."
    exit 1
fi

if [[ $OVERLAY_TARGET_BRANCH == lts2022-ubuntu* || $OVERLAY_TARGET_BRANCH == lts2023-ubuntu* || $OVERLAY_TARGET_BRANCH == lts2024-ubuntu* ]]; then
    OVERLAY_NAME="lts"
elif [[ $OVERLAY_TARGET_BRANCH == lts2022-rt-ubuntu* || $OVERLAY_TARGET_BRANCH == lts2023-rt-ubuntu* || $OVERLAY_TARGET_BRANCH == lts2024-rt-ubuntu* ]]; then
    OVERLAY_NAME="rt"
elif [[ $OVERLAY_TARGET_BRANCH == iotg-next-rt*-ubuntu ]]; then
    OVERLAY_NAME="iotg-next-rt"
elif [[ $OVERLAY_TARGET_BRANCH == iotg-next*-ubuntu ]]; then
    OVERLAY_NAME="iotg-next"
elif [[ $OVERLAY_TARGET_BRANCH == *mainline-tracking-rt*-ubuntu* ]]; then
    OVERLAY_NAME="mainline-tracking-rt"
elif [[ $OVERLAY_TARGET_BRANCH == mainline-tracking*-ubuntu* ]]; then
    OVERLAY_NAME="mainline-tracking"
else
    echo "OVERLAY_NAME is not defined. "
    exit 1
fi

# Update the overlay name in case of EBs
if [[ $OVERLAY_TARGET_BRANCH == *EB* ]]; then
    OVERLAY_NAME="${OVERLAY_NAME}-eb"
fi

# Update the overlay name in case of CVE
if [[ $OVERLAY_TARGET_BRANCH == *cve* ]]; then
    OVERLAY_NAME="${OVERLAY_NAME}-cve"
fi

echo "OVERLAY_NAME is $OVERLAY_NAME"

kernel_version_full=$KSRC_UPSTREAM_TAG
# check version info
if [[ ! $kernel_version_full == v* ]]; then
    echo "===== Error: Full kernel version $kernel_version_full is not the result we want ! ====="
    exit 1
else
    echo "===== Get the full kernel version: $kernel_version_full ====="
fi

# Get version/extraversion/subleaver information of the kernel
# get 5.12.6 from v5.12.6-rc3
kernel_version=$(echo ${kernel_version_full##v} | awk -F'-' '{print $1}')
# get rc3 from v5.12.6-rc3
kernel_extraversion=$(echo ${kernel_version_full##v} | awk -F'-' '{print $2}')
# get rt6 from v5.17-rc3-rt6
kernel_extraversion_rtversion=$(echo ${kernel_version_full##v} | awk -F'-' '{print $3}')
# get 6 from 5.12.6
kernel_version_sublevel=$(echo $kernel_version | grep -oP "[0-9]+\.[0-9]+\.?\K([0-9]+)?")

#add echo above, then easy to debug
echo "kernel_version=$kernel_version"
echo "kernel_extraversion=$kernel_extraversion"
echo "kernel_extraversion_rtversion=$kernel_extraversion_rtversion"
echo "kernel_version_sublevel=$kernel_version_sublevel"

#if [[ $kernel_extraversion_rtversion == rt* ]]; then
#	KEXTRARTV="-${kernel_extraversion}-${kernel_extraversion_rtversion}"
#elif [[ $kernel_extraversion == rc* ]]; then
if [[ $kernel_extraversion == rc* ]]; then
    KEXTRAVERSION="-${kernel_extraversion}"
else
    KEXTRAVERSION=""
fi

rm -f $OVERLAY_DIR/kernel-config/features/rt-cmd.cfg
if [[ $KSRC_UPSTREAM_TAG == *rt* ]]; then
    if [[ $KSRC_UPSTREAM_TAG == *6.1\.* ]] || [[ $KSRC_UPSTREAM_TAG == *6.6\.* ]] || [[ $KSRC_UPSTREAM_TAG == *6.12\.* ]]; then
        KRTV="-${kernel_extraversion}"
        KSRC_REPO="https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-stable-rt.git/"

	#if actually, no UPSTREAM_TAG in linux-stable-rt, will use linux-rt-devel
	git clone https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-stable-rt.git linux-stable-rt
	cd linux-stable-rt
	    tmp_upstream_tag=$(git tag -l ${KSRC_UPSTREAM_TAG})
	    if [[ "$tmp_upstream_tag" != "$KSRC_UPSTREAM_TAG" ]];then
	        KSRC_REPO="https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-rt-devel.git"
	    fi
	cd -
    elif [[ -n $kernel_extraversion_rtversion ]]; then
        KRTV="-${kernel_extraversion_rtversion}"
        KSRC_REPO="https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-rt-devel.git"
    else
        KRTV="-${kernel_extraversion}"
        KSRC_REPO="https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-rt-devel.git"
    fi
elif [[ $KSRC_UPSTREAM_TAG == v6.1\.* ]] || [[ $KSRC_UPSTREAM_TAG == v6.6\.* ]] || [[ $KSRC_UPSTREAM_TAG == v6.11\.* ]]; then
    KRTV=""
    KSRC_REPO="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/"
    rm -f $OVERLAY_DIR/kernel-config/features/rt.cfg
else
    KRTV=""
    #KSRC_REPO="https://github.com/torvalds/linux.git/"
    #actually, stable/linux.git covers torvalds/linux.git
    KSRC_REPO="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git"
    #rm -f $OVERLAY_DIR/kernel-config/features/rt.cfg
fi

if [ -z $kernel_version_sublevel ]; then
    kernel_version_sublevel='0'
    kernel_version="${kernel_version}.0"
fi

KVERSION=$(echo $kernel_version|awk -F'.' '{print $1}')
KPATCHLEVEL=$(echo $kernel_version|awk -F'.' '{print $2}')
KSUBLEVEL=$(echo $kernel_version|awk -F'.' '{print $3}')

# logging
echo "KVERSION:" $KVERSION
echo "KPATCHLEVEL:" $KPATCHLEVEL
echo "KSUBLEVEL:" $KSUBLEVEL
echo "KEXTRAVERSION:" $KEXTRAVERSION
echo "KEXTRARTV:" $KEXTRARTV
echo "KRTV:" $KRTV
echo "KSRC_REPO:" $KSRC_REPO

date_tag=$(basename $STAGING_REV | awk -F'-' '{print $NF}')
data_MMDD=${date_tag:2:4}

# Copy quilt patches to overlay repo
#  rm the old patches in overlay repo
rm -rf $OVERLAY_DIR/kernel-patches/patches/*
#  copy quilt patches to overlay
cp $KSRC_DIR/patches/* $OVERLAY_DIR/kernel-patches/patches/

# Generate build.sh scripts
BUILD_FILE=$OVERLAY_DIR/config.sh
if [ ! -f $BUILD_FILE ]; then
    echo "Error: ${BUILD_FILE} no such file."
    exit 1
fi

# kernel 5.12.0-rc3
# Set the KVERSION  e.g. 5
sed -i "/^KVERSION/c KVERSION=${KVERSION}" ${BUILD_FILE}
# Set the KPATCHLEVEL e.g. 12
sed -i "/^KPATCHLEVEL/c KPATCHLEVEL=${KPATCHLEVEL}" ${BUILD_FILE}
# Set the KSUBLEVEL  e.g. 0
sed -i "/^KSUBLEVEL/c KSUBLEVEL=${KSUBLEVEL}" ${BUILD_FILE}
# Set the KEXTRAVERSION  e.g. -rc3
sed -i "/^KEXTRAVERSION/c KEXTRAVERSION=${KEXTRAVERSION}" ${BUILD_FILE}
# Set the KRTV  e.g. -rt53
sed -i "/^KRTV/c KRTV=${KRTV}" ${BUILD_FILE}
# Set the KSRC_REPO
sed -i "/^KSRC_REPO/c KSRC_REPO=${KSRC_REPO}" ${BUILD_FILE}

# add commit then push change to remote repo
if git diff --no-ext-diff --quiet ./kernel-patches/patches/ ./config.sh ./kernel-config/; then
    set +x
    echo "===== No changes found in the SOURCES and SPECS folder, No need to submit commit! ====="
    # exit 1  - # Don't fail the build here : let the downstream build job trigger for test purposes
else
    # get user information then submit commit.
    user_name=$(git config user.name)
    user_email=$(git config user.email)
    git add ./kernel-patches/patches/ ./config.sh ./kernel-config/
    git commit -m "Auto update to $overlay_branch ${kernel_version_full}-${date_tag}

Source of patches:
${quilt_branch_info}
Signed-off-by: ${user_name} <${user_email}>
"
    # show the commit info
    git log -n1

    set +x
    overlay_new_commit=$(git log --no-decorate --oneline -n1)
    # push commit to the remote repo
    git push origin $overlay_branch
    git log -3 --oneline --decorate
fi

popd

echo "OVERLAY_BRANCH=$overlay_branch" > IKT_OVERLAY_BUILD_TRIGGER.prop
echo "STAGING_REV=$KERNEL_QUILT_TAG" >> IKT_OVERLAY_BUILD_TRIGGER.prop
echo "OVERLAY_NAME=$OVERLAY_NAME" >> IKT_OVERLAY_BUILD_TRIGGER.prop
echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> IKT_OVERLAY_BUILD_TRIGGER.prop
echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> IKT_OVERLAY_BUILD_TRIGGER.prop # staging/{merge branch}

# Build Information Summary

cat << EOF
=================== Build Information Summary ====================
+
+    KVERSION:      ${KVERSION}
+    KPATCHLEVEL:   ${KPATCHLEVEL}
+    KSUBLEVEL:     ${KSUBLEVEL}
+    KEXTRAVERSION: ${KEXTRAVERSION}
+    KRTV:	        ${KRTV}
+
+    Quilt Tag:	     $KERNEL_QUILT_TAG
+                   (${quilt_branch_info})
+
+    Overlay Branch:  $overlay_branch
+                   (${overlay_new_commit})
+                   -- Pushed to the remote repo --
+
==================================================================
+                    *** SUCCESS ** END ***                      +
==================================================================
EOF

