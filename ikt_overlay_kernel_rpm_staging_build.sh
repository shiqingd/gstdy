#!/bin/bash -ex

echo $USER

echo $OVERLAY_REPO
echo $OVERLAY_BRANCH
echo $IMAGE_SOURCE_LOCATION
echo $OVERLAY_NAME
echo $STAGING_REV
echo $UPLOAD_RPM_PACKAGE

# To avoid the "BTF: .tmp_vmlinux.btf: pahole (pahole) is not available" issue during build
sudo apt-get --assume-yes install dwarves

CUR_DIR=$(pwd)
RPMBUILD_TOPDIR=~/rpmbuild
# used the default value if jenkins job not set these options
BUILD_ID=${BUILD_ID:='0'}  # BUILD_ID is jenkins job a environment variable

loginfo() {
    echo $(date +"%Y-%m-%d %H:%M:%S >> ")$@
}

# Step1. check if bash is installed
bash_version=$(bash --version || exit 1)
bash_name=$(echo $bash_version | head -n 1 | awk -F',' '{print $1}')
echo $bash_name
if [ "$bash_name" != 'GNU bash' ]; then
  exit 1
fi
# change /bin/sh -> /bin/bash
SHELL=$(ls -l /bin/sh | awk -F'> ' '{print $NF}')
echo $SHELL
if [ "${SHELL}" != "bash" ]; then
  pushd /bin
  loginfo 'change /bin/sh -> /bin/bash'
  sudo rm sh
  sudo ln -s bash sh
  loginfo $(ls -l /bin/sh)
  popd
fi


# check rpmbuild workdir
loginfo 'checking the rpmbuild workdir'
WORKDIRS=(BUILD BUILDROOT RPMS SOURCES SPECS SRPMS)
for dir in ${WORKDIRS[@]}; do
    if [ ! -d "${RPMBUILD_TOPDIR}/${dir}" ]; then
        loginfo "Create the directory ${RPMBUILD_TOPDIR}/${dir}"
        mkdir -p ${RPMBUILD_TOPDIR}/${dir}
    fi
done

# clear ~/rpmbuild/SOURCES
rm -rf ~/rpmbuild/SOURCES/*


# clear RPMS
rm ./*.rpm || echo 'no such file'
rm ${RPMBUILD_TOPDIR}/RPMS/x86_64/* || echo 'no such file'
rm ${RPMBUILD_TOPDIR}/SRPMS/* || :


# clone the kernel.spec file and other source file
loginfo 'Clone the kernel.spec file and other source file.'
spec_repo_dir=${OVERLAY_REPO##*/}
rm $spec_repo_dir -rf
git clone -b ${OVERLAY_BRANCH} ${OVERLAY_REPO} $spec_repo_dir

pushd ${spec_repo_dir}
  ./update-build-id.sh -b $BUILD_ID

  cp -r ./SOURCES ${RPMBUILD_TOPDIR}
  cp ./SPECS/iotg-kernel.spec ${RPMBUILD_TOPDIR}/SPECS
popd

build_dir=`rpmspec -P ${RPMBUILD_TOPDIR}/SPECS/iotg-kernel.spec | grep '! -d "linux' | awk -F' ' '{print $NF}'`
build_path="${RPMBUILD_TOPDIR}/BUILD/$build_dir"
# run rpmbuild
rpmbuild -ba ${RPMBUILD_TOPDIR}/SPECS/iotg-kernel.spec --nodeps --verbose


# Restory /bin/sh link
echo $SHELL
if [ "${SHELL}" != "bash" ]; then
  pushd /bin
  loginfo "change /bin/sh -> /bin/${SHELL}"
  echo ${PASSWORD} | sudo -S rm sh
  echo ${PASSWORD} | sudo -S ln -s ${SHELL} sh
  loginfo $(ls -l /bin/sh)
  popd
fi

cd $WORKSPACE
#cp ${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-edge-core*.rpm \
#${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-edge-devel*.rpm \
#${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-headers*.rpm .
sudo cp ${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}*.rpm .
sudo cp ${RPMBUILD_TOPDIR}/SRPMS/${OVERLAY_NAME}*.src.rpm .
sudo cp ${RPMBUILD_TOPDIR}/BUILD/${build_dir}/.config ./kernel.config
sudo cp ${RPMBUILD_TOPDIR}/SPECS/iotg-kernel.spec .


######### start insert kernel package to centos img #########

