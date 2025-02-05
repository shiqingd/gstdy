#!/bin/bash
export http_proxy="http://proxy-chain.intel.com:911/"
export https_proxy="http://proxy-chain.intel.com:912/"
export ftp_proxy="ftp://proxy-us.intel.com:911/"
export all_proxy="http://proxy-us.intel.com:911/"
export socks_proxy="socks://proxy-us.intel.com:1080/"
export no_proxy="intel.com,.intel.com,10.0.0.0/8,192.168.0.0/16,localhost,127.0.0.0/8,134.134.0.0/16,172.16.0.0/20"

# All of the variables inside the env_vars.txt
source env_vars.txt
export $(cut -d= -f1 env_vars.txt)
#export URL=$(python3 get_flashfiles.py $BASE_URL "sys_oak" "$SYS_OAK_CRED_AD")
#TODO fix this. The get_flashfiles.py seems to be failing to get the URL. So i temporarily disabled this
export URL=$BASE_URL
env

rm -rf /artifacts/*
cd /artifacts
git clone https://github.com/intel-innersource/os.linux.kernel.devops.ikit-dev-ops.git lkit-dev-ops

pushd lkit-dev-ops
git checkout master

# Remove for finalization

# Passwd must be set in the Docker container, or else it's treated as
# "expired" by sudo.

echo -e "blarg\nblarg" | passwd

# Set opt_reuse=no environment variable.

export reuse=no

# We have to generate the trust store, for whatever reason.

pkill clrtrust || true
rm -f /run/lock/clrtrust.lock
clrtrust generate

# For whatever reason, our gitconfig isn't working.
git config --global user.email "you@example.com"
git config --global user.name "Your Name"

bash -x acrn_sos_staging.sh -b $BRANCH -p $PRODUCT -r $opt_reuse -u $URL
popd

# Copy the artifacts to the artifacts folder.
rm -f artifacts/*
cp /artifacts/lkit-dev-ops/acrn-sos/acrn-ebtool/pub/sos_rootfs.img \
	/artifacts/sos_rootfs.img
cp /artifacts/lkit-dev-ops/acrn-sos/acrn-ebtool/pub/sos_boot.img \
	/artifacts/sos_boot.img

