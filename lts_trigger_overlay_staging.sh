#!/bin/bash -ex

if [ -z $STAGING_REV ] ; then
    echo "error: parameters are not set !!!"
    exit 1
fi
rm -rf *.prop #clean-up old .prop files if any

datetime=${STAGING_REV##*-}
echo "datetime is $datetime"

if [ ${#datetime} == 14 ] && [[ $datetime =~ [0-9]{6}T[0-9]{6}Z ]] ; then
    echo "datetime format is correct."
else
    echo "error: $datetime datetime format is not correct!!!"
    exit 1
fi

baseline=${STAGING_REV#*lts-}
baseline=${baseline#*pre-prod-}

#for RT
if [[ $STAGING_REV == *preempt-rt* ]]; then
    baseline=${baseline%-preempt*}
        
    #for 5.15rt, for example, sandbox-lts-v5.15.96-rt61-preempt-rt-230412T053516Z
    if [[ $STAGING_REV == *v5.15* ]]; then
        echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_centos.prop
        echo "KERNEL_CONFIG_TAG=5.15/config" >> overlay_centos.prop
        echo "OVERLAY_TARGET_BRANCH=lts2021-rt-centos" >> overlay_centos.prop
        echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_centos.prop # v5.15.96-rt61
        echo "OVERLAY_NAME=lts2021_rt" >> overlay_centos.prop
        echo "UPLOAD_RPM_PACKAGE=$UPLOAD_RPM_PACKAGE" >> overlay_centos.prop

        echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
        echo "KERNEL_CONFIG_TAG=5.15/config" >> overlay_ubuntu.prop
        echo "OVERLAY_TARGET_BRANCH=lts2021-rt-ubuntu" >> overlay_ubuntu.prop
        echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v5.15.96-rt61
        echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
        echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

    #for 6.12rt
    elif [[ $STAGING_REV == *v6.12* ]]; then

        echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
        echo "KERNEL_CONFIG_TAG=6.12/config" >> overlay_ubuntu.prop
        echo "OVERLAY_TARGET_BRANCH=lts2024-rt-ubuntu" >> overlay_ubuntu.prop
        echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop
        echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
        echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

    elif [[ $STAGING_REV == *v6.6* ]]; then

        echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
        echo "KERNEL_CONFIG_TAG=6.6/config" >> overlay_ubuntu.prop
        echo "OVERLAY_TARGET_BRANCH=lts2023-rt-ubuntu" >> overlay_ubuntu.prop
        echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v6.6.1-rt3(example,not real)
        echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
        echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

    #for 6.1rt, for example, sandbox-lts-v6.1.12-rt7-preempt-rt-230330T012509Z
    elif [[ $STAGING_REV == *v6.1* ]]; then

        echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
        echo "KERNEL_CONFIG_TAG=6.1/config" >> overlay_ubuntu.prop
        echo "OVERLAY_TARGET_BRANCH=lts2022-rt-ubuntu" >> overlay_ubuntu.prop
        echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v6.1.12-rt7
        echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
        echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

    else
        echo "Please check $STAGING_REV, maybe wrong"
        exit 1
    fi

#for 5.15lts, for example, lts-v5.15.96-linux-230412T023156Z
elif [[ $STAGING_REV == *v5.15*linux* ]]; then
    baseline=${baseline%-linux*}
    PREINT_branch=sandbox/IKT/v5.15/PREINT/linux

    echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_centos.prop
    echo "KERNEL_CONFIG_TAG=5.15/config" >> overlay_centos.prop
    echo "OVERLAY_TARGET_BRANCH=lts2021-centos" >> overlay_centos.prop
    echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_centos.prop # v5.15.96
    echo "OVERLAY_NAME=lts2021" >> overlay_centos.prop
    echo "UPLOAD_RPM_PACKAGE=$UPLOAD_RPM_PACKAGE" >> overlay_centos.prop

    echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
    echo "KERNEL_CONFIG_TAG=5.15/config" >> overlay_ubuntu.prop
    echo "OVERLAY_TARGET_BRANCH=lts2021-ubuntu" >> overlay_ubuntu.prop
    echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v5.15.96
    echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
    echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

#for 6.12lts / LTS2024
elif [[ $STAGING_REV == *v6.12*linux* ]]; then
    baseline=${baseline%-linux*}

    echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
    echo "KERNEL_CONFIG_TAG=6.12/config" >> overlay_ubuntu.prop
    if [[ $STAGING_REV == *v6.12*linux-cve* ]];then
        echo "OVERLAY_TARGET_BRANCH=lts2024-ubuntu-cve" >> overlay_ubuntu.prop
    else
        echo "OVERLAY_TARGET_BRANCH=lts2024-ubuntu" >> overlay_ubuntu.prop
    fi
    echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v6.12.3 for example
    echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
    echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

#for 6.6lts
elif [[ $STAGING_REV == *v6.6*linux* ]]; then
    baseline=${baseline%-linux*}

    echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
    echo "KERNEL_CONFIG_TAG=6.6/config" >> overlay_ubuntu.prop
    if [[ $STAGING_REV == *v6.6*linux-cve* ]];then
        echo "OVERLAY_TARGET_BRANCH=lts2023-ubuntu-cve" >> overlay_ubuntu.prop
    else
        echo "OVERLAY_TARGET_BRANCH=lts2023-ubuntu" >> overlay_ubuntu.prop
    fi
    echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v6.6.1
    echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
    echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

#for 6.1lts, for example, lts-v6.1.12-linux-230328T070240Z
elif [[ $STAGING_REV == *v6.1*linux* ]]; then
    baseline=${baseline%-linux*}

    echo "KERNEL_QUILT_TAG=$STAGING_REV" > overlay_ubuntu.prop
    echo "KERNEL_CONFIG_TAG=6.1/config" >> overlay_ubuntu.prop
    if [[ $STAGING_REV == *v6.1*linux-cve* ]];then
        echo "OVERLAY_TARGET_BRANCH=lts2022-ubuntu-cve" >> overlay_ubuntu.prop
    else
        echo "OVERLAY_TARGET_BRANCH=lts2022-ubuntu" >> overlay_ubuntu.prop
    fi
    echo "KSRC_UPSTREAM_TAG=$baseline" >> overlay_ubuntu.prop # v6.1.12
    echo "UPLOAD_DEB_PACKAGE=$UPLOAD_DEB_PACKAGE" >> overlay_ubuntu.prop
    echo "KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >> overlay_ubuntu.prop

else
    echo "Input parameter STAGING_REV $STAGING_REV is invalid"
    exit 1
fi

echo "Kernel baseline is $baseline"

if [ "$SKIP_DOWNSTREAM_JOBS" == "true" ]; then
    rm -f *.prop  # delete all .prop file, downstream jobs will not run
fi

