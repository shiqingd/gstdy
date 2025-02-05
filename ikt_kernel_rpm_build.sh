#!/bin/bash -ex

echo $USER

echo $KERNEL_REPO
echo $KERNEL_BRANCH
echo $STAGING_REV
echo $OVERLAY_NAME
echo $OVERLAY_REPO

# echo $STAGING_REV
# echo $UPLOAD_RPM_PACKAGE

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
rm -rf ~/rpmbuild/SPECS/*
rm -rf ~/rpmbuild/BUILD/*
rm -rf ~/rpmbuild/BUILDROOT/*


# clear RPMS
rm ./*.rpm || echo 'no such file'
rm ${RPMBUILD_TOPDIR}/RPMS/x86_64/* || echo 'no such file'
rm ${RPMBUILD_TOPDIR}/SRPMS/* || :


# clone the kernel.spec file and other source file
loginfo 'Clone the kernel.spec file and other source file.'
kernel_repo_dir=${KERNEL_REPO##*/}
rm $kernel_repo_dir -rf
git clone ${KERNEL_REPO} -b master $kernel_repo_dir
pushd $kernel_repo_dir
  git checkout ${STAGING_REV}
popd

# update spec file
SPEC_FILE_NAME='kernel.spec'
KERNEL='svl'
NAME='svl'
date_tag=$(basename $STAGING_REV | awk -F'-' '{print $NF}')
data_MMDD=${date_tag:2:4}
#base_line=$(echo $STAGING_REV | grep -oP '\d+\.\d+(-rt\d+)?' | sed 's/-/_/')

OVERLAY_DIR=$CUR_DIR/overlay/centos

cp -r ${OVERLAY_DIR}/SPECS/$SPEC_FILE_NAME ${RPMBUILD_TOPDIR}/SPECS/
cp -r ${OVERLAY_DIR}/SOURCES/* ${RPMBUILD_TOPDIR}/SOURCES/

./update-build-id.sh -b $BUILD_ID -s ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME

sed -i "/^Name: /c Name: ${NAME}%{?variant}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
# Set embargo name
sed -i "/define embargoname/c %define embargoname ${data_MMDD}.${KERNEL}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
# Set rpmversion
kernel_version=$(echo "$STAGING_REV" | sed -E 's/.*v(6\.[0-9]+)-.*/\1.0/')
sed -i "/define rpmversion/c %define rpmversion  ${kernel_version}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME

# Set sux_ver
rt_version=$(echo $STAGING_REV | sed -n 's/.*-\(rt[0-9]\+\)-.*/\1/p')
rc_version=$(echo $STAGING_REV | sed -n 's/.*-\(rc[0-9]\+\)-.*/\1/p')
if [ -n "$rc_version" ] && [ -n "$rt_version" ]; then
    isrc_rt=1
    sux_ver="${rc_version}-${rt_version}."
    sux_ver_re="${rc_version}${rt_version}."
elif [ -n "$rc_version" ]; then
    isrc_rt=1
    sux_ver="$rc_version."
elif [ -n "$rt_version" ]; then
    isrc_rt=1
    sux_ver="$rt_version."
else
    isrc_rt=0
    sux_ver="."
fi
sed -i "/global isrc_rt/c %global isrc_rt ${isrc_rt}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
sed -i "/define sux_ver/c %define sux_ver ${sux_ver}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
# Set spec release
if [ -n "$rc_version" ] && [ -n "$rt_version" ]; then
  sed -i "/define specrelease/c %define specrelease ${sux_ver_re}${date_tag}_%{pkgrelease}%{?dist}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
else
  sed -i "/define specrelease/c %define specrelease %{?sux_ver}${date_tag}_%{pkgrelease}%{?dist}" ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
fi

if [ -n "$rt_version" ]; then
  sed -i 's|arch/x86/configs/svl.config .config|arch/x86/configs/svl-rt.config .config|g' ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME
fi

build_dir=`rpmspec -P ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME | grep '! -d "linux' | awk -F' ' '{print $NF}'`
build_path="${RPMBUILD_TOPDIR}/BUILD/$build_dir"

echo $build_dir
echo $build_path

