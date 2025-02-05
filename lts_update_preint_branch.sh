#!/bin/bash -ex

if [ -z $STAGING_REV ] ; then
    echo "error: parameters are not set !!!"
    exit 1
fi

baseline=$(echo $STAGING_REV | sed -E 's/.*v([0-9]+\.[0-9]+(-rt[0-9]+)?).*/v\1/')
datetime=${STAGING_REV##*-}

if [[ $STAGING_REV == *mainline-tracking* ]]; then
  kernel_repo=os.linux.kernel.mainline-tracking-staging
else
  kernel_repo=os.linux.kernel.kernel-lts-staging
fi
echo $baseline
echo $datetime
echo $kernel_repo

if [[ ${#datetime} == 14 ]] && [[ $datetime =~ [0-9]{6}T[0-9]{6}Z ]] ; then
    echo "datetime format is correct."
else
    echo "error: $datetime datetime is not correct!!!"
    exit 1
fi

if [[ $STAGING_REV == *preempt-rt* ]]; then

    #for 6.12rt
    if [[ $STAGING_REV == *lts*v6.12* ]]; then
        PREINT_branch=sandbox/IKT/v6.12/PREINT/preempt-rt

    #for 6.6rt
    elif [[ $STAGING_REV == *lts*v6.6* ]]; then
        PREINT_branch=sandbox/IKT/v6.6/PREINT/preempt-rt

    #for 6.1rt
    elif [[ $STAGING_REV == *lts*v6.1* ]]; then
        PREINT_branch=sandbox/IKT/v6.1/PREINT/preempt-rt

    #for mainline-tracking-rt
    elif [[ $STAGING_REV == *mainline-tracking* ]]; then
        PREINT_branch=sandbox/IKT/${baseline}/PREINT/preempt-rt
    else
        echo "Please check STAGING_REV $STAGING_REV, maybe wrong"
        exit 1
    fi

#for 6.12lts
elif [[ $STAGING_REV == *lts*v6.12*linux* ]]; then
    PREINT_branch=sandbox/IKT/v6.12/PREINT/linux

#for 6.6lts
elif [[ $STAGING_REV == *lts*v6.6*linux* ]]; then
    PREINT_branch=sandbox/IKT/v6.6/PREINT/linux

#for 6.1lts
elif [[ $STAGING_REV == *lts*v6.1*linux* ]]; then
    PREINT_branch=sandbox/IKT/v6.1/PREINT/linux

#for maineline-tracking
elif [[ $STAGING_REV == *mainline-tracking* ]]; then
    PREINT_branch=sandbox/IKT/${baseline}/PREINT/linux

else
    echo "Input STAGING_REV $STAGING_REV is invalid"
    exit 1
fi

echo "LTS/RT preint branch is $PREINT_branch" > PREINT_branch.txt

# Update LTS/RT preint branch
rm -fr $WORKSPACE/${kernel_repo}
git clone https://github.com/intel-innersource/${kernel_repo} ${kernel_repo}
pushd $WORKSPACE/${kernel_repo}
    git checkout $STAGING_REV
    git push origin HEAD:$PREINT_branch
    #git push --dry-run origin HEAD:$PREINT_branch
popd