# clear old files
sudo rm *.img || echo ''
sudo rm *.img.tar.gz || echo ''
sudo rm *.craff || echo ''
sudo rm -rf /var/lib/dracut/* || echo ''

if [ ! -d centos_dir ]; then
  mkdir centos_dir
else
  rm centos_dir/* || echo 'no such file'
fi

cd centos_dir

#cp ${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-edge-core*.rpm \
#${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-edge-devel*.rpm \
#${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-headers*.rpm .
sudo cp ${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-core*.rpm \
${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-devel*.rpm \
${RPMBUILD_TOPDIR}/RPMS/x86_64/${OVERLAY_NAME}-headers*.rpm .

IMG_NAME=$(basename ${IMAGE_SOURCE_LOCATION})
wget --no-check-certificate --no-proxy $IMAGE_SOURCE_LOCATION -O $IMG_NAME || cp -f /home/jenkins/$IMG_NAME ./$IMG_NAME
xz -d $IMG_NAME

CENTOS_IMG=$(ls *.img | head -n 1)
# KERNEL_PACKAGE=$(ls ${OVERLAY_NAME}-edge-core*.rpm | head -n 1)
KERNEL_PACKAGE=$(ls ${OVERLAY_NAME}-core*.rpm | head -n 1)
KERNEL_HEADERS_PACKAGE=$(ls ${OVERLAY_NAME}-headers*.rpm | head -n 1)
# KERNEL_DEVEL_PACKAGE=$(ls ${OVERLAY_NAME}-edge-devel*.rpm | head -n 1)
KERNEL_DEVEL_PACKAGE=$(ls ${OVERLAY_NAME}-devel*.rpm | head -n 1)
CENTOS_MNT_DIR=./centos_mount_dir
KERNEL_TMP_DIR=./kernel_tmp
WORK_DIR=$(pwd)
# get the kernel version from kernel rpm package
KERNEL_VERSION=$(rpm -qlp $KERNEL_PACKAGE | grep '/lib/modules/' | head -n1 | awk -F'/' '{print $4}')
NEW_INITRD_FILE=initramfs-${KERNEL_VERSION}.img
NEW_KERNEL_FILE=vmlinuz-${KERNEL_VERSION}

# mount centos base image
if [ ! -d $CENTOS_MNT_DIR ]; then
  mkdir $CENTOS_MNT_DIR
else
  sudo umount $CENTOS_MNT_DIR || echo 'not need umount'
fi

if [ ! -d $KERNEL_TMP_DIR ]; then
  mkdir $KERNEL_TMP_DIR
fi
rm $KERNEL_TMP_DIR/* || echo 'No such file.'

# Step1. inset kernel image and modules
sudo mount -o loop,offset=1599078400 $CENTOS_IMG $CENTOS_MNT_DIR
pushd $CENTOS_MNT_DIR
    #echo "rpm2cpio ${WORK_DIR}/${KERNEL_HEADERS_PACKAGE} | sudo cpio -iduvm --extract-over-symlinks"
    #echo "rpm2cpio ${WORK_DIR}/${KERNEL_DEVEL_PACKAGE} | sudo cpio -iduvm --extract-over-symlinks"
    #echo "rpm2cpio ${WORK_DIR}/${KERNEL_PACKAGE} | sudo cpio -iduvm --extract-over-symlinks"
    #exit 0
    rpm2cpio ${WORK_DIR}/${KERNEL_HEADERS_PACKAGE} | sudo cpio -iduvm
    rpm2cpio ${WORK_DIR}/${KERNEL_DEVEL_PACKAGE} | sudo cpio -iduvm
    rpm2cpio ${WORK_DIR}/${KERNEL_PACKAGE} | sudo cpio -iduvm
popd
# generate initrd
sudo cp ${CENTOS_MNT_DIR}/lib/modules/${KERNEL_VERSION}/vmlinuz ${KERNEL_TMP_DIR}/vmlinuz-${KERNEL_VERSION}
sudo cp ${CENTOS_MNT_DIR}/lib/modules/${KERNEL_VERSION}/config ${KERNEL_TMP_DIR}/config-${KERNEL_VERSION}
sudo cp ${CENTOS_MNT_DIR}/lib/modules/${KERNEL_VERSION}/System.map ${KERNEL_TMP_DIR}/System.map-${KERNEL_VERSION}
sudo depmod -b ${WORK_DIR}/${CENTOS_MNT_DIR} ${KERNEL_VERSION}
#cat ${WORK_DIR}/${CENTOS_MNT_DIR}/lib/modules/${KERNEL_VERSION}/modules.dep
dracut ${KERNEL_TMP_DIR}/$NEW_INITRD_FILE --kmoddir ${WORK_DIR}/${CENTOS_MNT_DIR}/lib/modules/${KERNEL_VERSION} \
-v --kernel-image ${WORK_DIR}/${CENTOS_MNT_DIR}/lib/modules/${KERNEL_VERSION}/vmlinuz --kver ${KERNEL_VERSION}
sudo umount $CENTOS_MNT_DIR

# Step2. copy some file to /boot partition and update boot grub
sudo mount -o loop,offset=525336576 $CENTOS_IMG $CENTOS_MNT_DIR
sudo cp ${KERNEL_TMP_DIR}/* $CENTOS_MNT_DIR
sudo chown root:root "${CENTOS_MNT_DIR}/${NEW_INITRD_FILE}"
sudo chmod 0600 "${CENTOS_MNT_DIR}/${NEW_INITRD_FILE}"
ENTRY_FILE=
for entry_file in `sudo find $CENTOS_MNT_DIR/loader/entries/ -name *.conf  -type f`
do
	ENTRY_FILE=$(basename $entry_file)
done
CONF_PREFIX=$(echo $ENTRY_FILE | cut -d '-' -f 1)
echo $CONF_PREFIX

ENTRY_ID=$CONF_PREFIX-${KERNEL_VERSION}
echo 'entry id is '${ENTRY_ID}
CONF_FILE=${ENTRY_ID}.conf
TEMP_CONF_FILE=$WORK_DIR/$CONF_FILE
CONF_FILE=$CENTOS_MNT_DIR/loader/entries/$CONF_FILE
touch $TEMP_CONF_FILE
echo "title CentOS Linux (${KERNEL_VERSION}) 8 (Core)" >> $TEMP_CONF_FILE
echo "version $KERNEL_VERSION" >> $TEMP_CONF_FILE
echo "linux /$NEW_KERNEL_FILE" >> $TEMP_CONF_FILE
echo "initrd /$NEW_INITRD_FILE \$tuned_initrd" >> $TEMP_CONF_FILE
echo "options \$kernelopts \$tuned_params" >> $TEMP_CONF_FILE
echo "id centos-${KERNEL_VERSION}" >> $TEMP_CONF_FILE
echo "grub_users \$grub_users" >> $TEMP_CONF_FILE
echo "grub_arg --unrestricted" >> $TEMP_CONF_FILE
echo "grub_class kernel" >> $TEMP_CONF_FILE
sudo cat $TEMP_CONF_FILE
sudo cp $TEMP_CONF_FILE $CONF_FILE
sudo umount ${CENTOS_MNT_DIR}

# modify the kernel boot order
sudo mount -o loop,offset=1048576 $CENTOS_IMG $CENTOS_MNT_DIR
sudo sed -i "s/^saved_entry=.*/saved_entry=${ENTRY_ID}/g" $CENTOS_MNT_DIR/EFI/centos/grubenv
sudo cat $CENTOS_MNT_DIR/EFI/centos/grubenv
sudo umount $CENTOS_MNT_DIR

