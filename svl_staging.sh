#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

exit_usage()
{
        cat <<EOF >&2
${0}: reconstitutes the dev-bkc kernel from all the coe-tracker sandboxed branches
USAGE:
	$0 [ -p ] [ -o ] [ -s ]

	p = push the branches to staging for backup (tracker by default)
	o = push the branches to bkc for testing
	s = use staging branches
	h|? = help (this screen)

EOF
exit 1
}

##########################################
#
# MAIN SCRIPT
#
##########################################

# Parse the commandline parameters
OPT_push=false
OPT_exit_only=false
while getopts "posbrh?" OPTION; do
	case $OPTION in
		p)
			OPT_push=true
			;;
		h|?)
			OPT_exit_only=true
			;;
	esac
done

$OPT_exit_only && exit_usage
test -n "$YOCTO_SANDBOX_BRANCH" || die "YOCTO_SANDBOX_BRANCH not defined"

yocto_sandbox_branch=$(echo $YOCTO_SANDBOX_BRANCH | sed -re 's/\s//' -e 's/^(tracker|origin)\///')

# Create a local copy of the kerne-bkc project, add the
# coe-tracker remote.
echo "Creating/Update working project"
declare repo=kernel-staging
declare repo_url=${KERNEL_REPOS[$repo]}
declare rmt=origin
declare repo_dir=$WORKSPACE/${repo_url##*/}
repo_dir=${repo_dir%\.git}
git_project $repo_url $repo_dir $yocto_sandbox_branch || \
	die "Unable to clone/update $repo"

#RT will be "-rt6", "-rt25" or empty, empty means non-RT
RT=$(echo "$YOCTO_SANDBOX_BRANCH" | sed -rn 's/.*(-rt[0-9]+).*/\1/p')

tags=""
pushd $repo_dir
    # Checkout the sandbox branch
    checkout $rmt/$yocto_sandbox_branch $yocto_sandbox_branch
    kernel_version=v$(make kernelversion)
    kernel_version=${kernel_version/\.0/}
    kernel_version="$kernel_version$RT"
    echo "kernelversion=$kernel_version"

    yocto_staging_tag=svl-pre-si-linux-${kernel_version}-${datetime}
    yocto_staging_branch=staging/svl-pre-si-linux-${kernel_version}-${datetime}

    tag $yocto_staging_tag "svl-pre-si linux kernel $kernel_version $datetime"

    # Push the sandbox branch to bkc remote as the staging branch
    if [ "$OPT_push" == "true" ] ; then
        push_remote $rmt $yocto_sandbox_branch $yocto_staging_branch
        echo -e "In repo $repo_url \nNew staging branch has been pushed: $yocto_staging_branch" > $WORKSPACE/message.txt
        push_tag $rmt $yocto_staging_tag
        test $? -eq 0 && tags="$tags ${yocto_staging_tag}:1:1"
        echo -e "New staging tag has been pushed: $yocto_staging_tag \n" >> $WORKSPACE/message.txt
    fi
popd

rm -f $WORKSPACE/*.prop
if [[ -z $RT ]]; then
cat <<EO_PROP >$WORKSPACE/new_branch.prop
YOCTO_STAGING_BRANCH=$yocto_staging_branch
STAGING_REV=$yocto_staging_tag
KERNEL_VERSION=$kernel_version
KSRC_UPSTREAM_TAG=$kernel_version
EO_PROP
else
cat <<EO_PROP >$WORKSPACE/new_branch_rt.prop
YOCTO_STAGING_BRANCH=$yocto_staging_branch
STAGING_REV=$yocto_staging_tag
KERNEL_VERSION=$kernel_version
KSRC_UPSTREAM_TAG=$kernel_version
EO_PROP
fi

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

echo -e "\033[0;32m*** Success ***\033[00m"
exit 0

