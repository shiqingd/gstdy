#!/bin/bash
export http_proxy="http://proxy-us.intel.com:911/"
export https_proxy="https://proxy-us.intel.com:911/"
export ftp_proxy="ftp://proxy-us.intel.com:911/"
export all_proxy="http://proxy-us.intel.com:911/"
export socks_proxy="socks://proxy-us.intel.com:1080/"
export no_proxy="intel.com,.intel.com,10.0.0.0/8,192.168.0.0/16,localhost,127.0.0.0/8,134.134.0.0/16,172.16.0.0/20"
export HTTP_PROXY="http://proxy-us.intel.com:911/"
export HTTPS_PROXY="https://proxy-us.intel.com:911/"
export FTP_PROXY="ftp://proxy-us.intel.com:911/"
export ALL_PROXY="http://proxy-us.intel.com:911/"
export SOCKS_PROXY="socks://proxy-us.intel.com:1080/"
export NO_PROXY="intel.com,.intel.com,10.0.0.0/8,192.168.0.0/16,localhost,127.0.0.0/8,134.134.0.0/16,172.16.0.0/20"

export MYBUILDNUMBER=$BUILD_NUMBER
echo "Build number = $MYBUILDNUMBER"
echo "Build URL = $BUILD_URL"

rm -rf artifacts/*
#git clone --single-branch --branch ${SCRIPT_BRANCH} ssh://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/lkit-dev-ops
git clone --single-branch --branch ${SCRIPT_BRANCH} https://github.com/intel-innersource/os.linux.kernel.devops.ikit-dev-ops.git lkit-dev-ops
pushd lkit-dev-ops
bash -ex osit_staging.sh -p ${PRODUCT} -s clear_linux -b $BRANCH
cp /lkit-dev-ops/osit/${PRODUCT}-clear_linux/out/* /artifacts/ | true
IMAGE_FILE=$(ls /artifacts/*.tar.bz2)
echo "IMAGE_URL=${BUILD_URL}artifact/build_clear_on_clear${IMAGE_FILE}" > /artifacts/param.prop
popd

