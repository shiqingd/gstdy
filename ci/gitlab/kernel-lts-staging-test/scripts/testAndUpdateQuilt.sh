#/bin/bash


patch_name=$(ls -1 *.patch)
cd ..
TOPDIR=`pwd`
SRCDIR="kernel-lts-staging-test"
QUILTDIR="kernel-dev-quilt-test"
LABEL=$CI_MERGE_REQUEST_LABELS

git config --global user.email "sys_oak@intel.com"
git config --global user.name "sys_oak on gitlab runner"
#git clone ssh://git@gitlab.devtools.intel.com/linux-kernel-integration/kernel-lts-staging-test
git clone https://sys_oak:${SYS_OAK_CRED_AD}@gitlab.devtools.intel.com/linux-kernel-integration/kernel-dev-quilt-test.git
cd $TOPDIR/$QUILTDIR
git checkout -b 5.8/yocto origin/5.8/yocto
git clean -xdf

#
#cd $TOPDIR/$SRCDIR
#git format-patch origin/5.8/ref/yocto HEAD
cp $TOPDIR/$SRCDIR/*.patch $TOPDIR/$QUILTDIR/patches/
#Get label info 
#Find the right section in series and update it
echo "$LABEL"
## TBD - Validate the label name - check with existing domainlookup scripts
echo "$patch_name"
command="cat $TOPDIR/$QUILTDIR/patches/series | sed -n '/."$LABEL"/p' | tail -n 1"
echo "$command"
last_patch=$(eval $command)
echo "$last_patch"
sed -i  "s/$last_patch/$last_patch\n$patch_name/"  $TOPDIR/$QUILTDIR/patches/series  # insert the patch name behind the last label


#Test Quilt series
cd $TOPDIR/$SRCDIR
git clean -xdf
git checkout origin/5.8/baseline
cp -r $TOPDIR/$QUILTDIR/patches .
git quiltimport
git diff  origin/$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME
#git diff origin/sandbox/rdutta/test-1
if [ "$(git diff origin/$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME | grep '^[+,-]')" != "" ] ; then
   echo "Quilt update does not align\n";
   exit 1
fi
#clean up workspace 
git reset --hard  origin/5.8/baseline

#if everything ok - commit the changes 
echo "Updating quilt series"
cd $TOPDIR/$QUILTDIR
git add patches/*
git commit -s -m "Update quilt series"
git push https://sys_oak:${SYS_OAK_CRED_AD}@gitlab.devtools.intel.com/linux-kernel-integration/kernel-dev-quilt-test.git HEAD:5.8/yocto
