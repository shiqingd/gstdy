#!/bin/bash -ex

KERNEL_SRC_BRANCH=$1
KERNEL_SRC_TAG=$2

if [ -z $KERNEL_SRC_BRANCH ]; then
	echo "error: parameters are not set !!!"
	exit 1
fi

WORKSPACE="$(cd $(dirname $0); pwd)"

#rm -fr $WORKSPACE/kernel-lts-staging
if [ ! -d $WORKSPACE/kernel-lts-staging ] ; then
	git clone -b ${KERNEL_SRC_BRANCH} https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git kernel-lts-staging
	pushd $WORKSPACE/kernel-lts-staging
	git fetch --all --tags -f
	popd
else
	pushd $WORKSPACE/kernel-lts-staging
	git remote prune origin
	git clean -xdf
	git reset --hard
	git fetch --all --tags -f
        git checkout -b ${KERNEL_SRC_BRANCH} origin/${KERNEL_SRC_BRANCH} || git checkout ${KERNEL_SRC_BRANCH}
        git reset --hard origin/${KERNEL_SRC_BRANCH}
	popd
fi

#rm -fr $WORKSPACE/kernel-dev-quilt
if [ ! -d $WORKSPACE/kernel-dev-quilt ] ; then
	git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt.git kernel-dev-quilt
else
	pushd $WORKSPACE/kernel-dev-quilt
	git remote prune origin
	git clean -xdf
	git fetch origin -f --tags
	git checkout -b ${KERNEL_SRC_BRANCH} origin/${KERNEL_SRC_BRANCH} || git checkout ${KERNEL_SRC_BRANCH}
        git reset --hard origin/${KERNEL_SRC_BRANCH}
	popd
fi

pushd $WORKSPACE/kernel-lts-staging
#git tag
datestring=$(date -u)
datetime=$(date -d "$datestring" -u +%g%m%dT%H%M%SZ)
staging_tag=lts-v5.15.21-rplp-po-$datetime
git tag $staging_tag
git push origin $staging_tag

#create quilt
git format-patch origin/5.15/rplp/int..${KERNEL_SRC_BRANCH} --suffix=.$datetime
if [ ! -e *${datetime}* ]; then
	echo 'base does not have patches to quiltify'
else
	ls *${datetime}* > files
	cp *${datetime}* $WORKSPACE/kernel-dev-quilt/patches
	cat files >> $WORKSPACE/kernel-dev-quilt/patches/series
fi
popd

pushd $WORKSPACE/kernel-dev-quilt
if [ "$(git diff ./patches/ )" ]; then
      git add $WORKSPACE/kernel-dev-quilt/patches/series
      git add $WORKSPACE/kernel-dev-quilt/patches/*${datetime}*
      git commit -m "Staging quilt for: $staging_tag "
fi    
git tag $staging_tag
git push origin $staging_tag
git push origin HEAD:${KERNEL_SRC_BRANCH}
popd

echo KERNEL_QUILT_TAG=$staging_tag > overlay_build.prop
echo KSRC_UPSTREAM_TAG="v5.15.21" >> overlay_build.prop
