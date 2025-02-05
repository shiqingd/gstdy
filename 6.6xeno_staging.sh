#!/bin/bash -ex
#this script is only for 6.6xenomai staing job

#generate datestring and STAGING_REV(actually, STAGING_REV is tag)
datestring=$(date +%y%m%d)T$(date +%H%M%S)Z
STAGING_REV=lts-${BASELINE}-xenomai-${datestring}
STAGING_REV_CVE=lts-${BASELINE}-xenomai-cve-${datestring}
echo "datestring=$datestring"
echo "STAGING_REV=$STAGING_REV"
echo "STAGING_REV_CVE=$STAGING_REV_CVE"

#get clean repos which used for build/compiling
rm -fr kernel-lts-staging
rm -fr kernel-lts-cve
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve     kernel-lts-cve

tags=""
#switch to 6.6 branch in cve repo, which used for CVE-tag generation
if [[ "$CREATE_CVE_STAGING_BRANCH" == "true" ]];then
  cd kernel-lts-cve
    git checkout 6.6

    #create tag for CVE content
    echo "tag_name is $STAGING_REV_CVE"
    git tag $STAGING_REV_CVE -m ""
    # gittag register: skip this tag
    git push origin $STAGING_REV_CVE
  cd -
fi

#create tag and cve-tag for compiling/build
cd kernel-lts-staging
  pwd

  if [[ $ABB == none ]] || [[ $ABB == "" ]];then
    echo "git checkout 6.6/dovetail-xenomai"
    git checkout 6.6/dovetail-xenomai
  else
    echo "git checkout $ABB"
    git checkout $ABB
  fi

  #create tag for compiling/build
  echo "tag_name is $STAGING_REV"
  git tag $STAGING_REV -m ""
  git push origin $STAGING_REV
  test $? -eq 0 && tags="${STAGING_REV}:1:1"

  #create cve-tag for compiling/build
  if [[ "$CREATE_CVE_STAGING_BRANCH" == "true" ]];then
    git quiltimport --series=../kernel-lts-cve/xenomai/patches/series --patches=../kernel-lts-cve/xenomai/patches/
    echo "cve tag_name is $STAGING_REV_CVE"
    git tag $STAGING_REV_CVE -m ""
    git push origin $STAGING_REV_CVE
    test $? -eq 0 && tags="$tags ${STAGING_REV_CVE}:3:1"
  fi

cd -

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
#generate prop file for downstream job, i.e., 6.6 xenomai build job and Banned words job
rm -f *.prop
echo "STAGING_REV=$STAGING_REV" > 6.6xeno.prop
echo "KERNEL=6.6lts" >> 6.6xeno.prop

echo "[Staging][${BASELINE}][XENOMAI]${datestring}" > subject.txt
echo "STAGING_REV=$STAGING_REV" > message.txt

if [[ "$CREATE_CVE_STAGING_BRANCH" == "true" ]];then
  echo "STAGING_REV=$STAGING_REV_CVE" > 6.6xeno_cve.prop
  echo "KERNEL=6.6lts" >> 6.6xeno_cve.prop
  echo "STAGING_REV_CVE=$STAGING_REV_CVE" >> message.txt
fi


