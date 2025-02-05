#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
echo "mydir=$mydir";
echo "WORKSPACE=$WORKSPACE";
source $mydir/bkc_common.sh # Include library of common build functions

exit_usage()
{
        cat << EOF >&2

USAGE:
	$0 <staging_number> <external release> <internal release> [ -n ]
    external release = true/false
    internal release = true/false
	h|? = help (this screen)

EOF
exit 1
}

if [[ $pre_prod == "true" ]]; then
  PREPROD="pre-prod-"
else
  PREPROD=""
fi

#########################
# main

if [ "${STAGING_NUMBER}" ] ; then
    staging_number=${STAGING_NUMBER}
else
    echo "Need a staging number to merge to mainline tracking!"
    exit_usage
fi

if [ "${INTERNAL}" != false ] && [ "${INTERNAL}" != true ] ; then
    echo "internal needs to be true or false to do an internal mainline tracking release!"
    exit_usage
fi
if [ "${EXTERNAL}" != false ] && [ "${EXTERNAL}" != true ] ; then
    echo "external needs to be true or false to do an external mainline tracking release!"
    exit_usage
fi

OPT_exit_only=false
while getopts "nh?" OPTION; do
    case $OPTION in
        h|?)
            OPT_exit_only=true
            ;;
    esac
done
$OPT_exit_only && exit_usage


echo "Creating/updating working projects"
rm -fr mainline-tracking-staging
rm -fr kernel-dev-quilt
rm -fr kernel-lts-cve
rm -fr mainline-tracking
git clone https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging mainline-tracking-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt          kernel-dev-quilt
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve            kernel-lts-cve
git clone https://github.com/intel/mainline-tracking                                     mainline-tracking

kernel_version=$BASELINE
echo "kernel_version=$BASELINE"

if [[ $kernel_version == v6.11 ]]; then
    OPT_cve=true
    cve_branch=6.11
    PREPROD=""
elif [[ $kernel_version == v6.12 ]]; then
    OPT_cve=true
    cve_branch=6.12
fi

if [[ $OPT_cve == "true" ]];then
    pushd kernel-lts-cve
        git checkout $cve_branch || die " git checkout cve branch failed, please check"
        #if there is no cve pacthes, set OPT_cve=false
        [[ ! -s mainline-tracking/patches/series ]] && OPT_cve=false
    popd
fi

if [ "${EXTERNAL}" == true ] ; then
    pushd mainline-tracking-staging
        add_scm ml_z_github https://github.com/intel/mainline-tracking.git || \
			die "Unable to git-remote-add mainline tracking github"
        add_scm ml_z_innersource https://github.com/intel-innersource/os.linux.kernel.mainline-tracking.git || \
			die "Unable to git-remote-add mainline tracking github/innersource"
    popd
fi

if [ "${INTERNAL}" == true ] ; then
    pushd kernel-dev-quilt
        add_scm ml_z_github_quilt https://github.com/intel/linux-intel-quilt.git || \
		die "Unable to git-remote-add linux-intel-quilt github"
        add_scm ml_z_innersource_quilt https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt.git || \
		die "Unable to git-remote-add mainline tracking github/innersource"
    popd
fi
echo "please check ml_z_github and ml_z_innersource in mainline-tracking-staging directory"

