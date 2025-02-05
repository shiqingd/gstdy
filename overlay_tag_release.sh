#!/bin/bash -ex

#declare KERNEL=$1
#declare KERNEL_TAG=$2
source bkc_common.sh

Usage()
{
    echo "This jobs is to release overlay tags."
    echo "example: $0 KERNEL KERNEL_TAG"
    echo "KERNEL: 6.6 | 6.6rt | mainline-tracking | iotg-next | svl"
    echo "KERNEL_TAG format: lts-v6.6.50-linux-240925T091328Z|lts-v6.6.50-rt42-preempt-rt-240925T173613Z"
    echo "KERNEL_TAG format: mainline-tracking-v5.15-rc6-yocto-211020T103635Z"
    echo "KERNEL_TAG format: iotg-next-v5.15-rc6-yocto-211020T104209Z"
    echo "KERNEL_TAG format: svl-pre-si-linux-v6.11-241126T040643Z"
    exit 1
}

tags=""
function release_overlay_tag()
{
    echo "================================================"
    echo "Current OVERLAY BRANCH is $1, OVERLAY TAG is $2."
    echo "To release OVERLAY_TAG:$2 to OVERLAY_BRANCH:$1"
    git tag -d $2 || :

    git checkout $1 || die "Unable to checkout $1"
    git tag $2 -m ""

    # push to intel-innersource/os.linux.kernel.iot-kernel-overlay-staging
    git push origin $2
    test $? -eq 0 && tags="$tags ${2}:4:1"

    echo "RD: git push origin $2"

    # push to intel-innersource/os.linux.kernel.iot-kernel-overlay
    git push RL $2
    test $? -eq 0 && tags="$tags ${2}:4:2"
    echo "RD: git push RL $2"
    git push RL HEAD:refs/heads/$1
    echo "RD: git push RL HEAD:refs/heads/$1"

    # delete tag locally, re-create it with singingkey and push tag to github external release repo
    git tag -d $2 || :
    git tag --sign $2 -m ""

    # external release, push to github.com/intel/linux-kernel-overlay
    if [[ $1 =~ 'iotg-next' || $2 =~ 'iotg-next' || $1 =~ 'svl' || $2 =~ 'svl' ]]; then
        echo "No need to release to Github repo."
    else
        git push GH $2
        test $? -eq 0 && tags="$tags ${2}:4:3"
        echo "RD: git push GH $2"
        git push GH HEAD:refs/heads/$1
        echo "RD: git push GH HEAD:refs/heads/$1"
    fi

    git log -n 1 --oneline --decorate

    echo "================================================"
}

#Main

if [ -z $KERNEL -o -z $KERNEL_TAG  ]; then
    echo "=====Failed! Two parameters are needed: KERNEL and KERNEL release tag.====="
    Usage
fi

if [[ $KERNEL_TAG =~ [0-9]{6}T[0-9]{6}Z$ ]];then
    echo "KERNEL_TAG=$KERNEL_TAG"
else
    echo "Pls check KERNEL_TAG format."
    Usage
fi


declare overlay_staging_repo="https://github.com/intel-innersource/os.linux.kernel.iot-kernel-overlay-staging.git"
declare overlay_release_repo="https://github.com/intel-innersource/os.linux.kernel.iot-kernel-overlay.git"
declare overlay_release_github_repo='https://github.com/intel/linux-kernel-overlay.git'

rm -rf iot-kernel-overlay-staging
echo "Clone the kernel overlay staging repo..."
git clone $overlay_staging_repo iot-kernel-overlay-staging

