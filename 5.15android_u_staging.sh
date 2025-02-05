#!/bin/bash -ex
#this script is only for 5.15 android_u staing job

if [[ $pre_prod == "true" ]];then
    PREPROD="pre-prod-"
else
    PREPROD=""
fi

if [[ $DATE_TIME == "none" ]];then
    OPT_cve=false
    datestring=$(date +%y%m%d)T$(date +%H%M%S)Z
else
    OPT_cve=true
    datestring=${DATE_TIME}
fi

#generate datestring and STAGING_REV(actually, STAGING_REV is tag)
STAGING_REV=lts-${PREPROD}${BASELINE}-android_u-${datestring}
STAGING_REV_CVE=lts-${PREPROD}${BASELINE}-android_u-cve-${datestring}
#echo "datestring=$datestring"
#echo "STAGING_REV=$STAGING_REV"
#echo "STAGING_REV_CVE=$STAGING_REV_CVE"

#get clean repos which used for build/compiling
rm -fr kernel-lts-staging
rm -fr kernel-config
rm -fr kernel-lts-cve
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-config      kernel-config
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve     kernel-lts-cve

tags=""

if [[ $OPT_cve == true ]];then
  #switch to 5.15 branch in cve repo, which used for CVE-tag generation
  cd kernel-lts-cve
    git checkout 5.15

    #create tag for CVE content
    echo "tag_name is $STAGING_REV"
    git tag $STAGING_REV -m ""
    # gittag register: skip this tag
    git push origin $STAGING_REV
  cd -
fi

#create tag and cve-tag for compiling/build
cd kernel-lts-staging
  pwd

  if [[ $ANDROID_STAGING_BRANCH == none ]];then
    echo "git checkout 5.15/android_u"
    git checkout 5.15/android_u
  else
    echo "git checkout $ANDROID_STAGING_BRANCH"
    git checkout $ANDROID_STAGING_BRANCH
  fi

  KERNEL_VERSION=v$(make kernelversion)
  if [[ ${BASELINE} != $KERNEL_VERSION ]];then
    echo "please check Parameter BASELINE is correct or not"
    exit 1
  fi

if [[ $OPT_cve == "false" ]];then
  #create tag for compiling/build
  echo "tag_name is $STAGING_REV"
  git tag $STAGING_REV -m ""
  git push origin $STAGING_REV
  test $? -eq 0 && tags="${STAGING_REV}:1:1"
else
  #create cve-tag for compiling/build
  git quiltimport --series=../kernel-lts-cve/android_u/patches/series --patches=../kernel-lts-cve/android_u/patches/
  echo "cve tag_name is $STAGING_REV_CVE"
  git tag $STAGING_REV_CVE -m ""
  git push origin $STAGING_REV_CVE
  test $? -eq 0 && tags="$tags ${STAGING_REV_CVE}:3:1"
fi

cd -

#create tag and cve-tag for compiling/build
cd kernel-config
  pwd

  if [[ $CONFIG_STAGING_BRANCH == none ]];then
    echo "git checkout 5.15/config_u"
    git checkout 5.15/config_u
  else
    echo "git checkout $CONFIG_STAGING_BRANCH"
    git checkout $CONFIG_STAGING_BRANCH
  fi

  if [[ $OPT_cve == "false" ]];then
    #create tag for compiling/build
    echo "tag_name is $STAGING_REV"
    git tag $STAGING_REV -m ""
    git push origin $STAGING_REV
  else
    echo "tag_name is $STAGING_REV_CVE"
    git tag $STAGING_REV_CVE -m ""
    git push origin $STAGING_REV_CVE
  fi

cd -


for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
#generate prop file for downstream job, i.e., 5.15 android_u build job
if [[ $OPT_cve == false ]];then
  echo "STAGING_REV=$STAGING_REV" > 5.15android_u.prop
  echo "KERNEL=5.15lts" >> 5.15android_u.prop
  echo "STAGING_REV=$STAGING_REV" > message.txt
else
  echo "STAGING_REV=$STAGING_REV_CVE" > 5.15android_u_cve.prop
  echo "KERNEL=5.15lts" >> 5.15android_u_cve.prop
  echo "STAGING_REV_CVE=$STAGING_REV_CVE" > message.txt
fi

echo "[Staging][${BASELINE}][Android_U]${datestring}" > subject.txt
#echo "STAGING_REV=$STAGING_REV" > message.txt
#echo "STAGING_REV_CVE=$STAGING_REV_CVE" >> message.txt




