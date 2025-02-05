#!/bin/bash

#
# Merge the domain branches that have new patches into the release branches
# for LTS releases. This code also maintains a rebasing shadow for each
# of the release branches. Conflicts are resolved first in the shadow
# branches, and the results are used to resolve any merge conflicts in
# the non-rebasing branches.
#

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions
source $mydir/lts_common.sh # Include library of common lts build functions

## show_usage
#
show_usage() {
cat <<End-Of-Usage

USAGE:
lts_staging.sh -l <LTS_VERSION> [ -i ] [ -m ] [ -c ] [ -p ] [ TIMESTAMP ]
lts_staging.sh -h

DESCRIPTION:
Search the LTS domain branches, incorporate any new patches,
and stage a new LTS release.

REQUIRED PARAMETERS:
-l Specify the LTS branch you are operating on: 4.9 or 4.14

OPTIONAL PARAMETERS:

The optional TIMESTAMP parameter can be used to specify identify a
prior staging branch on which the new release should be staged. This 
means that you can speculatively begin a new release on top of a
staging release that is still in flight (unreleased).

-h Show this usage message and exit

The -i, -m, and -c options are all turned on by default, and the -p
option is turned off by default. If, however, you specify one or more
of these options, then any of these options that are not specified
will be turned off. This makes it possible to pick and choose which
major portions of the script you want to run.

-i Initialize the work space
-m Merge the domain branches
-c Perform a compile test release branch candidates
-p Push the release candidates to staging branches

End-Of-Usage
}


## die_usage
#
die_usage() {
	show_usage >&2
	exit 1
}


## os_merge_domain
#
# Merge branches that are unique to a particular OS (e.g. android
# or yocto)
#
os_merge_domain() {
	declare os=$1
	declare lts_version=$2
	declare branches=$3
	declare count=0
	declare commits

	for domain in $branches; do
		echo "Checking $domain"

		version=$(base_version origin/${domain} \
			$stable_kernel $kernel_version)
		if [ -z "$version" ]; then
			warn "Skipping $domain - wrong base kernel version"
			continue
		fi

		# Cherry-pick the patches to rebasing-base
		commits=$(check_merged $lts_version/${os} \
			origin/${domain})
		[ -n "$commits" ] || continue
		echo "Processing $domain"
		cherry_pick rebasing/$lts_version/${os} \
			rebasing/$lts_version/${os} $commits

		# Merge the OS branch and check
		merge_branch $lts_version/${os} $domain tracker/$domain \
			$commits
		git_diff $lts_version/${os} rebasing/$lts_version/${os}
		if [ -z "$branches_merged" ]; then
			branches_merged=$domain
		else
			branches_merged="$branches_merged $domain"
		fi
	done
}


##########################################
#
# MAIN SCRIPT
#
##########################################

# Parse the commandline parameters
while getopts ":chil:mp" OPTION; do
	case $OPTION in
		c)
			do_compile=yes
			;;
		h)
			show_usage
			exit 0
			;;
		i)
			do_init=yes
			;;
		l)
			lts_version=$OPTARG
			;;
		m)
			do_merge=yes
			;;
		p)
			do_push=yes
			;;
		?)
			warn
			warn "Invalid Option: -$OPTARG"
			die_usage
			;;
	esac
done
shift $((OPTIND-1))

if [ -z "$do_init" ] && [ -z "$do_compile" ] && \
   [ -z "$do_merge" ] && [ -z "$do_push" ]; then
	do_compile=yes; do_init=yes; do_merge=yes
fi

# Verify that $lts_version is valid.
validate_lts_version $lts_version

