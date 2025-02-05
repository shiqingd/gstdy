#!/usr/bin/env /bin/bash

# Main arguments:
# PROJECT :   Github project in intel-innersource (e.g. os.linux.kernel.kernel-lts-staging)
# PULL_REQUEST_NUMBER : pull request number in project to scan
# ARCH -   Architecture the PR applies to (x86-64 or arm64)
#	FIXME - PRs that include some files intended for the other architecture only product errors
#	FIXME - workaround is under investigation

for arg in WORKSPACE PROJECT PULL_REQUEST_NUMBER SYS_OAK_CRED_GITHUB_API SYS_OAK_CRED_AD ARCH
do
	if [ -z "${!arg}" ]
	then
		echo ERROR:  Missing parameter or environment variable ${arg}
		fail=1
	else
		echo $arg=${!arg}
	fi
done
if [ -n "${fail}" ]
then
    exit 1
fi

## Set up workspace directories

# If run from a Jenkins Job, make sure EXECUTOR_NUMBER is set
# Else, set up work trees in a separate console space
if [ -z "${EXECUTOR_NUMBER}" ]
then
    if [ -z "${JENKINS_URL}" ]
    then
        REPO_HOME=${WORKSPACE}
    else
        REPO_HOME=${WORKSPACE}/executor/${EXECUTOR_NUMBER}
    fi
else
    REPO_HOME=${WORKSPACE}/executor/${EXECUTOR_NUMBER}
fi

REPO_HOME+=/intel-innersource

if [ ! -d ${REPO_HOME} ]
then
    mkdir -p ${REPO_HOME}
fi


TOOLS_HOME=${REPO_HOME}/os.linux.kernel.devops.ikit-dev-ops

if [ ! -d ${TOOLS_HOME} ]
then
	pushd ${REPO_HOME}
		git clone https://github.com/intel-innersource/os.linux.kernel.devops.ikit-dev-ops
	popd
else
	pushd ${TOOLS_HOME}
		git fetch --all --tags --force
	popd
fi

# Verify that Coverity Utiltiies are installed
if ! which cov-build
then
	echo "Coverity utilities not found on this machine"
	echo "Check PATH environment variable,"
	echo "or install Coverity Desktop Utilities release 2021.12.2"
	exit 1
fi

set -ex

# Get source ref of Pull request
PR_BRANCH=`curl --no-progress-meter -H "Authorization: token ${SYS_OAK_CRED_GITHUB_API}" -H 'Accept: application/vnd.github.v3-preview+json' https://api.github.com/repos/intel-innersource/${PROJECT}/pulls/${PULL_REQUEST_NUMBER} | jq .head.ref | sed -e 's/"//g'`

# Get Target Branch of Pull request
PR_TARGET=`curl --no-progress-meter -H "Authorization: token ${SYS_OAK_CRED_GITHUB_API}" -H 'Accept: application/vnd.github.v3-preview+json' https://api.github.com/repos/intel-innersource/${PROJECT}/pulls/${PULL_REQUEST_NUMBER} | jq .base.ref | sed -e 's/"//g'`

# Get the Coverity Project name to find baseline scan
COV_PROJECT=${PROJECT/os.linux.kernel./}
COV_PROJECT_KEY=`curl --no-progress-meter --user "sys_oak:${SYS_OAK_CRED_AD}" -H "Accept: application/json" https://coverity002.sc.devtools.intel.com:8443/api/v2/projects?namePattern=${COV_PROJECT}  | jq .projects[].projectKey`

# Get the Coverity Stream name where baseline scan should be found
COV_STREAM_NAME=`echo ${PR_TARGET}_${ARCH} | sed -e 's/\//_/g'`
COV_STREAM_KEY=`curl --no-progress-meter --user "sys_oak:${SYS_OAK_CRED_AD}"  -H "Accept: application/json" https://coverity002.sc.devtools.intel.com:8443/api/v2/streams?namePattern=${COV_STREAM_NAME} | jq .streams[].name`

# Baseline full scans should be done each time a domain update is done on ${PR_TARGET}
# If the correct stream for this PR is not found, stop here 
if [ -z "${COV_STREAM_KEY}" ] 
then
	echo ERROR: No stream ${COV_STREAM_NAME} exists on Coverity Server
	echo Please perform a full scan on branch ${PR_TARGET} using arch ${ARCH} and commit to stream ${COV_STREAM_NAME}
	exit 1