pushd iot-kernel-overlay-staging
    git remote add RL $overlay_release_repo || die "Unable to add remote repo."
    git remote add GH $overlay_release_github_repo || die "Unable to add remote repo."


    #lts-v6.1.8-linux-230201T082419Z
    if [[ "$KERNEL" == "6.1lts" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/lts-/lts-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/linux-/ubuntu-}
        #OVERLAY_TAG_ubuntu_cve=${OVERLAY_TAG/linux-/ubuntu-cve-}
        #OVERLAY_TAG_centos=${OVERLAY_TAG/linux-/centos-}

        OVERLAY_BRANCH_ubuntu="lts2022-ubuntu"
        #OVERLAY_BRANCH_ubuntu_cve="lts2022-ubuntu-cve"
        #OVERLAY_BRANCH_centos="lts2022-centos"

        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        #release_overlay_tag $OVERLAY_BRANCH_ubuntu_cve $OVERLAY_TAG_ubuntu_cve
        #release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "6.1lts OVERLAY TAGS are applied successfully! "

    #lts-v6.1.12-rt7-preempt-rt-230307T020547Z
    #lts-overlay-v6.1.12-rt7-preempt-rt-ubuntu-230307T020547Z
    elif [[ "$KERNEL" == "6.1rt" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/lts-/lts-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/preempt-rt-/preempt-rt-ubuntu-}
        #OVERLAY_TAG_centos=${OVERLAY_TAG/preempt-rt-/preempt-rt-centos-}

        OVERLAY_BRANCH_ubuntu="lts2022-rt-ubuntu"
        #OVERLAY_BRANCH_centos="lts2021-rt-centos"

        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        #release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "6.1rt OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "6.6lts" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/lts-/lts-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/linux-/ubuntu-}
        OVERLAY_BRANCH_ubuntu="lts2023-ubuntu"
        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        echo "6.6lts OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "6.6rt" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/lts-/lts-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/preempt-rt-/preempt-rt-ubuntu-}
        OVERLAY_BRANCH_ubuntu="lts2023-rt-ubuntu"
        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        echo "6.6rt OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "6.12lts" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/lts-/lts-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/linux-/ubuntu-}
        OVERLAY_BRANCH_ubuntu="lts2024-ubuntu"
        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        echo "6.12lts OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "6.12rt" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/lts-/lts-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/preempt-rt-/preempt-rt-ubuntu-}
        OVERLAY_BRANCH_ubuntu="lts2024-rt-ubuntu"
        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        echo "6.12rt OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "mainline-tracking" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/mainline-tracking-/mainline-tracking-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/linux-/ubuntu-}
        OVERLAY_TAG_centos=${OVERLAY_TAG/linux-/centos-}

        TEMP_TAG=${KERNEL_TAG#*tracking-}
        TEMP_TAG=${TEMP_TAG#*prod-}
        KSRC_UPSTREAM_TAG=${TEMP_TAG%-linux*}
        OVERLAY_BRANCH_ubuntu="mainline-tracking/$KSRC_UPSTREAM_TAG-ubuntu"
        OVERLAY_BRANCH_centos="mainline-tracking/$KSRC_UPSTREAM_TAG-centos"

        #OVERLAY_BRANCH_ubuntu="mainline-tracking-ubuntu"
        #OVERLAY_BRANCH_ubuntu="mainline-tracking/v5.17-ubuntu"

        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "MLT OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "mainline-tracking-rt" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/mainline-tracking-/mainline-tracking-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/preempt-rt-/preempt-rt-ubuntu-}

        TEMP_TAG=${KERNEL_TAG#*tracking-}
        TEMP_TAG=${TEMP_TAG#*prod-}
        KSRC_UPSTREAM_TAG=${TEMP_TAG%-preempt-rt*}
        OVERLAY_BRANCH_ubuntu="mainline-tracking-rt/$KSRC_UPSTREAM_TAG-ubuntu"

        #OVERLAY_BRANCH_ubuntu="mainline-tracking-rt/v5.17-rc3-rt6-ubuntu"

        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        #release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "MLT-RT OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "iotg-next" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/iotg-next-/iotg-next-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/linux-/ubuntu-}
        #OVERLAY_TAG_centos=${OVERLAY_TAG/linux-/centos-}
        
        TEMP_TAG=${KERNEL_TAG#*next-}
        KSRC_UPSTREAM_TAG=${TEMP_TAG%-linux*}
        OVERLAY_BRANCH_ubuntu="iotg-next/$KSRC_UPSTREAM_TAG-ubuntu"
        #OVERLAY_BRANCH_centos="iotg-next/$KSRC_UPSTREAM_TAG-centos"

        #OVERLAY_BRANCH_ubuntu="iotg-next-ubuntu"
        #OVERLAY_BRANCH_centos="iotg-next-centos"

        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu
        #release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "iotg-next OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "iotg-next-rt" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/iotg-next-/iotg-next-overlay-}
        OVERLAY_TAG_ubuntu=${OVERLAY_TAG/preempt-rt-/preempt-rt-ubuntu-}
        
        TEMP_TAG=${KERNEL_TAG#*next-}
        KSRC_UPSTREAM_TAG=${TEMP_TAG%-preempt-rt*}
        OVERLAY_BRANCH_ubuntu="iotg-next-rt/$KSRC_UPSTREAM_TAG-ubuntu"

        #OVERLAY_BRANCH_ubuntu="iotg-next-rt-ubuntu"

        release_overlay_tag $OVERLAY_BRANCH_ubuntu $OVERLAY_TAG_ubuntu

        echo "iotg-next-rt OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "svl" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/svl-pre-si-linux-/svl-overlay-linux-}
        OVERLAY_TAG_centos=${OVERLAY_TAG/linux-/centos-}
        
        TEMP_TAG=${KERNEL_TAG#*linux-}
        KSRC_UPSTREAM_TAG=${TEMP_TAG%-*}
        OVERLAY_BRANCH_centos="svl/pre-si/linux/$KSRC_UPSTREAM_TAG-centos"

        release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "svl OVERLAY TAGS are applied successfully! "

    elif [[ "$KERNEL" == "svl_rt" ]]; then
        OVERLAY_TAG=${KERNEL_TAG/svl-pre-si-linux-/svl-overlay-linux-}
        OVERLAY_TAG_centos=${OVERLAY_TAG/linux-/centos-}

        TEMP_TAG=${KERNEL_TAG#*linux-}
        KSRC_UPSTREAM_TAG=${TEMP_TAG%-*}
        OVERLAY_BRANCH_centos="svl/pre-si/linux-rt/$KSRC_UPSTREAM_TAG-centos"

        release_overlay_tag $OVERLAY_BRANCH_centos $OVERLAY_TAG_centos

        echo "svl OVERLAY TAGS are applied successfully! "

    else
        echo "Invalid KERNEL, pls check..."
        exit 1
    fi

    for tag in ${tags}; do
        echo "EXTRA_DATA_TAG=$tag"
    done

popd

