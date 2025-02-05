#!/bin/bash -ex

if [[ -z "$STAGING_REV" ]]; then
    echo "parameter STAGING_REV cannot be empty"
    exit 1
fi

# get staging number, for example, 241219T024423Z
STAGING_NUM=${STAGING_REV##*-}
kernel_version=${KERNEL_VERSION}

# downstream jobs list"
jobs="mainline_tracking_staging_osit_bxt_gp
IKT_overlay_kernel_debian_staging_build
IKT_overlay_kernel_rpm_staging_build"


JENKINS_URL_BASE="https://cje-fm-owrp-prod05.devtools.intel.com/nex-cisv-devops00/job/NEX-Kernel"
JENKINS_USER="sys_oak"
JENKINS_TOKEN="$SYS_OAK_CRED_JENKINS_API"

rm -f *.prop
echo STAGING_REV_YOCTO=$STAGING_REV > $WORKSPACE/yocto_build.prop
echo STAGING_REV=$STAGING_REV >> $WORKSPACE/yocto_build.prop
echo BRANCH=$STAGING_REV >> $WORKSPACE/yocto_build.prop # osit_staging.sh can use tags instead of branches


CRUMB=$(
curl -k -s -u \
	${JENKINS_USER}:${JENKINS_TOKEN} \
	"$JENKINS_URL_BASE/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)")


# get the largest number and set all projects to one plus that number
declare -A B_NUM
for j in ${jobs}; do
    NUM=`curl -k -u ${JENKINS_USER}:${JENKINS_TOKEN} $JENKINS_URL_BASE/job/$j/lastBuild/api/json?pretty=true 2> \
        /dev/null | grep \"number\" | awk '{print $3}' | \
        sed -e 's/\([0-9]*\).*/\1/'`
    B_NUM[$j]=$((++NUM))
done

echo KERNEL_VERSION=$kernel_version > $WORKSPACE/kernel_version.prop
cat $WORKSPACE/kernel_version.prop
if [[ $kernel_version == *rt* ]];then
    mv -f $WORKSPACE/kernel_version.prop  $WORKSPACE/kernel_version_rt.prop
fi

echo "[Staging][$kernel_version][mainline-tracking] $STAGING_NUM" > $WORKSPACE/subject.txt

msg="Hi All,

Staging.  Please test.

Please email your results to nex.linux.kernel.integration@intel.com; iotg.linux.kernel.testing@intel.com; nex.sw.linux.kernel@intel.com

Images: (When done)
$(
for j in ${jobs}; do
    echo "\t$JENKINS_URL_BASE/job/$j/${B_NUM[$j]}"
done
)
\thttps://cbjenkins-fm.devtools.intel.com/teams-iotgdevops00/job/NEX-Validation/job/Banned_Words_Scan/
\thttps://cbjenkins-fm.devtools.intel.com/teams-iotgdevops00/job/NEX-Validation/job/lts_build_osit_ubuntu/

Staging tags:
\t$STAGING_REV
"

echo -e "$msg" > $WORKSPACE/message.txt

