#!/bin/bash -ex

#cp -f /home/jenkins/jenkins/workspace/${OHOS_MANIFEST} .

rm -fr os.openharmony.manifests
git clone https://github.com/intel-sandbox/os.openharmony.manifests
cd os.openharmony.manifests
    git checkout OpenHarmony-4.1-Release
    #md5sum_old=$(md5sum latest-manifest.xml | awk '{print $1}')
    #md5sum_new=$(md5sum ../${OHOS_MANIFEST} | awk '{print $1}')
    #if [[ $md5sum_old != $md5sum_new ]]; then
        #cp -r /home/jenkins/jenkins/workspace/${OHOS_MANIFEST} latest-manifest.xml
        #git add latest-manifest.xml
        #git commit -m "update latest-manifest.xml from ${STAGING_REV}"
        #git push --dry-run origin ${MANIFEST_BRANCH}
        #git push origin OpenHarmony-4.1-Release
    #fi

    staging_tag_name=${STAGING_REV/Release/Staging}
    git reset --hard ${staging_tag_name}
    cp -f latest-manifest.xml ../${OHOS_MANIFEST}
    git tag ${STAGING_REV} -m ""
    git push --dry-run origin ${STAGING_REV}
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.device_board_intel
git clone https://github.com/intel-sandbox/os.openharmony.device_board_intel
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.device_board_intel | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.device_board_intel | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.device_board_intel
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.device_soc_intel
git clone https://github.com/intel-sandbox/os.openharmony.device_soc_intel
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.device_soc_intel | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.device_soc_intel | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.device_soc_intel
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV} 
cd -

tags=""
rm -fr os.openharmony.kernel_linux_linux-5.10
git clone https://github.com/intel-sandbox/os.openharmony.kernel_linux_linux-5.10
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.kernel_linux_linux-5.10 | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.kernel_linux_linux-5.10 | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.kernel_linux_linux-5.10 
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
    test $? -eq 0 && tags="${STAGING_REV}:1:2"
cd -
for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

rm -fr os.openharmony.third_party_bluez
git clone https://github.com/intel-sandbox/os.openharmony.third_party_bluez
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_bluez | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_bluez | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.third_party_bluez
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.third_party_glmark2
git clone https://github.com/intel-sandbox/os.openharmony.third_party_glmark2
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_glmark2 | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_glmark2 | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.third_party_glmark2
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.third_party_libpciaccess
git clone https://github.com/intel-sandbox/os.openharmony.third_party_libpciaccess
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_libpciaccess | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_libpciaccess | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.third_party_libpciaccess
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.third_party_mesa3d
git clone https://github.com/intel-sandbox/os.openharmony.third_party_mesa3d
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_mesa3d | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_mesa3d | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.third_party_mesa3d
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.third_party_minigbm
git clone https://github.com/intel-sandbox/os.openharmony.third_party_minigbm
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_minigbm | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_minigbm | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.third_party_minigbm
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}  
cd -

rm -fr os.openharmony.third_party_pciids
git clone https://github.com/intel-sandbox/os.openharmony.third_party_pciids
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_pciids | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.third_party_pciids | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.third_party_pciids
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -

rm -fr os.openharmony.vendor_intel
git clone https://github.com/intel-sandbox/os.openharmony.vendor_intel
SHA1=$(cat ${OHOS_MANIFEST} | grep os.openharmony.vendor_intel | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat ${OHOS_MANIFEST} | grep os.openharmony.vendor_intel | awk '{print $6}')
BRANCH=${BRANCH#*\"}
BRANCH=${BRANCH%\"}
cd os.openharmony.vendor_intel 
    git checkout ${BRANCH}
    git tag ${STAGING_REV} ${SHA1} -m ""
    git push origin ${STAGING_REV}
cd -