# Allow the user to stage off of a previous staging branch
if [ $# -eq 1 ]; then
	set_reference_release $1
elif [ $# -ne 0 ]; then
	die "Usage: lts_staging.sh -l LTS_VERSION [STAGING_TIMESTAMP]"
fi

if [ -n "$do_init" ]; then # Initialize the working directory
	# See if a staging branch has been specified to override the
	# Create a local copy of the kernel-lts-staging project,
	# and check-out local working instances
	# of the LTS branches.
	echo "Create/Update working project"
	init_kernel_lts_staging origin

	pushd $working_dir/kernel-config

	if [ "$lts_version" == "4.9" ]; then
		checkout origin/4.9/config 4.9/config
	fi
	if [ "$lts_version" == "4.14" ]; then
		checkout origin/4.14/config 4.14/config
	fi


	# Managing the config can be a bit tricky when building on top of
	# another staging build. origin/${lts_version}/lts-next needs to contain the
	# intended config, but it also must be a descendent of the staging
	# build that it is built from. Since we fix-up the configs
	# automatically before pushing a config staging branch, this is
	# a check to make sure that we don't forget to update ${lts_version}/lts-next
	# appropriately.
#	if ! git merge-base --is-ancestor ${lts_version}/lts-next $ref_config; then
#		die "${lts_version}/lts-next must be based on $ref_config!"
#	fi

	if [ "$lts_version" == "4.9" ]; then
		if ! git merge-base --is-ancestor 4.9/config $ref_config; then
			die "4.9/config must be based on $ref_config!"
		fi
	fi
	if [ "$lts_version" == "4.14" ]; then
		if ! git merge-base --is-ancestor 4.14/config $ref_config; then
			die "4.14/config must be based on $ref_config!"
		fi
	fi



	popd

	pushd $working_dir/kernel-lts-staging

	checkout $rebasing_base rebasing/$lts_version/base
	checkout $rebasing_yocto rebasing/$lts_version/yocto
	#checkout $rebasing_yocto_rt rebasing/$lts_version/yocto-rt
	if [ "$lts_version" == "4.9" ]; then
		checkout $rebasing_android rebasing/$lts_version/android
	fi
	
	if [ "$lts_version" == "4.9" ]; then
		checkout origin/4.9/base 4.9/base
		checkout origin/4.9/yocto 4.9/yocto
		checkout origin/4.9/android 4.9/android
	fi

	if [ "$lts_version" == "4.14" ]; then
		checkout origin/4.14/base 4.14/base
		checkout origin/4.14/yocto 4.14/yocto
	fi
	popd
fi # $do_init

# Verify that the rebasing and non-rebasing branches match BEFORE
# processing the domain branches.
pushd $working_dir/kernel-lts-staging
assert_kernel_consistency $lts_version
popd

if [ -n "$do_merge" ]; then # Merge new changes
	pushd $working_dir/kernel-lts-staging
	# Capture the base kernel version
	kernel_version=$(git merge-base $stable_kernel $base_kernel)
	if [ -z "$kernel_version" ]; then
		die "Unable to determine base kernel version for $base_kernel";
	fi
	# echo "Base kernel version for $base_kernel is $kernel_version"

	# Capture the SHA for the original tip of each of the
	# rebasing branches. These will be used to determine
	# the cherry-pick ranges when recreating the rebasing
	# branches
	base_tip=`sha_of_tip rebasing/$lts_version/base`
	yocto_tip=`sha_of_tip rebasing/$lts_version/yocto`
	#yocto_rt_tip=`sha_of_tip rebasing/$lts_version/yocto-rt`
	if [ "$lts_version" == "4.9" ]; then
		android_tip=`sha_of_tip rebasing/$lts_version/android`
	fi
	branches_merged=

	for domain in $domain_branches; do
		echo "Checking $domain"

		version=$(base_version origin/${domain} \
			$stable_kernel $kernel_version)
		if [ -z "$version" ]; then
			warn "Skipping $domain - wrong base kernel version"
			continue
		fi

		# Cherry-pick the patches to rebasing-base
		commits=$(check_merged ${base} origin/${domain})
		[ -n "$commits" ] || continue
		echo "Processing $domain"
		cherry_pick rebasing/$lts_version/base \
			rebasing/$lts_version/base $commits

		# Merge the base branch and check
		merge_branch $lts_version/base $domain tracker/$domain $commits
		git_diff $lts_version/base rebasing/$lts_version/base
		if [ -z "$branches_merged" ]; then
			branches_merged=$domain
		else
			branches_merged="$branches_merged $domain"
		fi
	done

	if [ -n "$branches_merged" ]; then
		# Rebuild each of the remaining rebasing branches on top of
		# the already rebased base branch.
		cherry_pick rebasing/$lts_version/base \
			rebasing/$lts_version/yocto \
			"${base_tip}..${yocto_tip}"
#		cherry_pick rebasing/$lts_version/yocto \
#			rebasing/$lts_version/yocto-rt \
#			"${yocto_tip}..${yocto_rt_tip}"
		cherry_pick rebasing/$lts_version/base \
			rebasing/$lts_version/android \
			"${base_tip}..${android_tip}"

		echo "Merge domains: $branches_merged"
		for domain in $branches_merged; do
			# Merge the remaining branches - we'll check them later
			commits=$(check_merged ${base} origin/${domain})
			merge_branch $lts_version/yocto $domain \
				tracker/$domain $commits
#			merge_branch $lts_version/yocto-rt $domain \
#				tracker/$domain $commits
			merge_branch $lts_version/android $domain \
				tracker/$domain $commits
		done

		# Check the merged branches against the rebasing branches.
		git_diff $lts_version/yocto rebasing/$lts_version/yocto
#		git_diff $lts_version/yocto-rt rebasing/$lts_version/yocto-rt
		git_diff $lts_version/android rebasing/$lts_version/android
	fi

	os_merge_domain base $lts_version "$base_branches"
	os_merge_domain yocto $lts_version "$yocto_branches"
#	os_merge_domain yocto-rt $lts_version "$yocto_branches"
	os_merge_domain android $lts_version "$android_branches"
	popd

	if [ -z "$branches_merged" ]; then
		echo "No domain branches to merge!"
		exit 0
	fi
	echo "Local copies of release branch are at: $working_dir"
fi # $do_merge

# Test that the candidate source compiles
[ -n "$do_compile" ] && test_lts_compile $working_dir $lts_version

# Push the staging branches.
[ -n "$do_push" ] && push_staging_branches $working_dir $lts_version

exit 0