# Copy the linux kernel source code to the target dir
kernel_source_dir="${RPMBUILD_TOPDIR}/BUILD/$build_dir"
[ ! -d "$kernel_source_dir" ] && mkdir -p $kernel_source_dir
cp -r ${kernel_repo_dir}/* $kernel_source_dir
tree ${RPMBUILD_TOPDIR} -L 3

# run rpmbuild
rpmbuild -ba ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME --nodeps --verbose

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
sudo cp ${RPMBUILD_TOPDIR}/SPECS/kernel.spec .

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
sudo cp ${RPMBUILD_TOPDIR}/RPMS/x86_64/*.rpm .

IMG_NAME=$(basename ${IMAGE_SOURCE_LOCATION})
wget --no-check-certificate --no-proxy $IMAGE_SOURCE_LOCATION -O $IMG_NAME || cp -f /home/jenkins/$IMG_NAME ./$IMG_NAME
xz -d $IMG_NAME

CENTOS_IMG=$(ls *.img | head -n 1)
# KERNEL_PACKAGE=$(ls ${OVERLAY_NAME}-edge-core*.rpm | head -n 1)
KERNEL_PACKAGE=$(ls ${OVERLAY_NAME}*-core*.rpm | head -n 1)
KERNEL_HEADERS_PACKAGE=$(ls ${OVERLAY_NAME}*-headers*.rpm | head -n 1)
# KERNEL_DEVEL_PACKAGE=$(ls ${OVERLAY_NAME}-edge-devel*.rpm | head -n 1)
KERNEL_DEVEL_PACKAGE=$(ls ${OVERLAY_NAME}*-devel*.rpm | head -n 1)
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


loop_dir=`sudo kpartx -av $CENTOS_IMG | grep 'add map' | tail -n 1 | awk '{print $3}'`

# Step1. inset kernel image and modules
sudo mount /dev/mapper/$loop_dir $CENTOS_MNT_DIR
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
#sudo umount $CENTOS_MNT_DIR

# Step2. copy some file to /boot partition and update boot grub
#sudo mount /dev/mapper/loop6p4 $CENTOS_MNT_DIR
sudo cp ${KERNEL_TMP_DIR}/* $CENTOS_MNT_DIR/boot/
sudo chown root:root "${CENTOS_MNT_DIR}/boot/${NEW_INITRD_FILE}"
sudo chmod 0600 "${CENTOS_MNT_DIR}/boot/${NEW_INITRD_FILE}"

ENTRY_ID=${KERNEL_VERSION}
echo 'entry id is '${ENTRY_ID}
CONF_FILE=${ENTRY_ID}.conf
TEMP_CONF_FILE=$WORK_DIR/$CONF_FILE
CONF_FILE=$CENTOS_MNT_DIR/boot/loader/entries/$CONF_FILE
touch $TEMP_CONF_FILE
echo "title CentOS Linux (${KERNEL_VERSION}) 8 (Core)" >> $TEMP_CONF_FILE
echo "version $KERNEL_VERSION" >> $TEMP_CONF_FILE
echo "linux /boot/$NEW_KERNEL_FILE" >> $TEMP_CONF_FILE
echo "initrd /boot/$NEW_INITRD_FILE \$tuned_initrd" >> $TEMP_CONF_FILE
echo "options \$kernelopts console=tty0 console=ttyS0,115200n8 earlyprintk=ttyS0,115200n8 initcall_debug log_buf_len=200M no_console_suspend nokaslr \$tuned_params" >> $TEMP_CONF_FILE
echo "id centos-${KERNEL_VERSION}" >> $TEMP_CONF_FILE
echo "grub_users \$grub_users" >> $TEMP_CONF_FILE
echo "grub_arg --unrestricted" >> $TEMP_CONF_FILE
echo "grub_class kernel" >> $TEMP_CONF_FILE
sudo cat $TEMP_CONF_FILE
sudo cp $TEMP_CONF_FILE $CONF_FILE
#sudo umount ${CENTOS_MNT_DIR}

# modify the kernel boot order
#sudo mount /dev/mapper/loop6p4 $CENTOS_MNT_DIR
sudo sed -i "s/^saved_entry=.*/saved_entry=${ENTRY_ID}/g" $CENTOS_MNT_DIR/boot/grub2/grubenv
sudo cat $CENTOS_MNT_DIR/boot/grub2/grubenv
#sudo umount $CENTOS_MNT_DIR

# Image 3: copy tools
#sudo mount /dev/mapper/loop6p4 $CENTOS_MNT_DIR
sudo cp $CUR_DIR/simicsfs-client $CENTOS_MNT_DIR/usr/bin
sudo chmod 755 $CENTOS_MNT_DIR/usr/bin/simicsfs-client
# sudo cp -r $CUR_DIR/ltp-ddt $CENTOS_MNT_DIR/opt/
# sudo cp -r $CUR_DIR/Offline_Upload_Gio_test $CENTOS_MNT_DIR/opt/
sudo umount $CENTOS_MNT_DIR