# Image 3: copy tools
sudo mount -o loop,offset=1599078400 $CENTOS_IMG $CENTOS_MNT_DIR
sudo cp $CUR_DIR/simicsfs-client $CENTOS_MNT_DIR/usr/bin
sudo chmod 755 $CENTOS_MNT_DIR/usr/bin/simicsfs-client
# sudo cp -r $CUR_DIR/ltp-ddt $CENTOS_MNT_DIR/opt/
# sudo cp -r $CUR_DIR/Offline_Upload_Gio_test $CENTOS_MNT_DIR/opt/
sudo umount $CENTOS_MNT_DIR

sudo rm -r $CENTOS_MNT_DIR $KERNEL_TMP_DIR
craff $CENTOS_IMG -o $CUR_DIR/centos-8.3.2011-${KERNEL_VERSION}.craff
mv ${CENTOS_IMG} $CUR_DIR/centos-8.3.2011-${KERNEL_VERSION}.img
cd $CUR_DIR
tar -zcvf centos-8.3.2011-${KERNEL_VERSION}.img.tar.gz centos-8.3.2011-${KERNEL_VERSION}.img
echo 'Done'

#upload rpm package 
if [ "$UPLOAD_RPM_PACKAGE" == "true" ]; then
	mkdir -p ${STAGING_REV}
	cp -f *.rpm ${STAGING_REV}
	scp -r ${STAGING_REV} sys_oak@oak-07.jf.intel.com:/var/www/html/ikt_kernel_rpm_repo/x86_64/RPMS/
	ssh sys_oak@oak-07.jf.intel.com "export REPREPRO_BASE_DIR=/var/www/html/ikt_kernel_rpm_repo;  createrepo --update /var/www/html/ikt_kernel_rpm_repo/x86_64/"
fi
echo 'Done'

