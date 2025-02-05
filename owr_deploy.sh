#!/bin/bash -ex
#set +o posix

CUR_DIR=$(pwd)
RPM_DIR="/var/www/html/ikt_kernel_rpm_repo/x86_64/RPMS/"
OAK07_DIR="http://oak-07.jf.intel.com/ikt_kernel_rpm_repo/x86_64/RPMS/"

#kernel: lts2020/ lts2020_rt/ lts2021/ lts2021_rt
KERNEL_TAG=$1
#KERNEL_TAG='lts-v5.10.100-rt62-preempt-rt-220226T032749Z'
JENKINS_LINK=$2
#JENKINS_LINK="https://oak-jenkins.ostc.intel.com/view/LTS/job/IKT-overlay-kernel-rpm-staging-build/355/artifact/"

#lts-v5.15.24-linux-220227T004911Z
#lts-v5.15.24-rt31-preempt-rt-220302T164436Z

if [ -z $KERNEL_TAG ];then
	echo "please input the release tag..."
	exit 1
fi

if [ -z $JENKINS_LINK ];then
	echo "download rpm fils from oak-07 rpm repo"
else
	echo "download rpm files from jenkins job artifacts"
fi

#get staging number for kernel tag
staging_number=$(echo ${KERNEL_TAG} | awk -F'-' '{print $NF}')
#get 5.10.100/v5.10.100-rt62 from kernel tag
if [[ $KERNEL_TAG == *preempt-rt* ]] ; then
	kernel_verison_v=$(echo ${KERNEL_TAG} | awk -F'-' '{printf("%s-%s", $2,$3)}')
	if [[ $kernel_verison_v == *5.15* ]];then
		kernel="lts2021_rt"
	elif [[ $kernel_verison_v == *5.10* ]];then
		kernel="lts2020_rt"
	else
		echo "kernel tag is not acceptable!"
	fi
else
	kernel_verison_v=$(echo ${KERNEL_TAG} | awk -F'-' '{print $2}')
	if [[ $kernel_verison_v == *5.15* ]];then
                kernel="lts2021"
	elif [[ $kernel_verison_v == *5.10* ]];then
                kernel="lts2020"
	else
		echo "kernel tag is not acceptable!"
        fi
fi
kernel_verison=${kernel_verison_v#*v}

echo "===========kernel is $kernel=========="
echo "staging number is $staging_number"
echo "kernel TAG is $KERNEL_TAG"
echo "kernel_verison:" $kernel_verison

WS_DIR=$CUR_DIR/$staging_number
WS_DIR_scratch=$WS_DIR/scratch
WS_DIR_rpms=$WS_DIR/rpms
WS_DIR_images=$WS_DIR/images

mkdir -p $WS_DIR $WS_DIR_scratch $WS_DIR_rpms
pushd $WS_DIR_scratch

#RPM=$(ssh sys_oak@oak-07.jf.intel.com "ls /var/www/html/ikt_kernel_rpm_repo/x86_64/RPMS/ | grep -E $kernel ")
RPM_I=$(ssh sys_oak@oak-07.jf.intel.com "ls $RPM_DIR | grep -E $kernel-${kernel_verison}.${staging_number}_[0-9]+.x86_64.rpm ")
echo "init file is:" $RPM_I
RPM_C=$(ssh sys_oak@oak-07.jf.intel.com "ls $RPM_DIR | grep -E "$kernel-core-$kernel_verison.${staging_number}_[0-9]+.x86_64.rpm"" )
echo "core file is:" $RPM_C
RPM_D=$(ssh sys_oak@oak-07.jf.intel.com "ls $RPM_DIR | grep -E "$kernel-devel-$kernel_verison.${staging_number}_[0-9]+.x86_64.rpm"" )
echo "devel file is:" $RPM_D
RPM_H=$(ssh sys_oak@oak-07.jf.intel.com "ls $RPM_DIR | grep -E "$kernel-headers-$kernel_verison.${staging_number}_[0-9]+.x86_64.rpm"" )
echo "headers file is:" $RPM_H

if [ -z $JENKINS_LINK ]; then
    wget --no-check-certificate $OAK07_DIR/$RPM_I $OAK07_DIR/$RPM_C $OAK07_DIR/$RPM_D $OAK07_DIR/$RPM_H
else
    wget --no-check-certificate $JENKINS_LINK/artifact/$RPM_I $JENKINS_LINK/artifact/$RPM_C $JENKINS_LINK/artifact/$RPM_D $JENKINS_LINK/artifact/$RPM_H
fi

tree
md5sum_B=$(md5sum *)
echo $md5sum_B
zip -r ${KERNEL_TAG}.zip .
# test the zip file
mkdir -p ${WS_DIR_scratch}/test
mv ${WS_DIR_scratch}/${KERNEL_TAG}.zip ${WS_DIR_scratch}/test
pushd ${WS_DIR_scratch}/test
unzip ${KERNEL_TAG}.zip
mv ${WS_DIR_scratch}/test/${KERNEL_TAG}.zip $WS_DIR_rpms
md5sum_A=$(md5sum *)
echo $md5sum_A
popd
rm -rf ${WS_DIR_scratch}/test

pushd $WS_DIR_rpms
touch ${KERNEL_TAG}.json
cat>${KERNEL_TAG}.json<<EOF
{
  "name": "iotg-kernel",
  "version": "${KERNEL_TAG}",
  "metaDataSchemaVersion": "1.0",
  "packageRevision": 0,
  "metaDataComponents": [
     {
	"type": "copyToImage",
	"files": []
     }
  ]
}
EOF
cat ${KERNEL_TAG}.json

if [ $md5sum_A != $md5sum_B ]; then
    echo "md5sum check failed, pls check... "
    exit 1
else
    tree
    echo "md5sum check passed!"
fi

# wit upload RPM files to OWR
#/home/nanli2x/wit deploy iotg-kernel --version ${KERNEL_TAG} --path `pwd`
/home/jiahuamx/workspace/repo/wit deploy iotg-kernel --version ${KERNEL_TAG}  --Artifactory-BaseUrl https://ubit-artifactory-sh.intel.com --path $WS_DIR_rpms
