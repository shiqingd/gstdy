#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

##########################################
#
# MAIN SCRIPT
#
##########################################

# Parse the commandline parameters
OPT_push=false
OPT_origin=false
OPT_staging=false
OPT_cve=false
OPT_exit_only=false
while getopts "posbrh?" OPTION; do
    case $OPTION in
        p)
            OPT_push=true
            ;;
        o)
            OPT_origin=true
            ;;
        s)
            OPT_staging=true
            ;;
        h|?)
            OPT_exit_only=true
            ;;
    esac
done

#RT will be "-rt6", "-rt25" or empty, empty means non-RT
RT=$(echo "$YOCTO_STAGING_BRANCH" | sed -rn 's/.*(-rt[0-9]+).*/\1/p')

if [[ $pre_prod == "true" ]]; then
  PREPROD="pre-prod-"
else
  PREPROD=""
fi


# Create a local copy of the mainline-tracking-staging project
echo "Creating/Update working project"
rm -fr mainline-tracking-staging
rm -fr kernel-dev-quilt
rm -fr kernel-lts-cve
git clone https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging mainline-tracking-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt          kernel-dev-quilt
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve            kernel-lts-cve


pushd mainline-tracking-staging
    # reset to YOCTO_STAGING_BRANCH, then, can get upstream_tag by 'make kernelversion'
    git checkout $YOCTO_STAGING_BRANCH

    # get upstream_tag, it will be v6.7-rc3, or v5.17-rc3-rt6, or v6.5-rt5, or v6.5
    upstream_tag=v$(make kernelversion)
    upstream_tag=$(echo $upstream_tag | sed -e "s/\.0//")
    upstream_tag="$upstream_tag$RT"
    echo "upstream_tag=$upstream_tag"
popd

if [[ $upstream_tag == v6.11 ]]; then
    cve_branch=6.11
    PREPROD=""
elif [[ $upstream_tag == v6.12 ]]; then
    cve_branch=6.12
else
    cve_branch=none
fi

if [[ $DATE_TIME == "none" ]]; then
    OPT_cve=false
    date_time=$datetime
else
    OPT_cve=true
    date_time=$DATE_TIME
fi

