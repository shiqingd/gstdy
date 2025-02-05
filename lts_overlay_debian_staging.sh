#!/bin/bash

DEBUG=true

if $DEBUG; then
	set -ex
else
	set -e
fi

WORKDIR=$(pwd)
OVERLAY_REPO="https://github.com/intel-innersource/os.linux.kernel.iot-kernel-overlay-staging.git"
OVERLAY_REPO_DIR="${WORKDIR}/$(basename $OVERLAY_REPO)"
KERNEL_QUILT_REPO_DIR="${WORKDIR}/$(basename $KERNEL_QUILT_REPO)"
KERNEL=$KERNEL
##KERNEL='5.10'
BUILD_ID=${BUILD_ID:='0'}
#lts_overlay_branch="lts2020-ubuntu"

quilt_branch=$(basename $STAGING_REV)
declare bullpen_build_true=` echo "$quilt_branch" | grep "bullpen" `
declare adl_beta_true=` echo "$quilt_branch" | grep "adl-beta" `

if [[ $KERNEL_VERSION == *rt* ]]; then
	if [ ${bullpen_build_true} ]; then
		lts_overlay_branch="lts2020-rt-bullpen-ubuntu"
	elif [ $adl_beta_true ]; then
		lts_overlay_branch="sandbox/linan/lts2020-rt-ADL-Beta-ubuntu"
	else
		lts_overlay_branch="lts2020-rt-ubuntu"
	fi
fi

if [[ $KERNEL_VERSION != *rt* ]]; then
  if [ ${bullpen_build_true} ]; then
	  lts_overlay_branch="lts2020-bullpen-ubuntu"
  elif [ $adl_beta_true ]; then
	  lts_overlay_branch="sandbox/fixissue_ADL_Beta"
  else
	  lts_overlay_branch="lts2020-ubuntu"
  fi
fi

# Step1. Clone the Kernel quilt patches
if [ -d $KERNEL_QUILT_REPO_DIR ]; then
	pushd $KERNEL_QUILT_REPO_DIR
	git clean -df
	git fetch origin
	git fetch --all --tags
	git checkout $STAGING_REV
	popd
else
	git clone $KERNEL_QUILT_REPO $KERNEL_QUILT_REPO_DIR
	pushd $KERNEL_QUILT_REPO_DIR
	git checkout $STAGING_REV
fi

# Get the full kernel version
pushd $KERNEL_QUILT_REPO_DIR
kernel_version_full=$KERNEL_VERSION
##kernel_version_full=$(git log --oneline -n1 | awk -F'to ' '{print $NF}')
quilt_branch_info=$(git log --no-decorate --oneline -n1)
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
# get 6 from 5.12.6
kernel_version_sublevel=$(echo $kernel_version | grep -oP "[0-9]+\.[0-9]+\.?\K([0-9]+)?") 
if [[ $kernel_extraversion == rc* ]]; then
	KEXTRAVERSION="-${kernel_extraversion}"
else
	KEXTRAVERSION=""
fi

if [[ $kernel_extraversion == rt* ]]; then
        KRTV="-${kernel_extraversion}"
else
        KRTV=""
fi

if [ -z $kernel_version_sublevel ]; then
	kernel_version_sublevel='0'
	kernel_version="${kernel_version}.0"
fi
KVERSION=$(echo $kernel_version|awk -F'.' '{print $1}')
KPATCHLEVEL=$(echo $kernel_version|awk -F'.' '{print $2}')
KSUBLEVEL=$(echo $kernel_version|awk -F'.' '{print $3}')

popd
# logging
echo "KVERSION:" $KVERSION
echo "KPATCHLEVEL:" $KPATCHLEVEL
echo "KSUBLEVEL:" $KSUBLEVEL
echo "KEXTRAVERSION:" $KEXTRAVERSION
echo "KRTV:" $KRTV

# Step2. Clone overlay code
if [ -d ${OVERLAY_REPO_DIR} ]; then
	pushd ${OVERLAY_REPO_DIR}
	git remote update origin --prune
	git clean -xdf
	git fetch origin
	git checkout $lts_overlay_branch
	git reset --hard origin/$lts_overlay_branch
	git pull --all --force
	popd
else
	git clone -b $lts_overlay_branch $OVERLAY_REPO $OVERLAY_REPO_DIR
fi

date_tag=$(basename $quilt_branch | awk -F'-' '{print $NF}')
data_MMDD=${date_tag:2:4}

# Step3. Copy quilt patches to overlay repo
pushd $OVERLAY_REPO_DIR
# 1. rm the old patches in overlay repo
rm -r ${OVERLAY_REPO_DIR}/kernel.overlay/patches/* 
# 2. copy quilt patches to overlay
cp ${KERNEL_QUILT_REPO_DIR}/patches/* ${OVERLAY_REPO_DIR}/kernel.overlay/patches/

# Step4. Generate build.sh scripts

BUILD_FILE=${OVERLAY_REPO_DIR}/build.sh
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

# Step5. add commit then push change to remote repo
if git diff --no-ext-diff --quiet ./kernel.overlay/ ./build.sh; then
	set +x
	echo "===== No changes found in the SOURCES and SPECS folder, No need to submit commit! ====="
	exit 1
fi
# get user information then submit commit.
user_name=$(git config user.name)
user_email=$(git config user.email)
git add ./kernel.overlay/ ./build.sh
if [ ${bullpen_build_true} ]; then
  bullpen_tag='-bullpen'
else
  bullpen_tag=''
fi
git commit -m "Auto update to lts-${kernel_version_full}${bullpen_tag}-${date_tag}

Source of patches:
${quilt_branch_info}

Signed-off-by: ${user_name} <${user_email}>
"
# show the commit info
git log -n1

set +x
overlay_new_commit=$(git log --no-decorate --oneline -n1)
# push commit to the remote repo
git push origin $lts_overlay_branch
popd

echo "OVERLAY_BRANCH=$lts_overlay_branch" > IKT_OVERLAY_BUILD_TRIGGER
echo "STAGING_REV=$STAGING_REV" >> IKT_OVERLAY_BUILD_TRIGGER

# Build Information Summary

cat << EOF

=================== Build Information Summary ====================
+
+    KVERSION:      ${KVERSION}
+    KPATCHLEVEL:   ${KPATCHLEVEL}
+    KSUBLEVEL:     ${KSUBLEVEL}
+    KEXTRAVERSION: ${KEXTRAVERSION}
+    KRTV:	    ${KRTV}
+
+    Quilt Tag:	     ${STAGING_REV}
+                   (${quilt_branch_info})
+
+    Overlay Branch:  $lts_overlay_branch
+                      (${overlay_new_commit})
+                   -- Pushed to the remote repo --
+
==================================================================
+                    *** SUCCESS ** END ***                      +
==================================================================
EOF



