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
BUILD_ID=${BUILD_ID:='0'}

quilt_branch=$(basename $STAGING_REV)
declare bullpen_build_true=` echo "$quilt_branch" | grep "bullpen" `

if [[ $KERNEL_VERSION == *rt* ]]; then
	if [ ${bullpen_build_true} ]; then
		KERNEL='lts2020_rt_bullpen'
		NAME='lts2020_rt_bullpen'
		lts2020_overlay_centos_branch="lts2020-rt-bullpen-centos"
	else
		KERNEL='lts2020_rt'
		NAME='lts2020_rt'
		lts2020_overlay_centos_branch="lts2020-rt-centos"
	fi
fi

if [[ $KERNEL_VERSION != *rt* ]]; then
	if [ ${bullpen_build_true} ]; then
		lts2020_overlay_centos_branch="lts2020-bullpen-centos"
		KERNEL='lts2020_bullpen'
		NAME='lts2020_bullpen'
	else
		lts2020_overlay_centos_branch="lts2020-centos"
		KERNEL='lts2020'
		NAME='lts2020'
	fi
fi

if [ -d $KERNEL_QUILT_REPO_DIR ]; then
	pushd $KERNEL_QUILT_REPO_DIR
	git reset --hard
	git clean -df
	git fetch origin
	git fetch --all --tags
	git checkout $STAGING_REV
	popd
else
	git clone  $KERNEL_QUILT_REPO $KERNEL_QUILT_REPO_DIR
	pushd $KERNEL_QUILT_REPO_DIR
	git checkout $STAGING_REV
	popd
fi

# Get the full kernel version
pushd $KERNEL_QUILT_REPO_DIR
kernel_version_full=$KERNEL_VERSION
quilt_branch_info=$(git log --no-decorate --oneline -n1)
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
else
        isrc=0
fi


if [ -z $kernel_version_sublevel ]; then
	kernel_version="${kernel_version}.0"
fi
popd
# logging
echo "kernel version:" $kernel_version
echo "extraverison:" $kernel_extraversion
echo "isrc:" $isrc

# Step2. Clone overlay code
if [ -d ${OVERLAY_REPO_DIR} ]; then
	pushd ${OVERLAY_REPO_DIR}
	git reset --hard
	git clean -df
	git remote update origin --prune
	git fetch origin
	git checkout ${lts2020_overlay_centos_branch}
	git pull --all --force
	popd
else
	git clone -b ${lts2020_overlay_centos_branch}  $OVERLAY_REPO $OVERLAY_REPO_DIR
fi

date_tag=$(basename $STAGING_REV | awk -F'-' '{print $NF}')
data_MMDD=${date_tag:2:4}

# Step3. Copy quilt patches to overlay repo
pushd $OVERLAY_REPO_DIR
# 1. rm the old patches in overlay repo
# rm -r ${OVERLAY_REPO_DIR}/SOURCES/patches/* 
# 2. copy quilt patches to overlay
# cp ${KERNEL_QUILT_REPO_DIR}/patches/* ${OVERLAY_REPO_DIR}/SOURCES/patches/
##### new fuction
# 1. rm the old patches.tar in overlay repo
rm ${OVERLAY_REPO_DIR}/SOURCES/patches.tar
# 2. copy quilt patches to overlay
pushd ${KERNEL_QUILT_REPO_DIR}
tar -zcf patches.tar patches/
cp patches.tar ${OVERLAY_REPO_DIR}/SOURCES/
rm patches.tar
popd

# Step4. Generate spec file
SPEC_FILE=${OVERLAY_REPO_DIR}/SPECS/iotg-kernel.spec
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
sed -i "/global kernel_src_tag/c %global kernel_src_tag ${kernel_version_full}" ${SPEC_FILE}
# Set the pkrelease
sed -i "/define pkgrelease/c %define pkgrelease  ${BUILD_ID}" ${SPEC_FILE}

# Step5. add commit then push change to remote repo
if git diff --no-ext-diff --quiet ./SOURCES/ README.md; then
	set +x
	echo "===== No changes found in the SOURCES and SPECS folder, No need to submit commit! ====="
	exit 1
fi

# get user information then submit commit.
user_name=$(git config user.name)
user_email=$(git config user.email)
git add SOURCES/ SPECS/ README.md

if [ ${bullpen_build_true} ]; then
	bullpen_tag='-bullpen'
else
	bullpen_tag=''
fi
git commit -m "Auto update to lts2020-${kernel_version_full}${bullpen_tag}-${date_tag}

Source of patches:
${quilt_branch_info}

Signed-off-by: ${user_name} <${user_email}>
"
# show the commit info
git log -n1

set +x
overlay_new_commit=$(git log --no-decorate --oneline -n1)
# push commit to the remote repo
git push origin ${lts2020_overlay_centos_branch}
popd

echo "OVERLAY_BRANCH=${lts2020_overlay_centos_branch}" > IKT_OVERLAY_BUILD_TRIGGER
echo "STAGING_REV=${quilt_branch}" >> IKT_OVERLAY_BUILD_TRIGGER
# Build Information Summary

cat << EOF

=================== Build Information Summary ====================
+
+    Kernel:        ${kernel_version}
+    Extraversion:  ${kernel_extraversion}
+    Isrc:          ${isrc}
+    Build_id:      ${BUILD_ID}
+
+    Quilt Branch:  ${KERNEL_QUILT_BRANCH}
+                   (${quilt_branch_info})
+
+    New Overlay:   ${lts2020_overlay_centos_branch}
		       		(${overlay_new_commit})
+                   -- Pushed to the remote repo --
+
==================================================================
+                    *** SUCCESS ** END ***                      +
==================================================================
EOF