tags=""
# Push the staging tags
if [[ -z $RT ]]; then

    if [[ $OPT_cve == "true" ]];then
        pushd kernel-lts-cve
            git checkout $cve_branch
        popd
    fi

    # push the new tags to mainline-tracking-staging with a timestamp format
    pushd mainline-tracking-staging
        if [[ $OPT_cve == "false" ]]; then
            git checkout $YOCTO_STAGING_BRANCH
            tagnm="mainline-tracking-${PREPROD}${upstream_tag}-linux-$date_time"
            tag_sandbox $tagnm ''
            push_tag_sandbox origin $tagnm ''
            test $? -eq 0 && tags="$tags $tagnm:1:1"
        else
            checkout origin/$YOCTO_STAGING_BRANCH ${YOCTO_STAGING_BRANCH}_cve
            git quiltimport --patches $working_dir/kernel-lts-cve/linux/patches --series $working_dir/kernel-lts-cve/linux/patches/series
            tagnm="mainline-tracking-${PREPROD}${upstream_tag}-linux-cve-${date_time}"
            tag_sandbox $tagnm ''
            push_tag_sandbox origin $tagnm ''
            test $? -eq 0 && tags="$tags $tagnm:3:1"
        fi

    popd

    # checkout supplied quilt branch from repository kernel-dev-quilt
    pushd kernel-dev-quilt
        if [[ $OPT_cve == "false" ]]; then
            git checkout $BASE_STAGING_BRACH_QUILT
            tagnm="mainline-tracking-${PREPROD}${upstream_tag}-linux-$date_time"
            tag_sandbox $tagnm ''
            push_tag_sandbox origin $tagnm ''
            test $? -eq 0 && tags="$tags $tagnm:2:1"
        elif [[ $OPT_cve == "true" ]]; then
            cp -f $working_dir/kernel-lts-cve/linux/patches/*.* ./patches/
            cat $working_dir/kernel-lts-cve/linux/patches/series >> ./patches/series
            git add .
            git commit -m "Add CVE patches"
            tagnm="mainline-tracking-${PREPROD}${upstream_tag}-linux-cve-${date_time}"
            tag_sandbox $tagnm ''
            push_tag_sandbox origin $tagnm ''
        fi

    popd

    if [[ $OPT_cve == "true" ]];then
        pushd kernel-lts-cve
            git checkout $cve_branch
            tagnm="mainline-tracking-${PREPROD}${upstream_tag}-linux-cve-${date_time}"
            tag_sandbox $tagnm ''
            push_tag_sandbox origin $tagnm ''
            test $? -eq 0 && tags="$tags $tagnm:3:2"
        popd
    fi
else
    #for RT

    pushd mainline-tracking-staging
        git checkout $YOCTO_STAGING_BRANCH
        tagnm="mainline-tracking-${PREPROD}${upstream_tag}-preempt-rt-$date_time"
        tag_sandbox $tagnm ''
        push_tag_sandbox origin $tagnm ''
        test $? -eq 0 && tags="$tags $tagnm:1:1"
    popd

    pushd kernel-dev-quilt
        git checkout $BASE_STAGING_BRACH_QUILT
        tagnm="mainline-tracking-${PREPROD}${upstream_tag}-preempt-rt-$date_time"
        tag_sandbox $tagnm ''
        push_tag_sandbox origin $tagnm ''
        test $? -eq 0 && tags="$tags $tagnm:2:1"
    popd

fi

echo -e "New staging branch pushed" > $working_dir/message.txt

echo "BASE_BRANCH=mainline-tracking-$date_time" > $WORKSPACE/new_branch_test.prop

echo "STAGING_REV_YOCTO=${tagnm}" >> $WORKSPACE/new_branch_test.prop
echo "STAGING_REV=${tagnm}" >> $WORKSPACE/new_branch_test.prop
echo "KERNEL_VERSION=${upstream_tag}" >> $WORKSPACE/new_branch_test.prop

if [[ -z $RT ]]; then
    if [[ $OPT_cve == "false" ]];then
        echo "KSRC_UPSTREAM_TAG=${upstream_tag}" > $WORKSPACE/overlay_ubuntu.prop
        echo "KERNEL_QUILT_TAG=mainline-tracking-${PREPROD}${upstream_tag}-linux-$date_time" >> $WORKSPACE/overlay_ubuntu.prop
        echo "KERNEL_CONFIG_TAG=mainline-tracking/config">>$WORKSPACE/overlay_ubuntu.prop
        echo "OVERLAY_TARGET_BRANCH=mainline-tracking/${upstream_tag}-ubuntu">>$WORKSPACE/overlay_ubuntu.prop
        echo "OVERLAY_TEMPLATE_TAG=mainline-tracking-ubuntu">>$WORKSPACE/overlay_ubuntu.prop
        echo "UPLOAD_DEB_PACKAGE=true">>$WORKSPACE/overlay_ubuntu.prop
        echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME">>$WORKSPACE/overlay_ubuntu.prop

        echo "KSRC_UPSTREAM_TAG=${upstream_tag}" > $WORKSPACE/overlay_centos.prop
        echo "KERNEL_QUILT_TAG=mainline-tracking-${PREPROD}${upstream_tag}-linux-$date_time" >> $WORKSPACE/overlay_centos.prop
        echo "KERNEL_CONFIG_TAG=mainline-tracking/config">>$WORKSPACE/overlay_centos.prop
        echo "OVERLAY_TEMPLATE_TAG=lts2022-centos">>$WORKSPACE/overlay_centos.prop
        echo "OVERLAY_TARGET_BRANCH=mainline-tracking/${upstream_tag}-centos">>$WORKSPACE/overlay_centos.prop
        echo "OVERLAY_NAME=mainline-tracking">>$WORKSPACE/overlay_centos.prop
        echo "UPLOAD_RPM_PACKAGE=true">>$WORKSPACE/overlay_centos.prop
        rm -fr $WORKSPACE/overlay_ubuntu_cve.prop #in case this file exists , then un-necessary job will be triggered

    elif [[ $OPT_cve == "true" ]];then
        echo "KSRC_UPSTREAM_TAG=${upstream_tag}" > $WORKSPACE/overlay_ubuntu_cve.prop
        echo "KERNEL_QUILT_TAG=mainline-tracking-${PREPROD}${upstream_tag}-linux-cve-$date_time" >> $WORKSPACE/overlay_ubuntu_cve.prop
        echo "KERNEL_CONFIG_TAG=mainline-tracking/config">>$WORKSPACE/overlay_ubuntu_cve.prop
        echo "OVERLAY_TARGET_BRANCH=mainline-tracking/${upstream_tag}-ubuntu-cve">>$WORKSPACE/overlay_ubuntu_cve.prop
        echo "OVERLAY_TEMPLATE_TAG=mainline-tracking-ubuntu">>$WORKSPACE/overlay_ubuntu_cve.prop
        echo "UPLOAD_DEB_PACKAGE=true">>$WORKSPACE/overlay_ubuntu_cve.prop
        echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME">>$WORKSPACE/overlay_ubuntu_cve.prop
    fi
else
    echo "KSRC_UPSTREAM_TAG=${upstream_tag}" > $WORKSPACE/overlay_ubuntu.prop
    echo "KERNEL_QUILT_TAG=mainline-tracking-${PREPROD}${upstream_tag}-preempt-rt-$date_time" >> $WORKSPACE/overlay_ubuntu.prop
    echo "KERNEL_CONFIG_TAG=mainline-tracking/config">>$WORKSPACE/overlay_ubuntu.prop
    echo "OVERLAY_TARGET_BRANCH=mainline-tracking-rt/${upstream_tag}-ubuntu">>$WORKSPACE/overlay_ubuntu.prop
    echo "OVERLAY_TEMPLATE_TAG=mainline-tracking-rt-ubuntu">>$WORKSPACE/overlay_ubuntu.prop
    echo "UPLOAD_DEB_PACKAGE=true">>$WORKSPACE/overlay_ubuntu.prop
    echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME">>$WORKSPACE/overlay_ubuntu.prop
fi

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

echo -e "\033[0;32m*** Success ***\033[00m"
exit 0

