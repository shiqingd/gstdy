#!/bin/bash -ex
#this script is only for 5.15 android_u release job
#usage:
#    ./5.15android_u_release.sh 

if [[ $pre_prod == "true" ]];then
  PREPROD="pre-prod-"
else
  PREPROD=""
fi

# STAGING_REV, it is tag name, example, lts-v5.15.148-android_u-240416T032855Z
STAGING_REV=lts-${PREPROD}${BASELINE}-android_u-${STAGING_NUMBER}
STAGING_REV_CVE=lts-${PREPROD}${BASELINE}-android_u-cve-${STAGING_NUMBER}
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

  git checkout 5.15/android_u
  git push --dry-run kernel_lts      5.15/android_u
  git push --dry-run linux_intel_lts 5.15/android_u
  git push --dry-run kernel_lts      ${STAGING_REV}
  git push --dry-run linux_intel_lts ${STAGING_REV}

  git push kernel_lts      5.15/android_u
  git push linux_intel_lts 5.15/android_u
  git push kernel_lts      ${STAGING_REV}
  test $? -eq 0 && tags="${STAGING_REV}:1:2"
  git push linux_intel_lts ${STAGING_REV}
  test $? -eq 0 && tags="$tags ${STAGING_REV}:1:3"
cd -

#push CVE branches and tag
cd kernel-lts-cve

  git remote add linux_intel_lts https://github.com/intel/linux-intel-lts
  git checkout ${STAGING_REV}

  mkdir android_u_tmp;cp -r android_u/* android_u_tmp;rm -fr android_u;mv android_u_tmp android_u

  rm -fr android_t
  rm -fr linux
  rm -fr xenomai
  git rm -r android_t
  git rm -r linux
  git rm -r xenomai
  git add android_u
  git commit -m "CVE quilt release for ${STAGING_NUMBER}"

  git tag -a ${STAGING_REV_CVE} HEAD -m "release Kernel 5.15 android U Dessert for ${STAGING_REV_CVE}"

  git push --dry-run -f linux_intel_lts HEAD:5.15/android_u-cve
  git push --dry-run linux_intel_lts ${STAGING_REV_CVE}

  git push -f linux_intel_lts HEAD:5.15/android_u-cve

  git push linux_intel_lts ${STAGING_REV_CVE}
  test $? -eq 0 && tags="$tags ${STAGING_REV_CVE}:3:3"
cd -


cd kernel-config
  git push --delete origin $STAGING_REV
  git tag -d $STAGING_REV

  git checkout 5.15/config_u

  git tag $STAGING_REV -m ""
  git push origin $STAGING_REV

  git checkout -B 5.15/release/config_u
  git push --dry-run origin 5.15/release/config_u
  git push origin 5.15/release/config_u
cd -

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
#generate draft release email
rm -f Message_*.html
Message="Message_${STAGING_NUMBER}.html"
Subject="[Release][$BASELINE][LTS-2021][Android U]$STAGING_NUMBER"

cat message_5.15lts_android_u.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}

EMAIL_TO="nex.linux.kernel.integration@intel.com"
#EMAIL_TO="qingdong.shi@intel.com"

#sudo apt-get install sharutils for uuencode
#sudo apt-get install mailutils for mail
uuencode ${Message} ${Message} | mail -s "$Subject" $EMAIL_TO #send an email with attached draft release email

