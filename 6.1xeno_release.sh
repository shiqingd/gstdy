#!/bin/bash -ex

#this script is only for 6.1xenomai release
#usage:
#  ./6.1xeno_release.sh 6.1xeno v6.1.59 240103T021358Z PKT-10099

KERNEL=$1
BASELINE=$2
STAGING_NUMBER=$3
TRACKING_JIRA=$4

#get tag_name, i.e., STAGING_REV, STAGING_REV_CVE
STAGING_REV=lts-${BASELINE}-xenomai-${STAGING_NUMBER}
STAGING_REV_CVE=lts-${BASELINE}-xenomai-cve-${STAGING_NUMBER}

echo "KERNEL=$KERNEL"
echo "BASELINE=$BASELINE"
echo "STAGING_NUMBER=$STAGING_NUMBER"
echo "TRACKING_JIRA=$TRACKING_JIRA"
echo "STAGING_REV=$STAGING_REV"
echo "STAGING_REV_CVE=$STAGING_REV_CVE"

tags=""
#rm -rf kernel-dev-quilt
rm -rf kernel-lts-staging
#git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt kernel-dev-quilt
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging kernel-lts-staging

#cd kernel-dev-quilt
#  git checkout ${STAGING_REV}
#  git log --oneline -10
#  git push --dry-run origin HEAD:5.15/dovetail-xenomai
#  git push origin HEAD:5.15/dovetail-xenomai
#cd -

cd kernel-lts-staging
  git checkout 6.1/dovetail-xenomai
  git log --oneline -10

  #internal release(non-CVE)
  git tag -d ${STAGING_REV} || :
  git tag -s ${STAGING_REV} -m "" #GPG sign tag
  git remote add kernel_lts https://github.com/intel-innersource/os.linux.kernel.kernel-lts
  git push --dry-run kernel_lts 6.1/dovetail-xenomai
  git push --dry-run kernel_lts ${STAGING_REV}
  git push kernel_lts 6.1/dovetail-xenomai
  git push kernel_lts ${STAGING_REV}
  test $? -eq 0 && tags="${STAGING_REV}:1:2"

  #external release
  git remote add linux_intel_lts https://github.com/intel/linux-intel-lts
  git push --dry-run linux_intel_lts 6.1/dovetail-xenomai
  git push --dry-run linux_intel_lts ${STAGING_REV}
  git push linux_intel_lts 6.1/dovetail-xenomai
  git push linux_intel_lts ${STAGING_REV}
  test $? -eq 0 && tags="$tags ${STAGING_REV}:1:3"

cd -

#external CVE release
rm -rf kernel-lts-cve
rm -rf linux-intel-lts
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve kernel-lts-cve
git clone https://github.com/intel/linux-intel-lts

cd kernel-lts-cve
  git checkout ${STAGING_REV_CVE}
cd -

cd linux-intel-lts
  git checkout 6.1/dovetail-xenomai-cve
  rm -fr xenomai/patches/*
  mkdir -p xenomai/patches/
  cp -f ../kernel-lts-cve/xenomai/patches/* xenomai/patches/
  git add .
  git commit --allow-empty -m "Fix for CVE ${STAGING_NUMBER}"
  git tag -s ${STAGING_REV_CVE} -m ""
  git push --dry-run origin 6.1/dovetail-xenomai-cve
  git push --dry-run origin ${STAGING_REV_CVE}
  git push origin 6.1/dovetail-xenomai-cve
  git push origin ${STAGING_REV_CVE}
  test $? -eq 0 && tags="$tags ${STAGING_REV_CVE}:3:3"
cd -

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
#generate draft release email
rm -f Message_*.html
Message="Message_${STAGING_NUMBER}.html"
Subject="[Release][$BASELINE][LTS-2022-STABLE-XENOMAI]$STAGING_NUMBER"

cat message_6.1xeno.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}

EMAIL_TO="nex.linux.kernel.integration@intel.com"
#EMAIL_TO="qingdong.shi@intel.com"

#sudo apt-get install sharutils for uuencode
#sudo apt-get install mailutils for mail
uuencode ${Message} ${Message} | mail -s "$Subject" $EMAIL_TO #send an email with attached draft release email

