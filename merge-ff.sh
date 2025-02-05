#!/bin/bash -ex

CUR_DIR=$(pwd)

declare base_branch=$1
declare sandbox_branch=$2
declare push_opt=$3

Usage()
{
        echo "This jobs is to merge sandbox_branch to base_branch."
        echo "example: $0 base_branch sandbox_branch push_opt "
        exit 1
}

if [ -z $base_branch -o -z $sandbox_branch ]; then
	echo "base_branch and sandbox_branch are needed. "
	Usage
	exit 1
fi

if [ $base_branch == 6.12/linux -o $base_branch == 6.6/tiber/dev/linux -o $base_branch == 6.6/tiber/dev/preempt-rt -o $base_branch == 6.6/linux -o $base_branch == 6.6/preempt-rt -o $base_branch == 6.1/linux ]; then
        working_dir=kernel-lts-staging
        working_repo=https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git
elif [[ $base_branch == svl/pre-si/linux* ]] || [[ $base_branch == iotg-next* ]]; then
        working_dir=kernel-staging
        working_repo=https://github.com/intel-innersource/os.linux.kernel.kernel-staging.git
elif [[ $base_branch == mainline-tracking* ]]; then
        working_dir=mainline-tracking-staging
        working_repo=https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git
fi

echo "$sandbox_branch is going to be merged to $base_branch in $working_dir."

if [ ! -d $working_dir ]; then
        git clone $working_repo $working_dir
else
        echo "repo exists!"
fi

pushd $working_dir
git fetch origin --tags --force --prune

if [[ $(git branch | grep -w $base_branch) ]]; then
        git checkout $base_branch
        git pull
	git reset --hard origin/$base_branch
else
        git checkout -b $base_branch origin/$base_branch
fi

git log --oneline --decorate -10
git log --oneline --decorate -10 origin/$sandbox_branch

git merge --ff origin/$sandbox_branch

base_branch_head=$(git log --no-decorate --oneline -n1)
sandbox_branch_head=$(git log --no-decorate --oneline -n1 origin/$sandbox_branch)


if [[ $base_branch_head = $sandbox_branch_head	]]; then
	echo "Fast-Forward merged."
	if [ $push_opt = true ]; then
		echo "Merge is done, git push origin $base_branch."
		git push origin $base_branch
	else
		echo "Please push manually..."
	fi
fi

popd

