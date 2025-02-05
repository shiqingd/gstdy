#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

# started by pull. inturpulate branch names.
test -n "$YOCTO_STAGING_BRANCH" || die "No YOCTO_STAGING_BRANCH defined"


get_ww_string ${YOCTO_STAGING_BRANCH##*-} date_string release_string
cat <<EO_PROP >$WORKSPACE/yocto_build.prop
YOCTO_STAGING_BRANCH=$YOCTO_STAGING_BRANCH
STAGING_REV=$STAGING_REV
KERNEL_VERSION=$KERNEL_VERSION
EO_PROP

#JENKINS_URL_BASE="https://oak-jenkins.ostc.intel.com"
JENKINS_URL_BASE="https://cbjenkins-fm.devtools.intel.com/teams-iotgdevops00/job/NEX-Kernel"
JENKINS_USER="sys_oak"
JENKINS_TOKEN="$SYS_OAK_CRED_JENKINS_API"
CRUMB=$(
curl -k -s -u \
	${JENKINS_USER}:${JENKINS_TOKEN} \
	"$JENKINS_URL_BASE/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)")

jobs="iotg_next_yocto_staging"

# get the largest number and set all projects to one plus that number
declare -A B_NUM
for j in ${jobs}; do
	NUM=`curl -k -u ${JENKINS_USER}:${JENKINS_TOKEN} $JENKINS_URL_BASE/job/$j/lastBuild/api/json?pretty=true 2> \
		/dev/null | grep \"number\" | awk '{print $3}' | \
		sed -e 's/\([0-9]*\).*/\1/'`
	B_NUM[$j]=$((++NUM))
done

#for j in ${jobs}; do
#	curl -k -X POST -H $CRUMB -u ${JENKINS_USER}:${JENKINS_TOKEN} \
#		--data nextBuildNumber=$B_NUM \
#		$JENKINS_URL_BASE/job/$j/nextbuildnumber/submit
#done

echo "[Staging][${KERNEL_VERSION}][iotg-next] $release_string" > $WORKSPACE/subject.txt

email_msg="Hi All,

Staging.  Please test.

Please email your results to nex.linux.kernel.integration@intel.com;iotg.linux.kernel.testing@intel.com;iotg.linux.kernel@intel.com

Staging branch:
\t$YOCTO_STAGING_BRANCH

Staging tag:
\t$STAGING_REV

Kernel Version:
\t$KERNEL_VERSION

Images: (When done)
$(
for j in ${jobs}; do
	echo "\t$JENKINS_URL_BASE/job/$j/${B_NUM[$j]}"
done
)"

echo -e "$email_msg" > $WORKSPACE/message.txt


