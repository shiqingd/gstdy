#!/bin/bash -ex

rm -rf Android
mkdir -p Android

pushd Android
  /home/jenkins/bin/repo.google init -u https://github.com/intel-innersource/os.android.bsp-gordon-peak.manifests -b android/u/bxtp_ivi/master -m r1
  cp -f $WORKSPACE/manifests/${MANIFEST_FILE} .repo/manifests/
  /home/jenkins/bin/repo.google init -m ${MANIFEST_FILE}
  /home/jenkins/bin/repo.google sync -cq  --fail-fast --force-sync
  /home/jenkins/bin/repo.google forall -vp -c 'git lfs pull'

  /home/jenkins/bin/repo.google manifest -r -o 5.15_android_u_manifest_original.xml #save original manifest

  #if not baseline, replace kernel code and kernel config
  if [[ $baseline == "False" ]]; then
    cd kernel
      rm -fr lts2018
      git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging lts2018 --branch ${STAGING_REV}
    cd -

    cd kernel/config-lts
      rm -fr lts2018
      git clone https://github.com/intel-innersource/os.linux.kernel.kernel-config lts2018 --branch ${STAGING_REV}
    cd -
  fi

  /home/jenkins/bin/repo.google manifest -r -o 5.15_u_manifest.xml #save manifest

  #workaround start:
    #fix lz4 issues
    #cp -f device/intel/mixins/groups/kernel/AndroidBoard.mk device/intel/mixins/groups/kernel/AndroidBoard_bak.mk
    #cp -f /home/jenkins/AndroidBoard.mk_u ./device/intel/mixins/groups/kernel/AndroidBoard.mk
  #end of workaround

  source build/envsetup.sh
  echo $?
  echo "the source result is above"

  lunch gordon_peak-userdebug
  echo $?
  echo "the lunch result is above"

  cp -f vendor/intel/abl/abl_build_tools/iasimage.py vendor/intel/abl/abl_build_tools/iasimage.py_bak
  sed -i 's^/usr/lib/python2.7/dist-packages^/home/jenkins/.local/lib/python3.10/site-packages^' vendor/intel/abl/abl_build_tools/iasimage.py

  #mixinup

  make flashfiles
  echo $?
  echo "make flashfiles result is above"

  pushd kernel/lts2018/
    git log --oneline -1 > kernel_code_HEAD.txt
  popd

popd