fi

# Set up source and destination paths
BUILD_DIR=./build
COV_HOST=coverity002.sc.devtools.intel.com
COV_PORT=8590
OUTPUT_BASENAME=${WORKSPACE}/cov_desktop_scan_`date +"%y%m%d%H%M%S"`
rm -rf ${WORKSPACE}/cov_desktop_scan_ci_*.json
rm -rf ${WORKSPACE}/cov_desktop_scan_ci_*.txt
JSON_OUTPUT=${OUTPUT_BASENAME}.json
TEXT_OUTPUT=${OUTPUT_BASENAME}.txt
MERGE_CONFIGS=/tmp/mergeconfig

# Set up source code work tree if needed
WORKTREE=${REPO_HOME}/${PROJECT}
if [ ! -d ${WORKTREE} ]
then
	pushd ${REPO_HOME}
		git clone https://github.com/intel-innersource/${PROJECT}
	popd
else
	pushd ${WORKTREE}
	git fetch --all --tags --force
	popd
fi

# Define architecture-specific compilers
GCC_x86_64=gcc
GCC_arm64=aarch-linux-gnu-gcc

GET_PR_CONFIGS=${TOOLS_HOME}/lib/config_finder.py

# Set up build parameters needed by each architecture
if [ "${ARCH}" = "arm64" ]
then
	ARCH_CONFIG="defconfig"
	XCOMPILE_ARG='CROSS_COMPILE=aarch64-linux-gnu-'
elif [ "${ARCH}" = "x86_64" ]
then
	ARCH_CONFIG="x86_64_defconfig"
	XCOMPILE_ARG=''
else
	echo ERROR:  invalid architectre name ARCH=${ARCH}
	exit 1
fi

pushd ${WORKTREE}
	# Reduce warnings on 'git checkout'
	git config --global advice.detachedHead false
	git checkout ${PR_BRANCH}
	rm -rf ${BUILD_DIR}
	IDIR=${BUILD_DIR}/cov_idir
	mkdir -p ${IDIR}
	COV_CONFIG_DIR=${BUILD_DIR}/cov_config
	mkdir -p ${COV_CONFIG_DIR}
	CONFIG=${COV_CONFIG_DIR}/coverity_config.xml
	GCCVAR=GCC_${ARCH}
	# Configure Coverity to use the correct compiler to produce translation units
	cov-configure --config ${CONFIG} --compiler ${!GCCVAR} --comptype gcc --template 
	# Start with a default config
	make O=${BUILD_DIR} ARCH=${ARCH} ${ARCH_CONFIG}
	FILES_CHANGED=`git diff origin/${PR_TARGET}..origin/${PR_BRANCH} --name-only | egrep "\.c$"`
	# Try to figure out what config parameters are needed for these changed files
	cp /dev/null ${MERGE_CONFIGS}		# Zero out the file
	sed -i '/^\tmodules$/d' init/Kconfig	# Workaround for bug in Python kconfiglib package
	PR_CONFIGS=`${GET_PR_CONFIGS} -a ${ARCH} ${FILES_CHANGED} 2>/dev/null`
	for cfg in $PR_CONFIGS
	do
		# Add CONFIG_* param to set to merge
		echo CONFIG_$cfg=y >> ${MERGE_CONFIGS}
	done
	echo CONFIG_RETPOLINE=n >> ${MERGE_CONFIGS}
#	cat ${MERGE_CONFIGS}
	git checkout -- init/Kconfig	# Restore from kconfiglib bug
	# Merge derived configs into the default config
	./scripts/kconfig/merge_config.sh -O ${BUILD_DIR} ${BUILD_DIR}/.config ${MERGE_CONFIGS}
	# Specify "yes" in case needed menuconfig configs are not set
	yes "" | cov-build --dir ${IDIR} --config ${CONFIG} --record-with-source --parallel-translate=`nproc` make O=${BUILD_DIR} -j`nproc` ARCH=${ARCH} ${XCOMPILE_ARG} 
	cov-run-desktop --dir ${IDIR} --host ${COV_HOST} --port ${COV_PORT} --stream ${COV_STREAM_NAME} --disable-parse-warnings --ignore-uncapturable-inputs true --strip-path ${WORKTREE}/ --text-output ${TEXT_OUTPUT} --text-output-style oneline --json-output-v7 ${JSON_OUTPUT} ${FILES_CHANGED}
popd

