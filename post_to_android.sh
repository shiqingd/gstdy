#!/bin/bash -x

declare mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions


#
# Functions
#

# get kernel by release tag
# get_kernel_bytag <tag> <var_kernel>
get_kernel_bytag() {
    for k in ${!RELTAG_PATTERNS[@]}; do
        # use glob pattern matting
        if [[ "$1" == ${RELTAG_PATTERNS[$k]}* ]]; then
            eval "$2=\"${k}\""
            break
        fi
    done
}


#
# Main
#
if [ -z "$ANDROID_TAG" ]; then
    echo "ERROR: ANDROID_TAG is not defined"
    exit 1
fi
declare kernel=""
get_kernel_bytag $ANDROID_TAG kernel
if [ -z "$kernel" ]; then
    echo "ERROR: invalid release tag: $ANDROID_TAG"
    exit 1
fi

# comment out this part as quiltdiff job has been obsoleted
#declare try_cnt=3
#declare is_passed=false
## check if the change list for the release is available
#chglst_url=${QUILTDIFF_CHGLST_BASE_URL}$ANDROID_TAG
#curl -s $chglst_url 2>/dev/null | grep -q 'changes'
#if [ $? -ne 0 ]; then
#    for ((i=1; i<=$try_cnt; i++)); do
#        # try to trigger the job again to generate change list
#        curl -s ${TRIGGER_QUILTDIFF_BASE_URL}$ANDROID_TAG 2>/dev/null | \
#          grep -qi 'SUCCESS'
#        if [ $? -eq 0 ]; then
#            is_passed=true
#            break
#        fi
#        sleep 300
#    done
#    if [ "$is_passed" == "false" ]; then
#        echo "ERROR: change list is not available: $chglst_url"
#        exit 2
#    fi
#fi

declare job_params="buildWithParameters?token=${ANDROID_TOKEN_PARAMS[$kernel]}&TAG_NAME=$ANDROID_TAG"
# pn: parameter name
# pv: parameter value
declare pv=""
for pn in ${CIB_JOB_PARAMS[$kernel]}; do
    eval "pv=\$${pn}"
    if [ -n "$pv" ]; then
        job_params="${job_params}&${pn}=${pv}"
    fi
done
job_params=${job_params//,/%2C}
# trigger CI bridge jenkins job
curl --fail -k -X POST -u ${CIB_JENKINS_USER}:${SYS_OAK_CRED_ANDR_JENKINS_API} \
  "${CIB_JENKINS_BASE_URL}/${CIB_JOBS[$kernel]}/${job_params}"
