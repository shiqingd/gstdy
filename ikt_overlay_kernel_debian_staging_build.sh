#!/bin/bash -ex

CUR_DIR=$(pwd)
BUILD_ID=${BUILD_ID:='0'}  # BUILD_ID is jenkins job a environment variable

rm -rf ${CUR_DIR}/*.deb ${CUR_DIR}/kernel.config # delete old Artifact files

# clone the kernel.spec file and other source file
OVERLAY_REPO_DIR=${CUR_DIR}/iot-kernel-overlay-staging
KERNEL_CONFIG_DIR=$CUR_DIR/kernel-config
rm -rf ${OVERLAY_REPO_DIR}
rm -rf ${KERNEL_CONFIG_DIR}

git clone -b ${OVERLAY_BRANCH} ${OVERLAY_REPO} $OVERLAY_REPO_DIR
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-config.git $KERNEL_CONFIG_DIR

pushd ${KERNEL_CONFIG_DIR}
  result=$(git branch -a | grep $KERNEL_CONFIG_NAME) || :
  if [[ "$result" == "" ]]; then
    echo "Branch $KERNEL_CONFIG_NAME does not exist. will create!"
    git checkout --orphan $KERNEL_CONFIG_NAME
    git rm -rf .
    touch x86_64_defconfig
    git add .
    git commit -m "clear workspcace"
    git push origin HEAD:refs/heads/$KERNEL_CONFIG_NAME
  else
    echo "Branch $KERNEL_CONFIG_NAME exists."
    git checkout $KERNEL_CONFIG_NAME
  fi
popd

pushd ${OVERLAY_REPO_DIR}
    # 6.1lts / 6.6lts / 6.11mlt use old config file
    if [[ $STAGING_REV == *6.1.* || $STAGING_REV == *6.6.* || $STAGING_REV == *6.11* ]]; then
        ./build.sh ${STAGING_REV} ${BUILD_ID} ${OVERLAY_NAME}
        tar -czvf ${STAGING_REV}.tar.gz *.deb kernel.config
    # v6.12 and higher versions are required build rt / non-rt deb package
    else
        ./build.sh -r yes -t ${STAGING_REV} -b ${BUILD_ID} -c ${OVERLAY_NAME}
        mv kernel.config kernel-rt.config && tar -czvf ${STAGING_REV}_RT.tar.gz *.deb kernel-rt.config && rm *.deb
        ./build.sh -r no -t ${STAGING_REV} -b ${BUILD_ID} -c ${OVERLAY_NAME}
        tar -czvf ${STAGING_REV}_NON-RT.tar.gz *.deb kernel.config
    fi
    rm -fr $CUR_DIR/*.deb
    rm -fr $CUR_DIR/*.changes $CUR_DIR/*.upload $CUR_DIR/*.buildinfo

    ls -alh
    count=$(ls -1 *.deb 2>/dev/null | wc -l)
    [ $count != 0 ] && cp *.deb $CUR_DIR
    cp ./build/*.changes ./build/*.buildinfo $CUR_DIR/ || :

    [[ -e kernel.config ]] && cp kernel.config $CUR_DIR/
popd

#push update kernel-config file and push kernel-config tag
pushd ${KERNEL_CONFIG_DIR}
    rm -rf $KERNEL_CONFIG_DIR/*
    cp -r $CUR_DIR/kernel.config $KERNEL_CONFIG_DIR/x86_64_defconfig
    git add .
    git commit -m "Update kernel config for $STAGING_REV" || echo "git commit failed, continuing with the script."

    result=$(git tag -l | grep $STAGING_REV) || :
    if [[ "$result" == "" ]]; then
        echo "Tag $STAGING_REV does not exist."
        git tag $STAGING_REV -m ""
        git push origin HEAD:$KERNEL_CONFIG_NAME
        git push origin $STAGING_REV
    else
        echo "Tag $STAGING_REV exists."
    fi

popd

if [[ $UPLOAD_DEB_PACKAGE == "true" ]]; then
    pushd ${OVERLAY_REPO_DIR}
        dir=${STAGING_REV#sandbox-}
        rm -rf $dir
        mkdir $dir
        cp *.tar.gz $dir
        [[ $? != 0 ]] && exit 1
        cp *.config $dir
        [[ $? != 0 ]] && exit 1
        scp -r $dir sys_oak@oak-07.jf.intel.com:/var/www/html/ikt_kernel_deb_repo/pool/main/l/
        echo "EXTRA_DATA_PKG_URL=http://oak-07.jf.intel.com/ikt_kernel_deb_repo/pool/main/l/$dir"
    popd
fi

echo 'Done'

