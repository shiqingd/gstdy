#!/bin/bash -ex

rm -fr OpenHarmony
mkdir -p OpenHarmony
pushd OpenHarmony
  /home/jenkins/bin/repo init -u https://github.com/intel-sandbox/os.openharmony.manifests.git -b ${MANIFEST_BRANCH}
  /home/jenkins/bin/repo sync -c --fail-fast || /home/jenkins/bin/repo sync -c --fail-fast || /home/jenkins/bin/repo sync -c --fail-fast || /home/jenkins/bin/repo sync -c --fail-fast || /home/jenkins/bin/repo sync -c --fail-fast || /home/jenkins/bin/repo sync -c --fail-fast
  /home/jenkins/bin/repo forall -vp -c 'git lfs pull'

  bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002

  /home/jenkins/bin/repo manifest -r -o ${OHOS_MANIFEST}
  cp -f ${OHOS_MANIFEST} /home/jenkins/jenkins/workspace/

  ./vendor/intel/common/apply_patch.sh |& tee apply_patch_${BUILD_ID}.log

  hb build --product-name adl --skip-partlist-check --load-test-config=false  --archive-image adl_image --ccache

popd

echo "Done, please check apply_patch.log, if there are conflicts or not."

rm -fr os.openharmony.manifests
git clone https://github.com/intel-sandbox/os.openharmony.manifests
tags=""
cd os.openharmony.manifests
    git checkout ${MANIFEST_BRANCH}
    md5sum_old=$(md5sum latest-manifest.xml | awk '{print $1}')
    md5sum_new=$(md5sum ../OpenHarmony/${OHOS_MANIFEST} | awk '{print $1}')
    if [[ $md5sum_old != $md5sum_new ]]; then
        cp -r /home/jenkins/jenkins/workspace/${OHOS_MANIFEST} latest-manifest.xml
        git add latest-manifest.xml
        git commit -m "update latest-manifest.xml from ${STAGING_REV}"
        git push --dry-run origin ${MANIFEST_BRANCH}
        git push origin OpenHarmony-4.1-Release
    fi
    git tag ${STAGING_REV} -m ""
    git push --dry-run origin ${STAGING_REV}
    git push origin ${STAGING_REV}
    test $? -eq 0 && tags="${STAGING_REV}:1:1"
cd -

rm -fr os.openharmony.kernel_linux_linux-5.10
git clone https://github.com/intel-sandbox/os.openharmony.kernel_linux_linux-5.10
SHA1=$(cat /home/jenkins/jenkins/workspace/${OHOS_MANIFEST} | grep os.openharmony.kernel_linux_linux-5.10 | awk '{print $5}')
SHA1=${SHA1#*\"}
SHA1=${SHA1%\"}
BRANCH=$(cat /home/jenkins/jenkins/workspace/${OHOS_MANIFEST} | grep os.openharmony.kernel_linux_linux-5.10 | awk '{print $6}')
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
