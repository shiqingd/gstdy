#!/bin/bash -ex

# Author: qingdong.shi@intel.com

# This script can generate draft release emails base on templates
# Who will receive emails, please modify EMAIL_TO in this script

# If your machine has no mail command, please install it firstly.
# 1)sudo apt-get install sharutils ---> for uuencode
# 2)sudo apt-get install mailutils ---> for mail

# usage/steps:
# 1)mkdir <test_dir> ;
# 2)put this script in <test_dir>, chmod +x <script> ;
# 3)put email_template message_5.15rt.html and message_5.15lts.html in the directory;
# 4)run it (see Usage), for example, ./<script> v5.15.2 201225T065818Z PKT-4909

Usage()
{
    echo "Three mandatory paramaters: BASELINE and staging_number and tracking_jira"
    echo "usage: $0 { BASELINE } { STAGING_NUMBER } { TRACKING_JIRA }"
    echo "example for lts: $0 v6.1.8 231225T065818Z PKT-4909 "
    echo "example for rt : $0 v6.1.23-rt21 230506T021352Z PKT-4910 "
}

#Main/main program
if [ $# != 3 ];then
    echo "must has three paramaters, they are mandatory."
    Usage
    exit 1
fi

#BASELINE="v6.1.8"
#STAGING_NUMBER="230220T053739Z"
BASELINE=$1
STAGING_NUMBER=$2
TRACKING_JIRA=$3

# To check staging_number's format is correct or not
echo $STAGING_NUMBER | grep '[0-9]\{6\}T[0-9]\{6\}Z'
if [ $? != 0 ];then
    echo "You input a wrong staging_number, please check"
    Usage
    exit 1
fi

rm -f Message_*.html
Message="Message_${STAGING_NUMBER}.html"

if [[ "${BASELINE}" == *rt* ]];then
    if [ ! -f message_6.1rt.html ];then
        echo "RT release email template message_6.1rt.html does not exist, please check"
        exit 1
    fi

    Subject="[Release][$BASELINE][LTS-2022-STABLE-RT] $STAGING_NUMBER"

    cat message_6.1rt.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}

else
    if [ ! -f message_6.1lts.html ];then
        echo "LTS release email template message_6.1lts.html does not exist, please check"
        exit 1
    fi

    Subject="[Release][$BASELINE][LTS-2022] $STAGING_NUMBER"
    cat message_6.1lts.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}
fi


EMAIL_TO="nex.linux.kernel.integration@intel.com"
#EMAIL_TO="qingdong.shi@intel.com"

#sudo apt-get install sharutils for uuencode
#sudo apt-get install mailutils for mail
uuencode ${Message} ${Message} | mail -s "$Subject" $EMAIL_TO #send an email with attached draft release email

