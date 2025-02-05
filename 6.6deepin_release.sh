#!/bin/bash -ex

#this script is only for 6.6 Deepin release
#usage:
# ./6.6deepin_release.sh v6.6.11 240117T110945Z PKT-10968

BASELINE=$1
STAGING_NUMBER=$2
TRACKING_JIRA=$3

#get tag_name, i.e., STAGING_REV
STAGING_REV=lts-${BASELINE}-deepin-dev-${STAGING_NUMBER}

echo "BASELINE=$BASELINE"
echo "STAGING_NUMBER=$STAGING_NUMBER"
echo "TRACKING_JIRA=$TRACKING_JIRA"
echo "STAGING_REV=$STAGING_REV"

tags=""
rm -rf kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging kernel-lts-staging

cd kernel-lts-staging
    #git checkout 6.6/deepin/dev/linux
    git checkout $STAGING_REV
    git log --oneline -10

    #internal release(non-CVE)
    git remote add kernel_lts https://github.com/intel-innersource/os.linux.kernel.kernel-lts
    git push --dry-run kernel_lts HEAD:refs/heads/6.6/deepin/dev/linux
    git push --dry-run kernel_lts ${STAGING_REV}

    if [[ "$DRY_RUN" == False ]];then
        git push kernel_lts HEAD:refs/heads/6.6/deepin/dev/linux
        git push kernel_lts ${STAGING_REV}
    fi

    test $? -eq 0 && tags="${STAGING_REV}:1:2"

    #external release, currently, no external release

cd -

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

#generate draft release email
rm -f Message_*.html
Message="Message_${STAGING_NUMBER}.html"
Subject="[Release][$BASELINE][LTS-2023-Deepin]$STAGING_NUMBER"

cat message_6.6deepin.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}

EMAIL_TO="nex.linux.kernel.integration@intel.com"
#EMAIL_TO="qingdong.shi@intel.com"

#sudo apt-get install sharutils for uuencode
#sudo apt-get install mailutils for mail
uuencode ${Message} ${Message} | mail -s "$Subject" $EMAIL_TO #send an email with attached draft release email

