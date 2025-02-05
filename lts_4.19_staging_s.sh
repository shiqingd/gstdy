#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

exit_usage() {
        cat <<EOF >&2
${0}: reconstitutes the dev-bkc kernel from all the coe-tracker release branches
and will attempt to use the shared rr-cache
USAGE:
	$0 [ -a ] [ -p ] [ -o ] [ -s || -e || -b ] [ -r ]

	a = automatic merge resolution
	p = push the branches to staging for backup (tracker by default)
	o = push the branches to bkc for testing
	s = use staging branches
	e = use embargoed branches (currently for ${embargoed_base})
	b = specify staging branch to replace with release branch,
	    [ this options expects an enviornment variable SPECIFIC_STAGING to be set,
	      the staging branch should be in the below format
	      Format:-   domain_name:branch
	      eg:- audio:tracker/dev/staging/audio
	      Specify multiple branches using ',' as the separator
	      eg:- audio:tracker/dev/staging/audio,camera:tracker/dev/staging/camera
	    ]
	r = don't download/upload rr-cache

	h|? = help (this screen)

EOF
exit 1
}

quiltify() {
	#get .patches from last release  to HEAD (origin/last rc)
	# and add suffix with timestamp
	TAG=$1
	pushd $mydir/kernel-lts-staging
		git format-patch origin/4.19/release/android_s --suffix=.$datetime
		if [ ! -e *${datetime}* ]; then 
		echo 'base does not have patches to quiltify'
		popd
		return 0
		fi
		ls *${datetime}* > files
		rsync -av *${datetime}* $mydir/kernel-dev-quilt/patches
		cat files >> $mydir/kernel-dev-quilt/patches/series
		# commit all changes for future staging
		pushd $mydir/kernel-dev-quilt
		git add patches/series
		git add patches/*${datetime}*
		git commit -m "Staging quilt for:  $TAG"
		popd
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
OPT_cve=false
push_scm="origin"

alternative_android_s_branch=${AAB}
alternative_quilt_branch=${AQB}

if [[ $AAB != "none" ]] && [[ ${AQB} == "none" ]]
then
	echo "Error: No Quilt branch provided for your sandbox branch !"
	return;
fi

while getopts "psch?" OPTION; do
	case $OPTION in
		p)
			OPT_push=true
			;;
		s)
			OPT_staging=true
			;;
		c)
			OPT_cve=true
			;;
		h|?)
			OPT_exit_only=true
			;;
	esac
done

#if AAB does not equal to none then continue with sandbox
if [[ $AAB != "none" ]]; then
	SANDBOX_TAG="sandbox"
fi

$OPT_exit_only && exit_usage


if $OPT_staging; then

	if [ "${alternative_android_s_branch}" == "none" ] ; then
		local_android=4.19/android_s
	else
		local_android=${alternative_android_s_branch}
	fi
	#naming for Tag in all repo's

	local_config=4.19/release/config_s
    local_config_next=4.19/config_s
	alternative_lts_quilt=${alternative_quilt_branch}
    local_lts_quilt=4.19/android_s


	remote_android=$local_android
	remote_config=$local_config
	remote_config_next=$local_config_next
fi
rm -f $WORKSPACE/message.txt
rm -f $WORKSPACE/subject.txt

# Create a local copy of the kerne-lts-staging project

echo "Creating/Update working project pass the quilt branch"
init_kernel_lts_staging

# Create local branches
pushd kernel-lts-staging
  checkout origin/$remote_android $local_android
  upstream_tag=v`make kernelversion`
  echo "upstream_tag is $upstream_tag"

  #for final staging, use the last staging STAGING_NUMBER to create the release tag, we don't create a new STAGING_NUMBER any more
  #check STAGING_NUMBER is correct or not
  if [[ $STAGING_NUMBER != "none" ]]; then
    datetime=$STAGING_NUMBER
    git show -s --oneline sandbox-lts-${upstream_tag}-android_s-${datetime}
    if [[ $? != 0 ]]; then
        echo "STAGING_NUMBER $STAGING_NUMBER is not correct, please check."
        echo "the tag doesn't exist in kernel-lts-staging repo, sandbox-lts-${upstream_tag}-android_s-${datetime}, please check."
        exit 1
    else
        echo "find tag sandbox-lts-${upstream_tag}-android_s-${datetime} in kernel-lts-staging repo"
    fi
  fi
popd


get_ww_string $datetime date_string release_string

if [ "$SANDBOX_TAG" == "sandbox" ] ; then
	tag_label_prop=$SANDBOX_TAG-lts-$upstream_tag-android_s-$datetime
	tag_label_cve_prop=$SANDBOX_TAG-lts-$upstream_tag-android_s-cve-$datetime
else
	tag_label_prop=lts-$upstream_tag-android_s-$datetime
	tag_label_cve_prop=lts-$upstream_tag-android_s-cve-$datetime
fi
tag_label=lts-$upstream_tag-android_s-$datetime
tag_label_cve=lts-$upstream_tag-android_s-cve-$datetime

# Update configs for checking for difference from previous and release branches
pushd kernel-config
  checkout origin/$remote_config_next $local_config_next
popd

pushd kernel-lts-staging
  checkout origin/$local_android $local_android
  tag_sandbox $tag_label $SANDBOX_TAG
  update_config_timestamp x86_64 $working_dir/kernel-config/bxt/android/non-embargoed/x86_64_defconfig android_s
popd


#1. go to 4.19/android_s
#2. get get diff patches from last rc to HEAD in 4.19/android_s (quiltify)
#3. add patches to kernel-dev-quilt
#4. commit it
#5. Tag it
pushd kernel-dev-quilt
  if [ "${alternative_quilt_branch}" == "none" ] ; then
	  checkout origin/$local_lts_quilt $local_lts_quilt
	  quiltify $tag_label
  else
	  checkout origin/$alternative_lts_quilt $alternative_lts_quilt
  fi

  tag_sandbox $tag_label $SANDBOX_TAG
popd


pushd kernel-lts-cve
  tag_sandbox $tag_label_cve $SANDBOX_TAG
popd

pushd kernel-config
  commit_local "x86: config: update for kernel change $datetime"
  tag_sandbox $tag_label $SANDBOX_TAG
popd

pushd kernel-config
  checkout origin/$remote_config_next $local_config_next
popd

pushd kernel-lts-staging
	ln -s $mydir/kernel-lts-cve/android_s/patches .
	git quiltimport
	tag_sandbox $tag_label_cve $SANDBOX_TAG
	update_config_timestamp x86_64 $working_dir/kernel-config/bxt/android/non-embargoed/x86_64_defconfig android_s
popd

pushd kernel-config
  commit_local "x86: config: update for kernel change $datetime CVE"
  tag_sandbox $tag_label_cve $SANDBOX_TAG
popd

tags=""
# Push the staging branches
if $OPT_push ; then
	if [ "$push_scm" == "origin" ] ; then
		pushd kernel-config
			push_tag_sandbox origin $tag_label $SANDBOX_TAG
			push_tag_sandbox origin $tag_label_cve $SANDBOX_TAG
		popd
	fi
	pushd kernel-lts-staging 
		push_tag_sandbox origin $tag_label $SANDBOX_TAG
		test $? -eq 0 && tags="${tag_label_prop}:1:1"
		push_tag_sandbox origin $tag_label_cve $SANDBOX_TAG
		test $? -eq 0 && tags="$tags ${tag_label_cve_prop}:3:1"
		# We're going to cascade the Jenkins job down with a PROP file.
        cat <<EO_ANDR >$mydir/ANDROID_BRANCH.prop
AAB=${AAB}
ABB=${ABB}
BRANCH=$tag_label_prop
ANDROID_TAG=$tag_label_prop
KERNEL_VERSION=$upstream_tag
revision=$tag_label_prop
STAGING_REV=$tag_label_prop
EO_ANDR
        cat <<EO_CVE >$mydir/CVE.prop
BRANCH=$tag_label_cve_prop
ANDROID_TAG=$tag_label_cve_prop
KERNEL_VERSION=$upstream_tag
STAGING_REV=$tag_label_cve_prop
revision=$tag_label_cve_prop
EO_CVE
	popd

	pushd kernel-dev-quilt
		push_tag_sandbox origin $tag_label $SANDBOX_TAG
		test $? -eq 0 && tags="$tags ${tag_label_prop}:2:1"
	popd

	pushd kernel-lts-cve
		push_tag_sandbox origin $tag_label_cve $SANDBOX_TAG
	popd

	
	echo -e "New staging branch pushed" > $working_dir/message.txt
fi

subject_msg="[Staging][Android-S][$upstream_tag][LTS] $release_string"

if [[ -n $SANDBOX_TAG ]]
then
    subject_msg="[SANDBOX]$subject_msg"
fi

echo $subject_msg > $WORKSPACE/subject.txt

JENKINS_URL_BASE="https://oak-jenkins.ostc.intel.com"

jobs="4.19-bkc-banned-words-scan
4.19-bkc-staging-android_s-build-test
4.19-bkc-staging-gordon_peak_s-baseline
4.19-bkc-staging-gordon_peak_s"

declare -A B_NUM

for j in ${jobs}; do
    NUM=`curl -k $JENKINS_URL_BASE/job/$j/lastBuild/api/json?pretty=true 2> \
        /dev/null | grep \"number\" | awk '{print $3}' | \
        sed -e 's/\([0-9]*\).*/\1/'`
    #echo $NUM
    B_NUM[$j]=$((++NUM))
done

email_msg="Hi All,

Staging.  Please test.

Please email your results to nex.linux.kernel.integration@intel.com; iotg.linux.kernel.testing@intel.com; iotg.linux.kernel@intel.com

Staging Tags:
\t$tag_label_prop
\t$tag_label_cve_prop


Images: (When done)
$(
for j in ${jobs}; do
    echo "\t$JENKINS_URL_BASE/job/$j/${B_NUM[$j]}"

    if [[ "$j" == "4.19-bkc-banned-words-scan" || "$j" == "4.19-bkc-staging-gordon_peak_s" ]];then
        let B_NUM[$j]=${B_NUM[$j]}+1
        echo "\t$JENKINS_URL_BASE/job/$j/${B_NUM[$j]}"
    fi

done
)"

if [[ -n $SANDBOX_TAG ]]
then
    email_msg=${email_msg/Staging/Sandbox staging}
fi

echo -e "$email_msg" > $WORKSPACE/message.txt

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

echo -e "\033[0;32m*** Success ***\033[00m"

exit 0
