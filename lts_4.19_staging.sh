#!/bin/bash

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

exit_usage() {
        cat <<EOF >&2
${0}: reconstitutes the dev-bkc kernel from all the coe-tracker release branches
and will attempt to use the shared rr-cache
USAGE:
	$0 [ -p ] [ -o ] [ -r ] [-s ] soc [ -u ] prduct

	p = push the branches to staging for backup (tracker by default)
	o = push the branches to bkc for testing
        r = don't download/upload rr-cache
	s = soc to modify the configuration file with timestamp
	u = Product name for changing the configuration file with timestamp
	h|? = help (this screen)

EOF
exit 1
}

quiltify() {
	#get .patches from last base release branch(origin/4.19/base) to HEAD (origin/base)
	# and add suffix with timestamp
	git format-patch origin/4.19/release/base --suffix=.$datetime
	if [ ! -e *${datetime}* ]; then 
	echo 'base does not have patches to quiltify'
	return 0
	fi
	ls *${datetime}* > files
	rsync -av *${datetime}* $mydir/kernel-dev-quilt/patches
	cat files >> $mydir/kernel-dev-quilt/patches/series

	# commit all changes for future staging
	pushd $mydir/kernel-dev-quilt
		git add $mydir/kernel-dev-quilt/patches/series
		git add $mydir/kernel-dev-quilt/patches/*${datetime}*
		git commit -m "Staging quilt for: staging/4.19/lts/base-${datetime}"
	popd
}

##########################################
#
# MAIN SCRIPT
#
##########################################

# Parse the commandline parameters
OPT_push=false
OPT_origin=false
OPT_staging=false
OPT_exit_only=false
OPT_rr_cache=true
OPT_cve=false
socs=(gordon_peak gordon_peak_acrn clear_linux_bm clear_linux_laag clear_linux_sos)
alternative_base_branch=${ABB}
#alternative_android_branch=${AAB}
stable_base_branch_quilt=${SBBQ}
#debug purpose
#alternative_base_branch=none
#alternative_android_branch=none

while getopts "pos:rcu:h?" OPTION; do
	case $OPTION in
		p)
			OPT_push=true
			;;
		o)
			OPT_origin=true
			;;
		s)
			SOC=${OPTARG}
			;;
		r)
			OPT_rr_cache=false
			;;
		c)
			OPT_cve=true
			;;
		u)
			product="${OPTARG}"
			case "$product" in
				devbkc|4.9bkc|4.14bkc|mainlinetracking|4.19lts)
					:
					;;
				*)
					OPT_exit_only=true
					;;
			esac
			;;
		h|?)
			OPT_exit_only=true
			;;
	esac
done


# If ABB or AAB is filled in, then this is a sandbox branch. 
#if [[ -n $ABB || -n $AAB ]]
#then
	#if [[ $ABB != "none" || $AAB != "none" ]]
	if [[ $ABB != "none" ]]
	then
		SANDBOX_TAG="sandbox"
	fi
#fi

echo "SANDBOX_TAG=$SANDBOX_TAG" # to check SANDBOX_TAG is sandbox or empty

$OPT_exit_only && exit_usage



if $OPT_origin ; then
	push_scm="origin"
fi


#if [ "${alternative_base_branch}" != "none" ] && [ "${alternative_android_branch}" != "none" ] ; then
if [ "${alternative_base_branch}" != "none" ] ; then
	local_base=${alternative_base_branch}
	#local_android=${alternative_android_branch}
else
	local_base=4.19/base
	#local_android=4.19/android
fi
local_config=4.19/release/config
local_config_next=4.19/config
staging_branch_prefix=4.19/lts
local_base_quilt=4.19/base
remote_base=$local_base
#remote_android=$local_android
remote_config=$local_config
remote_config_next=$local_config_next

echo "STAGING_NUMBER=$STAGING_NUMBER" # print STAGING_NUMBER value

# Create a local copy of the kerne-lts-staging project
echo "Creating/Update working project"
init_kernel_lts_staging

upstream_tag=$UPSTREAM_KERNEL_VERSION

#for final staging, use the last staging STAGING_NUMBER to create the release tag, we don't create a new STAGING_NUMBER any more
#check STAGING_NUMBER is correct or not
if [[ -n $STAGING_NUMBER && $STAGING_NUMBER != "none" ]]; then
    datetime=$STAGING_NUMBER
    pushd kernel-lts-staging
        #git show -s --oneline sandbox-lts-${upstream_tag}-android-${datetime}
        #if [[ $? != 0 ]]; then
        #    echo "STAGING_NUMBER $STAGING_NUMBER is not correct, please check."
        #    echo "the tag doesn't exist in kernel-lts-staging repo, sandbox-lts-$upstream_tag-android-$datetime, please check."
        #    exit 1
        #else
        #    echo "find tag sandbox-lts-$upstream_tag-android-$datetime in kernel-lts-staging repo"
        #fi
		
        git show -s --oneline sandbox-lts-${upstream_tag}-base-${datetime}
        if [[ $? != 0 ]]; then
            echo "STAGING_NUMBER $STAGING_NUMBER is not correct, please check."
            echo "the tag doesn't exist in kernel-lts-staging repo, sandbox-lts-$upstream_tag-base-$datetime, please check."
            exit 1
        else
            echo "find tag sandbox-lts-$upstream_tag-base-$datetime in kernel-lts-staging repo"
        fi
    popd
fi

# Create local branches
pushd kernel-lts-staging
git branch -D $local_base || :
checkout origin/$remote_base $local_base
#checkout origin/$remote_android $local_android
popd

# Update configs
pushd kernel-config
git branch -D $local_config_next || :
checkout origin/$remote_config_next $local_config_next
popd

pushd kernel-lts-staging
#checkout_local $local_android
#tag_sandbox lts-$upstream_tag-android-$datetime $SANDBOX_TAG
#update_config_timestamp x86_64 $working_dir/kernel-config/bxt/android/non-embargoed/x86_64_defconfig

checkout_local $local_base
tag_sandbox lts-$upstream_tag-base-$datetime $SANDBOX_TAG

# CVE branches get tagged with both - one for the Coverity scans, and one to
# prevent releases.
if $OPT_cve; then
	tag_sandbox lts-$upstream_tag-base-$datetime ""
fi

#skip the creating and commiting new patches from last release to new patches in base to supply to quilt.
#when there is a alternative basebranch quilt A branch sanbox needs to be supplied to match the stable update quilt.
#creating patches from base branch if there are no stable update branch
if [[ ${stable_base_branch_quilt} == '' ]] ; then
	quiltify
fi

update_config_timestamp x86_64 $working_dir/kernel-config/bxt/clear/linux_guest/non-embargoed/x86_64_defconfig
update_config_timestamp x86_64 $working_dir/kernel-config/bxt/clear/service_os/non-embargoed/x86_64_defconfig
update_config_timestamp x86_64 $working_dir/kernel-config/bxt/clear/bare_metal/non-embargoed/x86_64_defconfig
popd

pushd kernel-config
commit_local "x86: config: update for kernel change $datetime"
tag_sandbox lts-$upstream_tag-base-$datetime $SANDBOX_TAG
if $OPT_cve; then
	tag_sandbox lts-$upstream_tag-base-$datetime ""
fi
popd

# Check if there is a difference from the previous staging
pushd kernel-config
previous_date=$(git branch -r | grep origin/staging/${staging_branch_prefix} | tail -1 | \
	sed -n 's/.*\([0-9]\{6\}T[0-9]\{6\}[A-Z]\).*/\1/p')
popd

if [ "$previous_date" != "" ] ; then
	[[ $- =~ e ]] ; errexit=$? # save error exit state restore later
	set +e
	pushd kernel-config
	git diff --exit-code $local_config_next origin/staging/${staging_branch_prefix}-${previous_date} &> /dev/null
	ret_config=$?
	popd
	if [ "${alternative_base_branch}" == "" ]; then
		pushd kernel-lts-staging
		git diff --exit-code $local_base origin/staging/$remote_base-$previous_date &> /dev/null
		ret_base=$?
		#git diff --exit-code $local_android origin/staging/$remote_android-$previous_date &> /dev/null
		#ret_android=$?
		popd
		(( $errexit )) && set +e
		if [ $ret_config -eq 0 ] && [ $ret_base -eq 0 ]; then
			echo -e "\033[0;32mNo difference from previous staging\033[00m"
			echo -e "No difference from previous staging" > $working_dir/message.txt
			#exit 0
		fi
	fi
fi

# Check if there is a difference from the release
pushd kernel-config
[[ $- =~ e ]] ; errexit=$? # save error exit state restore later
set +e
git diff --exit-code $local_config_next origin/$remote_config &> /dev/null
ret_config=$?
popd
if [ "${alternative_base_branch}" == "" ]; then
	pushd kernel-lts-staging
	git diff --exit-code $local_base origin/$remote_base &> /dev/null
	ret_base=$?
	#git diff --exit-code $local_android origin/$remote_android &> /dev/null
	#ret_android=$?
	(( $errexit )) && set +e
	popd
	if [ $ret_config -eq 0 ] && [ $ret_base -eq 0 ]; then
		echo -e "\033[0;32mNo difference from release\033[00m"
		echo -e "No difference from previous release" > $working_dir/message.txt
		#exit 0
	fi
fi

# Push the staging branches
if $OPT_push ; then
	if [ "$push_scm" == "origin" ] ; then
		pushd kernel-config
			push_remote $push_scm $local_config_next staging/${staging_branch_prefix}-$datetime
			push_tag_sandbox origin lts-$upstream_tag-base-$datetime $SANDBOX_TAG
			if $OPT_cve; then
				push_tag_sandbox origin lts-$upstream_tag-base-$datetime ""
			fi
		popd
	fi
	pushd kernel-lts-staging 
		#push_remote $push_scm $local_android staging/4.19/lts/android-$datetime
		push_remote $push_scm $local_base staging/4.19/lts/base-$datetime
		#push_tag_sandbox origin lts-$upstream_tag-android-$datetime $SANDBOX_TAG
		push_tag_sandbox origin lts-$upstream_tag-base-$datetime $SANDBOX_TAG
		if $OPT_cve; then
			#push_tag_sandbox origin lts-$upstream_tag-android-$datetime ""
			push_tag_sandbox origin lts-$upstream_tag-base-$datetime ""
		fi
		#if [ $SANDBOX_TAG == "sandbox" ];then
		#	STAGING_REV=sandbox-lts-${upstream_tag}-android-$datetime
		#else
		#	STAGING_REV=lts-${upstream_tag}-android-$datetime
		#fi
		# We're going to cascade the Jenkins job down with a PROP file.
		#echo -e "AAB=${AAB}\nABB=${ABB}\nPROP_BRANCH=staging/4.19/lts/android-$datetime\nSTAGING_REV=$STAGING_REV" > $mydir/ANDROID_BRANCH.prop
		echo -e "ABB=${ABB}\nBASE_BRANCH=staging/4.19/lts/base-$datetime" > $mydir/BASE_BRANCH.prop
		echo -e "BASE_BRANCH=staging/4.19/lts/base-$datetime\nUPSTREAM_KERNEL_VERSION=$UPSTREAM_KERNEL_VERSION" > $mydir/CVE.prop
	popd

	pushd kernel-dev-quilt
		if [[ ${stable_base_branch_quilt} != '' ]] ; then
			checkout origin/${stable_base_branch_quilt} staging_quilt
			push_remote $push_scm HEAD staging/4.19/lts/base-$datetime
		else
			push_remote $push_scm $local_base_quilt staging/4.19/lts/base-$datetime
		fi
		tag_sandbox lts-$upstream_tag-base-$datetime $SANDBOX_TAG
		push_tag_sandbox origin lts-$upstream_tag-base-$datetime $SANDBOX_TAG
		if $OPT_cve; then
			tag_sandbox lts-$upstream_tag-base-$datetime ""
			push_tag_sandbox origin lts-$upstream_tag-base-$datetime ""
		fi
	popd
	
	echo -e "New staging branch pushed" > $working_dir/message.txt
fi

echo -e "\033[0;32m*** Success ***\033[00m"
exit 0
