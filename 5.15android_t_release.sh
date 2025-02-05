#!/bin/bash -ex
#this script is only for 5.15 android_t release job
#usage:
#    ./5.15android_t_release.sh 

# STAGING_REV, it is tag name, example, lts-v5.15.106-android_t-230717T032855Z
STAGING_REV=lts-${BASELINE}-android_t-${STAGING_NUMBER}
STAGING_REV_CVE=lts-${BASELINE}-android_t-cve-${STAGING_NUMBER}
echo "STAGING_REV=$STAGING_REV"
echo "STAGING_REV_CVE=$STAGING_REV_CVE"

#get clean repos
rm -fr kernel-lts-staging
rm -fr kernel-config
rm -fr kernel-lts-cve
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-config      kernel-config
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve     kernel-lts-cve

tags=""
#push branches and tag
cd kernel-lts-staging
  git remote add kernel_lts       https://github.com/intel-innersource/os.linux.kernel.kernel-lts
  git remote add linux_intel_lts  https://github.com/intel/linux-intel-lts

  git checkout 5.15/android_t
  git push --dry-run kernel_lts      5.15/android_t
  git push --dry-run linux_intel_lts 5.15/android_t
  git push --dry-run kernel_lts      ${STAGING_REV}
  git push --dry-run linux_intel_lts ${STAGING_REV}

  git push kernel_lts      5.15/android_t
  git push linux_intel_lts 5.15/android_t
  git push kernel_lts      ${STAGING_REV}
  test $? -eq 0 && tags="${STAGING_REV}:1:2"
  git push linux_intel_lts ${STAGING_REV}
  test $? -eq 0 && tags="$tags ${STAGING_REV}:1:3"
cd -

#push CVE branches and tag
cd kernel-lts-cve

  git remote add linux_intel_lts https://github.com/intel/linux-intel-lts
  git checkout ${STAGING_REV}

  rm -fr linux
  rm -fr xenomai
  rm -fr android_u
  git rm -r linux
  git rm -r xenomai
  git rm -r android_u
  git add android_t
  git commit -m "CVE quilt release for ${STAGING_NUMBER}"

  git tag -a ${STAGING_REV_CVE} HEAD -m "release Kernel 5.15 android T Dessert for ${STAGING_REV_CVE}"

  git push --dry-run -f linux_intel_lts HEAD:5.15/android_t-cve
  git push --dry-run linux_intel_lts ${STAGING_REV_CVE}

  git push -f linux_intel_lts HEAD:5.15/android_t-cve

  git push linux_intel_lts ${STAGING_REV_CVE}
  test $? -eq 0 && tags="$tags ${STAGING_REV_CVE}:3:3"
cd -


cd kernel-config
  git push --delete origin $STAGING_REV
  git tag -d $STAGING_REV

  git checkout 5.15/config_t

  git tag $STAGING_REV -m ""
  git push origin $STAGING_REV

  git checkout -B 5.15/release/config_t
  git push --dry-run origin 5.15/release/config_t
  git push origin 5.15/release/config_t
cd -

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
#generate draft release email
rm -f Message_*.html
Message="Message_${STAGING_NUMBER}.html"
Subject="[Release][$BASELINE][LTS-2021][Android T]$STAGING_NUMBER"

cat message_5.15lts_android_t.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}

EMAIL_TO="nex.linux.kernel.integration@intel.com"
#EMAIL_TO="qingdong.shi@intel.com"

#sudo apt-get install sharutils for uuencode
#sudo apt-get install mailutils for mail
uuencode ${Message} ${Message} | mail -s "$Subject" $EMAIL_TO #send an email with attached draft release email

