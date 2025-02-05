#!/bin/bash -x

# Author: qingdong.shi@intel.com

#this script can generate release email template
#who will receive emails, please modify EMAIL_TO in this script

#if your machine has no mail command, please install it firstly.
#sudo apt-get install mailutils
#usage/steps: 1)mkdir <test_dir> ; 2)put this script in <test_dir>, chmod +x <script> ; 
#             3)put email_template message.html in the directory; 4)example, run ./<script> v5.17-rc3 220224T034010Z PKT-6301 


Usage()
{
    echo "Three mandatory paramaters: BASELINE and staging_number and tracking_jira"
    echo "usage: $0 { BASELINE } { STAGING_NUMBER } { TRACKING_JIRA }"
    echo "example: $0 v5.17-rc3 220224T034010Z PKT-6301"
    echo "example: $0 v5.17-rc3-rt6 220217T100001Z PKT-6293"
}

#Main/main program
if [ $# != 3 ];then
    echo "must has three paramaters, they are mandatory."
    Usage
    exit 1
fi

BASELINE=$1
STAGING_NUMBER=$2
TRACKING_JIRA=$3

#to check staging_number's format is correct
echo $STAGING_NUMBER | grep '[0-9]\{6\}T[0-9]\{6\}Z'
if [ $? != 0 ];then
    echo "You input a wrong staging_number, please check"
    Usage
    exit 1
fi

rm -f Message_*.html
Message="Message_${STAGING_NUMBER}.html"

if [[ "${BASELINE}" == *rt* ]];then
    if [ ! -f message_mainline_tracking_rt.html ];then
        echo "email_template message_mainline_tracking_rt.html doesn't exist, please check"
        exit 1
    fi

    Subject="[Release][$BASELINE][Mainline Tracking RT] $STAGING_NUMBER"

    cat message_mainline_tracking_rt.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}
else
    if [ ! -f message_mainline_tracking.html ];then
        echo "email_template message_mainline_tracking.html doesn't exist, please check"
        exit 1
    fi

    Subject="[Release][$BASELINE][Mainline Tracking] $STAGING_NUMBER"
    cat message_mainline_tracking.html  | sed "s/\$BASELINE/$BASELINE/g" | sed "s/\$STAGING_NUMBER/$STAGING_NUMBER/g" | sed "s/\$TRACKING_JIRA/$TRACKING_JIRA/g" > ${Message}
fi


EMAIL_TO="nex.linux.kernel.integration@intel.com"
#EMAIL_TO="qingdong.shi@intel.com"

#sudo apt-get install sharutils for uuencode
#sudo apt-get install mailutils for mail
uuencode ${Message} ${Message} | mail -s "$Subject" $EMAIL_TO

