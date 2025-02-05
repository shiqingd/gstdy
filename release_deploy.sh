#!/bin/bash -ex

CUR_DIR=$(pwd)
kernel=$1
staging_number=$2
DEPLOY_DEB=$3
DEPLOY_DEB_BULLPEN=$4

REPO_PATH='/var/www/html/ikt_kernel_deb_repo/pool/main/l/'
#KERNEL_P: lts2021/ lts2021-rt/ lts2020/ lts2020-rt/


function deb_deploy_to_latest {

        DEB_H=$(ls $REPO_PATH/$DEB_DIR | grep -iE "^linux-headers-$kernel_verison-(lts|rt|lts-bullpen|rt-bullpen)-${staging_number}_${kernel_verison}" )
        echo "headers file is:" $DEB_H
        DEB_I=$(ls $REPO_PATH/$DEB_DIR | grep -iE "^linux-image-${kernel_verison}-(lts|rt|lts-bullpen|rt-bullpen)-${staging_number}_${kernel_verison}" )
        echo "image file is:" $DEB_I
        DEB_D=$(ls $REPO_PATH/$DEB_DIR | grep -iE "^linux-image-${kernel_verison}-(lts|rt|lts-bullpen|rt-bullpen)-${staging_number}-dbg_${kernel_verison}" )
        echo "debug file is:" $DEB_D

        pushd /var/www/html/ikt_kernel_deb_repo/latest/$KERNEL_P
	#pushd /var/www/html/ikt_kernel_deb_repo/test/$KERNEL_P
        if [ -e "linux-headers-${P_FIELD}_amd64.deb" ] || [ -e "linux-image-${P_FIELD}_amd64.deb" ] || [  -e "linux-image-${P_FIELD}_dbg_amd64.deb" ]; then
                echo "Old symbolic files exist"
                rm -rf "linux-headers-${P_FIELD}_amd64.deb" "linux-image-${P_FIELD}_amd64.deb" "linux-image-${P_FIELD}_dbg_amd64.deb"
                ln -s $REPO_PATH/$DEB_DIR/${DEB_H} linux-headers-${P_FIELD}_amd64.deb
                ln -s $REPO_PATH/$DEB_DIR/$DEB_I linux-image-${P_FIELD}_amd64.deb
                ln -s $REPO_PATH/$DEB_DIR/$DEB_D linux-image-${P_FIELD}_dbg_amd64.deb

                ls -al
        else
                echo "File doesn't exist!"
                exit 1
        fi
        popd
}

if [ "$DEPLOY_DEB" = "true" ]; then
        DEB_DIR=$(ls $REPO_PATH | grep -i $staging_number | grep -v 'bullpen')
        KERNEL_P=$kernel
        case $KERNEL_P in
                "lts2021") P_FIELD="5.15"
                ;;
                "lts2021-bullpen") P_FIELD="5.15-bullpen"
                ;;
                "lts2021-rt") P_FIELD="5.15-rt"
                ;;
                "lts2021-rt-bullpen") P_FIELD="5.15-rt-bullpen"
                ;;
                "lts2020") P_FIELD="5.10"
                ;;
                "lts2020-bullpen") P_FIELD="5.10-bullpen"
		;;
                "lts2020-rt") P_FIELD="5.10-rt"
                ;;
                "lts2020-rt-bullpen") P_FIELD="5.10-rt-bullpen"
                ;;
        esac
	echo $DEB_DIR $KERNEL_P $P_FIELD
        kernel_verison=$(echo ${DEB_DIR} | awk -F'-' '{print $2}')
        echo "kernel_verison:" $kernel_verison
        echo "staging_number:" $staging_number

        deb_deploy_to_latest

fi

if [ "$DEPLOY_DEB_BULLPEN" = "true" ]; then
        DEB_DIR=$(ls $REPO_PATH | grep -i $staging_number | grep 'bullpen')
        KERNEL_P=$kernel-bullpen
        case $KERNEL_P in
                "lts2021") P_FIELD="5.15"
                ;;
                "lts2021-bullpen") P_FIELD="5.15-bullpen"
                ;;
                "lts2021-rt") P_FIELD="5.15-rt"
                ;;
                "lts2021-rt-bullpen") P_FIELD="5.15-rt-bullpen"
                ;;
                "lts2020") P_FIELD="5.10"
                ;;
                "lts2020-bullpen") P_FIELD="5.10-bullpen"
                ;;
                "lts2020-rt") P_FIELD="5.10-rt"
                ;;
                "lts2020-rt-bullpen") P_FIELD="5.10-rt-bullpen"
                ;;
        esac
	echo $DEB_DIR $KERNEL_P $P_FIELD
        kernel_verison=$(echo ${DEB_DIR} | awk -F'-' '{print $2}')
        echo "kernel_verison:" $kernel_verison
        echo "staging_number:" $staging_number

        deb_deploy_to_latest

fi
