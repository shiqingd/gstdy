#!/bin/bash -ex

rm -fr OpenHarmony
mkdir -p OpenHarmony
pushd OpenHarmony
  repo init -u https://github.com/intel-sandbox/os.openharmony.manifests.git -b "${MANIFEST_BRANCH}"
  repo sync -c --force-sync --repo-upgraded || repo sync -c --force-sync --repo-upgraded || repo sync -c --force-sync --repo-upgraded || repo sync -c --force-sync --repo-upgraded || repo sync -c --force-sync --repo-upgraded || repo sync -c --force-sync --repo-upgraded
  repo forall -c 'git lfs pull'

  bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002 || bash build/prebuilts_download.sh --tool-repo http://10.238.151.67:32001 --pypi-url http://mirrors.huaweicloud.com/repository/pypi/simple --npm-registry http://10.238.151.87:32002

  repo manifest -r -o "${OHOS_MANIFEST}"
  cp -f "${OHOS_MANIFEST}" /home/jenkins/jenkins/workspace/
  ./vendor/intel/common/apply_patch.sh |& tee apply_patch_daily_${BUILD_ID}.log
  repo manifest -r -o my_manifest_after_patch.xml

  hb build --product-name adl --skip-partlist-check --load-test-config=false  --archive-image adl_image --ccache
  sudo ./vendor/intel/common/mk_disk.sh || :
  if [[ -d out/adl/packages/phone/images/ ]];then
    pushd out/adl/packages/phone/images/
      tar -zcvf ohos_raw.img.tar.gz ohos_raw.img || :
    popd
  fi

  pushd test/xts/acts
    echo "current directory is:"
    pwd
    ./build.sh product_name=adl system_size=standard target_arch=x86_64 |& tee acts_${BUILD_ID}.log
  popd

  pushd test/xts/hats
    echo "current directory is:"
    pwd
    ./build.sh product_name=adl system_size=standard target_arch=x86_64 |& tee hats_${BUILD_ID}.log
  popd

  pushd test/xts/dcts
    echo "current directory is:"
    pwd
    ./build.sh product_name=adl system_size=standard target_arch=x86_64 |& tee dcts_${BUILD_ID}.log
  popd

  ./vendor/intel/common/clean_patch.sh
  repo manifest -r -o my_manifest_after_clean_patch.xml

popd

echo "Done, please check apply_patch.log, if there are conflicts or not."

if [[ -f OpenHarmony/out/adl/packages/phone/images/ohos_raw.img.tar.gz ]]; then
  rm -fr os.openharmony.manifests
  git clone https://github.com/intel-sandbox/os.openharmony.manifests --branch "${MANIFEST_BRANCH}"
  cd os.openharmony.manifests
    md5sum_old=$(md5sum latest-manifest.xml | awk '{print $1}')
    md5sum_new=$(md5sum ../OpenHarmony/${OHOS_MANIFEST} | awk '{print $1}')
    if [[ $md5sum_old != $md5sum_new ]]; then
      cp ../OpenHarmony/${OHOS_MANIFEST} latest-manifest.xml
      git add .
      git commit -m "update latest-manifest.xml from ${STAGING_REV}"
      git push --dry-run origin "${MANIFEST_BRANCH}"
      git push origin "${MANIFEST_BRANCH}"
    fi
  cd -
fi

pushd OpenHarmony/out/adl
    tar -zcvf suites_${BUILD_ID}.tar.gz suites/ || :
popd

