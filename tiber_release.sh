#!/bin/bash -ex

echo "tiber_release job is running"

#internal release
rm -fr os.linux.kernel.kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging
cd os.linux.kernel.kernel-lts-staging
	tag=''
    git remote add kernel_lts https://github.com/intel-innersource/os.linux.kernel.kernel-lts
    git reset --hard "${STAGING_REV}"
    if [[ $STAGING_REV == *rt* ]];then
        git push --dry-run kernel_lts HEAD:6.6/tiber/dev/preempt-rt
    else
        git push --dry-run kernel_lts HEAD:6.6/tiber/dev/linux
    fi
    git push --dry-run kernel_lts "${STAGING_REV}"
    
    if [[ $STAGING_REV == *rt* ]];then
        git push kernel_lts HEAD:6.6/tiber/dev/preempt-rt
    else
        git push kernel_lts HEAD:6.6/tiber/dev/linux
    fi
    git push kernel_lts "${STAGING_REV}"

    test $? -eq 0 && tags="${STAGING_REV}:1:2"
cd -

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

#push cve tag
cd os.linux.kernel.kernel-lts-staging
    datetime=${STAGING_REV##*-}
    git tag | grep $datetime | grep cve
    if [[ $? == 0 ]];then
        STAGING_REV_CVE=$(git tag | grep $datetime | grep cve)
        git push --dry-run kernel_lts "${STAGING_REV_CVE}"
        git push kernel_lts "${STAGING_REV_CVE}"
    fi
cd -

