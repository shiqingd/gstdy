#!/bin/bash -ex

#2023-April-19, v1.01, for 6.1lts and 6.1rt release
#overlay release is covered by 'overlay_tag_release' job

if [[ $KERNEL == *lts* ]];then
  release_tag_name=lts-${BASELINE}-linux-${STAGING_NUMBER}
  release_branch=6.1/linux
else
  release_tag_name=lts-${BASELINE}-preempt-rt-${STAGING_NUMBER}
  release_branch=6.1/preempt-rt
fi
echo "release_tag_name is $release_tag_name"
echo "release_branch is $release_branch"

#init all relate repos, git clone from the scratch, everything is clean
rm -fr os.linux.kernel.kernel-lts-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging

rm -fr os.linux.kernel.kernel-lts
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts

rm -fr linux-intel-lts
git clone https://github.com/intel/linux-intel-lts

rm -fr os.linux.kernel.kernel-dev-quilt
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt

rm -fr os.linux.kernel.kernel-lts-quilt
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt

rm -fr linux-intel-quilt
git clone https://github.com/intel/linux-intel-quilt

rm -fr os.linux.kernel.kernel-lts-cve
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve


tags=""
#push branch/tag from innersource/kernel-lts-staging to innersource/kernel-lts and github/linux-intel-lts
cd os.linux.kernel.kernel-lts-staging
  git checkout $release_branch
  git reset --hard $release_tag_name
  git push origin $release_branch

  git remote add kernel_lts https://github.com/intel-innersource/os.linux.kernel.kernel-lts
  git push kernel_lts $release_branch
  git push kernel_lts $release_tag_name
  test $? -eq 0 && tags="${release_tag_name}:1:2"

  git remote add linux_intel_lts https://github.com/intel/linux-intel-lts
  git push linux_intel_lts $release_branch
  git tag -d $release_tag_name
  git tag -s $release_tag_name -m "" #GPG sign tags for external release
  git push linux_intel_lts $release_tag_name
  test $? -eq 0 && tags="$tags ${release_tag_name}:1:3"
cd -

#push branch/tag from innersource/kernel-dev-quilt to innersource/kernel-lts-quilt and github/linux-intel-quilt
cd os.linux.kernel.kernel-dev-quilt
  git checkout $release_branch
  git reset --hard $release_tag_name
  git push origin $release_branch

  git remote add kernel_lts_quilt https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt 
  git push kernel_lts_quilt $release_branch
  git push kernel_lts_quilt $release_tag_name
  test $? -eq 0 && tags="$tags ${release_tag_name}:2:2"

  git remote add linux_intel_quilt https://github.com/intel/linux-intel-quilt 
  git push linux_intel_quilt $release_branch
  git tag -d $release_tag_name
  git tag -s $release_tag_name -m "" #GPG sign tags for external release
  git push linux_intel_quilt $release_tag_name
  test $? -eq 0 && tags="$tags ${release_tag_name}:2:3"
cd -

#push CVE. LTS has CVE, RT has not CVE
if [[ $KERNEL == *lts* ]];then
  release_cve_tag=lts-${BASELINE}-linux-cve-${STAGING_NUMBER}
  echo "release_cve_tag is $release_cve_tag"

  cd os.linux.kernel.kernel-lts-cve
    git checkout 6.1
    git reset --hard $release_tag_name
    git push origin 6.1
  cd -

  cd linux-intel-lts
    git checkout 6.1/linux-cve
    cp -rf ../os.linux.kernel.kernel-lts-cve/linux/patches/* ./linux/patches/
    git add linux/patches
    git commit -m "Update CVE patches" --allow-empty
    git push origin 6.1/linux-cve
    git tag -s $release_cve_tag -m "Update CVE patches" #GPG sign tags for external release repos
    git push origin $release_cve_tag
    test $? -eq 0 && tags="$tags ${release_cve_tag}:3:3"
  cd -
fi #end of CVE Part

#generate .prop file to call downstream job: 'overlay_tag_release'
echo "KERNEL_TAG=$release_tag_name" > ds_release.prop
echo "KERNEL=$KERNEL" >> ds_release.prop
echo "STAGING_NUMBER=$STAGING_NUMBER" >> ds_release.prop
cat ds_release.prop

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