sudo rm -fr $CENTOS_MNT_DIR $KERNEL_TMP_DIR
/home/jenkins/bin/craff $CENTOS_IMG -o $CUR_DIR/svl-bkc-centos-stream-9-${KERNEL_VERSION}.craff
mv ${CENTOS_IMG} $CUR_DIR/svl-bkc-centos-stream-9-${KERNEL_VERSION}.img
cd $CUR_DIR
tar -zcvf svl-bkc-centos-stream-9-${KERNEL_VERSION}.img.tar.gz svl-bkc-centos-stream-9-${KERNEL_VERSION}.img
echo 'Done'

#upload rpm package 
if [ "$UPLOAD_RPM_PACKAGE" == "true" ]; then
	mkdir -p ${STAGING_REV}
	cp -f *.rpm ${STAGING_REV}
	scp -r ${STAGING_REV} sys_oak@oak-07.jf.intel.com:/var/www/html/ikt_kernel_rpm_repo/x86_64/RPMS/
	ssh sys_oak@oak-07.jf.intel.com "export REPREPRO_BASE_DIR=/var/www/html/ikt_kernel_rpm_repo;  createrepo --update /var/www/html/ikt_kernel_rpm_repo/x86_64/"
fi
echo 'Done'

#update overlay branch
OVERLAY_DIR=$CUR_DIR/iotg-kernel-overlay
rm -rf $OVERLAY_DIR

echo "Clone the kernel overlay..."
git clone $OVERLAY_REPO $OVERLAY_DIR
echo "Clone the kernel overlay...Done"

pushd $OVERLAY_DIR

TEMP_TAG=${STAGING_REV#*linux-}
KSRC_UPSTREAM_TAG=${TEMP_TAG%-*}
if [ -n "$rt_version" ]; then
  OVERLAY_BRANCH="svl/pre-si/linux-rt/$KSRC_UPSTREAM_TAG-centos"
else
  OVERLAY_BRANCH="svl/pre-si/linux/$KSRC_UPSTREAM_TAG-centos"
fi

# Switch to overlay branch
if [ $(git branch -r | grep -w origin/$OVERLAY_BRANCH | wc -l) -gt 0 ]; then
        git checkout $OVERLAY_BRANCH
        git fetch origin --tags
        git pull
else
        git checkout -b $OVERLAY_BRANCH origin/svl/v6.11-centos
fi
popd

rm -rf $OVERLAY_DIR/SOURCES/kernel-config/
rm -rf $OVERLAY_DIR/SPECS/
mkdir -p $OVERLAY_DIR/SOURCES/kernel-config/
mkdir -p $OVERLAY_DIR/SPECS/

if [ -d $kernel_repo_dir/arch/x86/configs ]; then
        cp -rf $kernel_repo_dir/arch/x86/configs/* $OVERLAY_DIR/SOURCES/kernel-config/
else
        echo "config for overlay does not exist, please checking ..."
        exit 1
fi

if [ ! -f ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME ]; then
        echo "Error: ${SPEC_FILE} no such file."
        exit 1
else
        cp ${RPMBUILD_TOPDIR}/SPECS/$SPEC_FILE_NAME $OVERLAY_DIR/SPECS/
fi

if git diff --no-ext-diff --quiet $CUR_DIR/iotg-kernel-overlay/SOURCES/ $CUR_DIR/iotg-kernel-overlay/SPECS/; then
        set +x
        echo "===== No changes found in the SOURCES and SPECS folder, No need to submit commit! ====="
        #exit 1
fi

pushd $OVERLAY_DIR

date_tag=$(basename $STAGING_REV | awk -F'-' '{print $NF}')
git add .
git commit -m "Auto update to $OVERLAY_BRANCH ${KSRC_UPSTREAM_TAG}-${date_tag}"

# show the commit info
git log -n1

set +x
overlay_new_commit=$(git log --no-decorate --oneline -n1)
echo "push commit to the remote repo"
git push origin $OVERLAY_BRANCH
echo "push commit done!"

popd

cat << EOF

=================== Build Information Summary ====================
+    New Overlay:   ${OVERLAY_BRANCH}
                    (${overlay_new_commit})
+                   -- Pushed to the remote repo --
+
==================================================================
+                    *** SUCCESS ** END ***                      +
==================================================================
EOF

