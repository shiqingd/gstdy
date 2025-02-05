#!/bin/bash -ex
CUR_DIR=$(pwd)

declare base_branch=$1
declare sandbox_branch=$2
declare push_opt=$3

Usage()
{
        echo "This jobs is to rebase sandbox_branch against base_branch."
        echo "example: $0 base_branch sandbox_branch push_opt "
        exit 1
}

if [ -z $base_branch -o -z $sandbox_branch ]; then
	echo "base_branch and sandbox_branch are needed. "
	Usage
	exit 1
fi

if [ $base_branch == 5.10/yocto -o $base_branch == 5.4/yocto -o $base_branch == 5.15/linux -o $base_branch == 5.15/ehl/mr3/linux -o $base_branch == 5.15/ehl/mr3/preempt-rt -o $base_branch == 5.4/preempt-rt -o $base_branch == 5.15/preempt-rt -o $base_branch == 5.10/preempt-rt -o $base_branch == 5.15/kmb/mr3/linux -o $base_branch == 5.15/thb/mr3/linux ]; then
	working_dir=kernel-lts-staging
	working_repo=https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git
elif [[ $base_branch == bullpen/v5.10 ]] || [[ $base_branch == bullpen/v5.15 ]] || [[ $base_branch == iotg-next/* ]]; then
	working_dir=kernel-staging
	working_repo=https://github.com/intel-innersource/os.linux.kernel.kernel-staging.git
elif [[ $base_branch == mainline-tracking/v5* ]]; then
        working_dir=mainline-tracking-staging
        working_repo=https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git
fi

if [ ! -d $working_dir ]; then
	git clone $working_repo $working_dir
else
	echo "repo exists!"
fi

pushd $working_dir
git fetch origin --tags --force --prune

if [ $(git branch | grep -w $sandbox_branch) ]; then
        git checkout $sandbox_branch
        git pull
else
        git checkout $sandbox_branch
fi

git log --oneline --decorate -10  origin/$base_branch
git log --oneline --decorate -10
head_origin=$(echo $(git log --no-decorate --oneline -n1)  | awk -F' ' '{print $2,$3,$4,$NF} ' )

git rebase origin/$base_branch
if [ $? = 0 ]; then
	head_rebase=$(echo $(git log --no-decorate --oneline -n1) | awk -F' ' '{print $2,$3,$4,$NF} ' )
	if [ "$head_origin" = "$head_rebase" ]; then
		echo "Sandbox branch is rebased."
		if [ "$push_opt" = true ]; then
			echo "Rebase is done, git push -f origin $sandbox_branch."
			git push -f origin $sandbox_branch
		else
			echo "Please push manually..."
		fi
	else
		echo "Rebase failed, pls check..."
	fi
fi

popd

