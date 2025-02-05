#!/usr/bin/bash -ex

#qingdong.shi@intel.com, 2024_SEP

rm -fr tiberlinuxos
git clone https://github.com/intel-innersource/os.linux.tiberos.tiberlinuxos.git tiberlinuxos
pushd tiberlinuxos
    git checkout 3.0
    #git reset --hard 6428ac58f
    git log -1
popd


rm -fr os.linux.kernel.kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging
pushd os.linux.kernel.kernel-lts-staging
    git reset --hard "${STAGING_REV}"
popd

cp -f os.linux.kernel.kernel-lts-staging/Intel/config tiberlinuxos/SPECS/kernel/config

if [[ $STAGING_REV == *tiber*cve* ]];then
  rsync -a  --exclude '.*' os.linux.kernel.kernel-lts-staging/* ./${STAGING_REV}
  tar -cvzf ${STAGING_REV}.tar.gz ${STAGING_REV}
  cp -f ${STAGING_REV}.tar.gz tiberlinuxos/SPECS/kernel/
else
  wget https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES/${STAGING_REV}.tar.gz
fi

echo "display CONFIGHASH sha256sum value"
CONFIGHASH=$(sha256sum tiberlinuxos/SPECS/kernel/config | awk '{print $1}'); echo "$CONFIGHASH"

echo "display SOURCEHASH sha256sum value"
SOURCEHASH=$(sha256sum ${STAGING_REV}.tar.gz | awk '{print $1}') ; echo "$SOURCEHASH"

pushd tiberlinuxos/SPECS/kernel/
  sed -i 's/  "config": .*/  "config": "'"$CONFIGHASH"'",/' kernel.signatures.json
  sed -i 's/  ".*tar.gz": .*/  "'"$STAGING_REV"'.tar.gz": "'"$SOURCEHASH"'"/' kernel.signatures.json
  sed -i 's/^Version.*/Version:        '"$BASELINE"'/' kernel.spec

  if [[ $STAGING_REV == *tiber*cve* ]];then
    sed -i 's/^Release.*/Release:        '"${datetime}_cve"'%{?dist}/' kernel.spec
    sed -i '/^Patch/d' kernel.spec #if corresponding .tar.gz includes CVE patches, use this line
  else
    sed -i 's/^Release.*/Release:        '"$datetime"'%{?dist}/' kernel.spec
    sed -i '/^Patch/d' kernel.spec  # Non-CVE , should use this line
  fi

  if [[ $STAGING_REV == *tiber*cve* ]];then
    sed -i 's/^Source0.*/Source0:        '"$STAGING_REV"'.tar.gz/' kernel.spec
  else
    sed -i 's/^Source0.*/Source0:        https:\/\/af01p-png-app03.devtools.intel.com\/artifactory\/tiberos-packages-png-local\/CM2\/SOURCES\/'"$STAGING_REV"'.tar.gz/' kernel.spec
  fi

  sed -i 's/^%setup -q -n.*/%setup -q -n '"${STAGING_REV}"'/' kernel.spec
  sed -i 's/^%autosetup -p1 -n.*/%autosetup -p1 -n '"${STAGING_REV}"'/' kernel.spec
popd

pushd tiberlinuxos/toolkit
    #sudo make build-packages REBUILD_TOOLS=y CONFIG_FILE= SPECS_DIR=../SPECS SOURCE_URL=https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES PACKAGE_REBUILD_LIST="kernel"
    sudo make build-packages REBUILD_TOOLS=y SRPM_PACK_LIST="kernel"
    sudo make image REBUILD_TOOLS=y REBUILD_PACKAGES=n CONFIG_FILE=./imageconfigs/tiber-image-dev.json
popd

if [[ "$UPLOAD_RPM_PACKAGE" == "true" ]]; then
    mkdir -p ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/SPECS/kernel/config ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/SPECS/kernel/kernel.s* ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/out/RPMS/x86_64/kernel-6*x86_64.rpm ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/out/RPMS/x86_64/*driver* ${STAGING_REV}_${BUILD_NUMBER}
    cp -r tiberlinuxos/out/RPMS ${STAGING_REV}_${BUILD_NUMBER}
    cp -r tiberlinuxos/out/images ${STAGING_REV}_${BUILD_NUMBER}
    scp -r ${STAGING_REV}_${BUILD_NUMBER} sys_oak@oak-07.jf.intel.com:/var/www/html/ikt_kernel_deb_repo/pool/main/l/
fi