tags=""
if [[ "$kernel_version" != *rt* ]];then
    pushd mainline-tracking-staging
        yocto_tag=mainline-tracking-${PREPROD}${kernel_version}-linux-${staging_number}
        checkout_remote $yocto_tag
        if [ "${INTERNAL}" == true ] ; then
            push_remote ml_z_innersource HEAD mainline-tracking/$kernel_version true
            push_tag ml_z_innersource $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:1:2"
        fi

        if [ "${EXTERNAL}" == true ] ; then
            push_remote ml_z_github HEAD linux/$kernel_version true
            # delete tag locally, re-create it with singingkey and push tag to github external release repo
            git tag -d $yocto_tag || :
            git tag -s $yocto_tag -m ""
            push_tag ml_z_github $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:1:3"
        fi
    popd # popd of mianline-tracking-staging

    if [[ "${EXTERNAL}" == true ]] && [[ $OPT_cve == "true" ]];then
        pushd kernel-lts-cve
            checkout origin/$cve_branch $cve_branch
        popd

        pushd mainline-tracking
            git branch -D linux-cve/$kernel_version || :
            git checkout -B linux-cve/$kernel_version
            rm -rf linux
            cp -r ../kernel-lts-cve/linux .
            git add -f linux
            git commit -m "CVE quilt release for staging: $yocto_tag" || :
            git push -f origin HEAD:refs/heads/linux-cve/$kernel_version
            tag=mainline-tracking-${PREPROD}${kernel_version}-linux-cve-${staging_number}
            git tag $tag -m ""
            push_tag origin $tag
            test $? -eq 0 && tags="$tags ${tag}:3:3"
        popd
    fi

    pushd kernel-dev-quilt
        checkout_remote $yocto_tag
        if [ "${INTERNAL}" == true ] ; then
            push_remote origin HEAD mainline-tracking/$kernel_version
            push_remote ml_z_innersource_quilt HEAD mainline-tracking/$kernel_version true
            push_tag ml_z_innersource_quilt $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:2:2"
        fi

        if [ "${EXTERNAL}" == true ] ; then
            push_remote ml_z_github_quilt HEAD mainline-tracking/linux/$kernel_version true
            # delete tag locally, re-create it with singingkey and push tag to github external release repo
            git tag -d $yocto_tag || :
            git tag -s $yocto_tag -m ""
            push_tag ml_z_github_quilt $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:2:3"
        fi

    popd #popd of kernel-dev-quilt

    #gerenate similar prop file as release.py, used form overlay_tag_release job
    echo "KERNEL_TAG=${yocto_tag}" > ds_release.prop
    echo "KERNEL=mainline-tracking" >> ds_release.prop
    echo "STAGING_NUMBER={staging_number}" >> ds_release.prop

else  # for MLT-RT
    pushd mainline-tracking-staging

        yocto_tag=mainline-tracking-${PREPROD}${kernel_version}-preempt-rt-${staging_number}
        checkout_remote $yocto_tag
        if [ "${INTERNAL}" == true ] ; then
	    push_remote ml_z_innersource HEAD mainline-tracking-rt/$kernel_version true
	    push_tag ml_z_innersource $yocto_tag
	    test $? -eq 0 && tags="$tags ${yocto_tag}:1:2"

	    push_remote origin HEAD mainline-tracking-rt/$kernel_version
        fi

        if [ "${EXTERNAL}" == true ] ; then
            push_remote ml_z_github HEAD preempt-rt/$kernel_version true
            # delete tag locally, re-create it with singingkey and push tag to github external release repo
            git tag -d $yocto_tag || :
            git tag -s $yocto_tag -m ""
            push_tag ml_z_github $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:1:3"
        fi

    popd # popd of mianline-tracking-staging

    pushd kernel-dev-quilt
        checkout_remote $yocto_tag
        if [ "${INTERNAL}" == true ] ; then
            push_remote origin HEAD mainline-tracking-rt/$kernel_version
            push_remote ml_z_innersource_quilt HEAD mainline-tracking-rt/$kernel_version true
            push_tag ml_z_innersource_quilt $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:2:2"
        fi

        if [ "${EXTERNAL}" == true ] ; then
            push_remote ml_z_github_quilt HEAD mainline-tracking/preempt-rt/$kernel_version true
            # delete tag locally, re-create it with singingkey and push tag to github external release repo
            git tag -d $yocto_tag || :
            git tag -s $yocto_tag -m ""
            push_tag ml_z_github_quilt $yocto_tag
            test $? -eq 0 && tags="$tags ${yocto_tag}:2:3"
        fi

    popd #popd of kernel-dev-quilt

    #gerenate similar prop file as release.py, used form overlay_tag_release job
    echo "KERNEL_TAG=${yocto_tag}" > ds_release.prop
    echo "KERNEL=mainline-tracking-rt" >> ds_release.prop
    echo "STAGING_NUMBER={staging_number}" >> ds_release.prop

fi


for tag in $tags; do
    echo "EXTRA_DATA_TAG=$tag"
done

