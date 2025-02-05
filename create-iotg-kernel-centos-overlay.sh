#!/bin/bash
set -ex

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
  tar -zcf patches.tar patches/
popd
echo "Clone the kernel quilt patches...Done!"

echo "Clone the kernel overlay..."
git clone $OVERLAY_REPO $OVERLAY_DIR
echo "Clone the kernel overlay...Done"

pushd $OVERLAY_DIR

# Switch to overlay branch
if [ $(git branch -r | grep -w origin/$overlay_branch | wc -l) -gt 0 ]; then
        git checkout $overlay_branch
        git fetch origin --tags
        git pull
else
        git checkout -b $overlay_branch origin/$OVERLAY_TEMPLATE_TAG
fi

rm -rf $OVERLAY_DIR/SOURCES/kernel-config/
mkdir -p $OVERLAY_DIR/SOURCES/kernel-config/
# Get config files from kernel-config repo
if [ -d $KCFG_DIR/overlay/base-os -a -d $KCFG_DIR/overlay/features -a -d $KCFG_DIR/overlay/overlay ]; then
        cp -rf $KCFG_DIR/overlay/* $OVERLAY_DIR/SOURCES/kernel-config/
        if [[ $KSRC_UPSTREAM_TAG == *rt* ]]; then
                echo "rf.cfg is included."
        else
                rm $OVERLAY_DIR/SOURCES/kernel-config/features/rt.cfg || :
                rm $OVERLAY_DIR/SOURCES/kernel-config/features/rt-*.cfg || :
        fi
else
        echo "config for overlay does not exist, please checking ..."
        exit 1
fi

BUILD_ID=${BUILD_ID:='0'}

if [[ $OVERLAY_NAME = lts2020 ]]; then
        KERNEL='lts2020'
        NAME='lts2020'
        #overlay_branch="lts2020-centos"

elif [[ $OVERLAY_NAME = lts2020_rt ]]; then
        KERNEL='lts2020_rt'
        NAME='lts2020_rt'
        #overlay_branch="lts2020-rt-centos"

elif [[ $OVERLAY_NAME = iotg-next ]]; then
        KERNEL='iotg_next'
        NAME='iotg-next'
        #overlay_branch="iotg-next-centos"

elif [[ $OVERLAY_NAME = mainline-tracking ]]; then
        KERNEL='mainline_tracking'
        NAME='mainline-tracking'
        #overlay_branch="mainline-tracking-centos"

elif [[ $OVERLAY_NAME = lts2021 ]]; then
        KERNEL='lts2021'
        NAME='lts2021'
        #overlay_branch="lts2021-centos"

elif [[ $OVERLAY_NAME = lts2021_rt ]]; then
        KERNEL='lts2021_rt'
        NAME='lts2021_rt'
        #overlay_branch="lts2021-rt-centos"

elif [[ $OVERLAY_NAME = lts2022 ]]; then
        KERNEL='lts2022'
        NAME='lts2022'
        #overlay_branch="lts2022-centos"

else
        echo "$OVERLAY_NAME is not defined. "
        exit 1
fi
 
if [[ $OVERLAY_NAME = iotg-next || $OVERLAY_NAME = mainline-tracking ]]; then
	kernel_src_repo='https://github.com/torvalds/linux.git'
elif [[ $OVERLAY_NAME = 'lts2021_rt' || $OVERLAY_NAME = 'lts2020_rt'  ]]; then
    kernel_src_repo='https://git.kernel.org/pub/scm/linux/kernel/git/rt/linux-stable-rt.git'
else
	kernel_src_repo='https://kernel.googlesource.com/pub/scm/linux/kernel/git/stable/linux.git'
fi

# Get the full kernel version
kernel_version_full=$KSRC_UPSTREAM_TAG
# check version info
if [[ ! $kernel_version_full == v* ]]; then
        echo "===== Error: Full kernel version $kernel_version_full is not the result we want ! ====="
        exit 1
else
        echo "===== Get the full kernel version: $kernel_version_full ====="
fi

# Get version/extraversion/subleaver information of the kernel
# get 5.12 from v5.12.6-rc3
kernel_version=$(echo ${kernel_version_full##v} | awk -F'-' '{print $1}')
# get rc3 from v5.12.6-rc3
kernel_extraversion=$(echo ${kernel_version_full##v} | awk -F'-' '{print $2}')
# get 6 from 5.12.6
kernel_version_sublevel=$(echo $kernel_version | grep -oP "[0-9]+\.[0-9]+\.?\K([0-9]+)?")
if [[ $kernel_extraversion == rc* ]]; then
        isrc=1
else
        isrc=0
fi

if [[ $kernel_extraversion == rt* ]]; then
        isrc=1
fi
#else
#        isrc=0
#fi

if [ -z $kernel_version_sublevel ]; then
        kernel_version="${kernel_version}.0"
fi

# logging
echo "kernel version:" $kernel_version
echo "extraverison:" $kernel_extraversion
echo "isrc:" $isrc
echo "kernel source repo:" ${kernel_src_repo}

date_tag=$(basename $STAGING_REV | awk -F'-' '{print $NF}')
data_MMDD=${date_tag:2:4}

# Copy quilt patches to overlay repo
# 1. rm the old patches.tar in overlay repo
rm ${OVERLAY_DIR}/SOURCES/patches.tar || :
# 2. copy quilt patches to overlay
cp ${KSRC_DIR}/patches.tar ${OVERLAY_DIR}/SOURCES/
rm ${KSRC_DIR}/patches.tar || :

# Generate spec file
SPEC_FILE=${OVERLAY_DIR}/SPECS/iotg-kernel.spec
if [ ! -f $SPEC_FILE ]; then
        echo "Error: ${SPEC_FILE} no such file."
        exit 1
fi

# Set the Name
sed -i "/^Name: /c Name: ${NAME}%{?variant}" ${SPEC_FILE}
# Set the rpmversion plus .0
sed -i "/define rpmversion/c %define rpmversion  ${kernel_version}" ${SPEC_FILE}
# Set the rc version
sed -i "/define rcversion/c %define rcversion   ${kernel_extraversion}." ${SPEC_FILE}
# Set isrc
sed -i "/global isrc/c %global isrc ${isrc}" ${SPEC_FILE}
# Set embargo name
sed -i "/define embargoname/c %define embargoname ${data_MMDD}.${KERNEL}" ${SPEC_FILE}
# Set spec release
sed -i "/define specrelease/c %define specrelease %{?rcversion}${date_tag}_%{pkgrelease}%{?dist}" ${SPEC_FILE}
# Set the kernel src
sed -i "/global kernel_src_repo/c %global kernel_src_repo ${kernel_src_repo}" ${SPEC_FILE}
sed -i "/global kernel_src_tag/c %global kernel_src_tag ${kernel_version_full}" ${SPEC_FILE}
# Set the pkrelease
##sed -i "/define pkgrelease/c %define pkgrelease  ${BUILD_ID}" ${SPEC_FILE}

# Step5. add commit then push change to remote repo
if git diff --no-ext-diff --quiet ./SOURCES/ README.md; then
        set +x
        echo "===== No changes found in the SOURCES and SPECS folder, No need to submit commit! ====="
        #exit 1
fi

# modifing the README.md --only iotg-next have embargo warning
if [ ! "$NAME" = "iotg-next" ]; then
        if [[ $t == WARNING ]];then
                sed -i '1,5d' README.md
        fi
fi

# get user information then submit commit.
user_name=$(git config user.name)
user_email=$(git config user.email)
git add SOURCES/ SPECS/ README.md
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
popd

echo "OVERLAY_BRANCH=${overlay_branch}" > IKT_OVERLAY_BUILD_TRIGGER
echo "STAGING_REV=${KERNEL_QUILT_TAG}" >> IKT_OVERLAY_BUILD_TRIGGER
echo "OVERLAY_NAME=$OVERLAY_NAME" >> IKT_OVERLAY_BUILD_TRIGGER
echo "UPLOAD_RPM_PACKAGE=$UPLOAD_RPM_PACKAGE" >> IKT_OVERLAY_BUILD_TRIGGER
# Build Information Summary

cat << EOF

=================== Build Information Summary ====================
+
+    Kernel:        ${kernel_version}
+    Extraversion:  ${kernel_extraversion}
+    Isrc:          ${isrc}
+
+    Quilt Tag:     ${KERNEL_QUILT_TAG}
+                   (${quilt_branch_info})
+
+    New Overlay:   ${overlay_branch}
                    (${overlay_new_commit})
+                   -- Pushed to the remote repo --
+
==================================================================
+                    *** SUCCESS ** END ***                      +
==================================================================
EOF

