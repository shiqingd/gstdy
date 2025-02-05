#!/usr/bin/bash -ex

datetime=${STAGING_REV##*-}
export datetime=${datetime}
echo "datetime=$datetime"
echo "BASELINE=$BASELINE"
echo "STAGING_REV=$STAGING_REV"
echo "WORKSPACE=$WORKSPACE"
RT_VERSION=${BASELINE##*-}
echo "RT_VERSION=${RT_VERSION}"


rm -fr tiberlinuxos
git clone https://github.com/intel-innersource/os.linux.tiberos.tiberlinuxos.git tiberlinuxos
pushd tiberlinuxos
    git checkout 3.0
    git log -1
popd

rm -fr os.linux.kernel.kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging
pushd os.linux.kernel.kernel-lts-staging
    git reset --hard ${STAGING_REV}
    KERNELVERSION=$(make kernelversion)
popd

cp -f os.linux.kernel.kernel-lts-staging/Intel/config-rt tiberlinuxos/SPECS/kernel-rt/config

if [[ $STAGING_REV == *tiber*cve* ]];then
  rsync -a  --exclude '.*' os.linux.kernel.kernel-lts-staging/* ./${STAGING_REV}
  tar -cvzf ${STAGING_REV}.tar.gz ${STAGING_REV}
  cp -f ${STAGING_REV}.tar.gz tiberlinuxos/SPECS/kernel-rt/
else
  wget https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES/${STAGING_REV}.tar.gz
fi

echo "display CONFIGHASH sha256sum value"
CONFIGHASH=$(sha256sum tiberlinuxos/SPECS/kernel-rt/config | awk '{print $1}'); echo $CONFIGHASH

echo "display SOURCEHASH sha256sum value"
SOURCEHASH=$(sha256sum ${STAGING_REV}.tar.gz | awk '{print $1}') ; echo  $SOURCEHASH

pushd tiberlinuxos/SPECS/kernel-rt/
  sed -i 's/  "config": .*/  "config": "'"$CONFIGHASH"'",/' kernel-rt.signatures.json
  sed -i 's/  ".*tar.gz": .*/  "'"$STAGING_REV"'.tar.gz": "'"$SOURCEHASH"'"/' kernel-rt.signatures.json
  sed -i 's/^Version.*/Version:        '"$KERNELVERSION"'/' kernel-rt.spec

  if [[ $STAGING_REV == *tiber*cve* ]];then
    sed -i 's/^Release.*/Release:        '"${datetime}_RT_cve"'%{?dist}/' kernel-rt.spec
    sed -i '/^Patch/d' kernel-rt.spec
  else
    sed -i 's/^Release.*/Release:        '"${datetime}_RT"'%{?dist}/' kernel-rt.spec
    sed -i '/^Patch/d' kernel-rt.spec
  fi

  sed -i 's/^%define uname_r .*/%define uname_r %{version}-'"${RT_VERSION}"'-%{release}/' kernel-rt.spec

  if [[ $STAGING_REV == *tiber*cve* ]];then
    sed -i 's/^Source0.*/Source0:        '"$STAGING_REV"'.tar.gz/' kernel-rt.spec
  else
    sed -i 's/^Source0.*/Source0:        https:\/\/af01p-png-app03.devtools.intel.com\/artifactory\/tiberos-packages-png-local\/CM2\/SOURCES\/'"$STAGING_REV"'.tar.gz/' kernel-rt.spec
  fi

  sed -i 's/^%setup -q -n.*/%setup -q -n '"${STAGING_REV}"'/' kernel-rt.spec
  sed -i 's/^%autosetup -p1 -n.*/%autosetup -p1 -n '"${STAGING_REV}"'/' kernel-rt.spec
popd

pushd tiberlinuxos/toolkit
    #sudo make build-packages REBUILD_TOOLS=y CONFIG_FILE= SPECS_DIR=../SPECS SOURCE_URL=https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES PACKAGE_REBUILD_LIST="kernel-rt"
    sudo make build-packages REBUILD_TOOLS=y SRPM_PACK_LIST="kernel-rt"
    sudo make image REBUILD_TOOLS=y REBUILD_PACKAGES=n CONFIG_FILE=./imageconfigs/tiber-image-rt-dev.json
popd

if [[ "$UPLOAD_RPM_PACKAGE" == "true" ]]; then
    mkdir -p ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/SPECS/kernel-rt/config ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/SPECS/kernel-rt/kernel-rt.s* ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/out/RPMS/x86_64/kernel-rt-6*x86_64.rpm ${STAGING_REV}_${BUILD_NUMBER}
    cp tiberlinuxos/out/RPMS/x86_64/*driver* ${STAGING_REV}_${BUILD_NUMBER}
    cp -r tiberlinuxos/out/RPMS ${STAGING_REV}_${BUILD_NUMBER}
    cp -r tiberlinuxos/out/images ${STAGING_REV}_${BUILD_NUMBER}
    scp -r ${STAGING_REV}_${BUILD_NUMBER} sys_oak@oak-07.jf.intel.com:/var/www/html/ikt_kernel_deb_repo/pool/main/l/
fi


