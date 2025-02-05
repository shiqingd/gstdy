#!/bin/bash -x

# before send official release emails, to check official tags exist in coressponding git repos
# should be changed when there are new git repo or new projects
# Author: qingdong.shi@intel.com
# V4.03 2020_May_21

#if your machine has no mail command, please install it firstly.
#sudo apt-get install mailutils
#sudo apt-get install sendmail
#usage/steps: 1)mkdir <test_dir> ; 2)put this script in <test_dir>, chmod +x <script> ; 3)example, run ./<script> -l 5.4lts -tag 200410T030357Z
#who will receive emails, please modify EMAIL_TO in this script

Usage()
{
    echo "Two mandatory options/paramaters: -l and release line; -tag and staging number"
    echo "example: $0 -l 6.6lts -tag 240517T123905Z"
    echo "usage: $0 -l { 5.15lts_u(5.15ults) | 5.15lts_t(5.15tlts) | 4.19slts(or 4.19lts_s) | 6.12lts | 6.12rt | 6.1lts | 6.1rt | 6.6lts | 6.6rt | mlt | mlt-rt | iot-next | iot-next-rt | svl | svl_rt } -tag { <staging_number> }"
}

EMAIL_TO="nex.linux.kernel.integration@intel.com"

#check tag exists or not in github linux-intel-lts git repos
function github_linux_intel_lts()
{
    rm -fr linux-intel-lts
    git clone https://github.com/intel/linux-intel-lts
    if [ $? == 0 ];then
        :
        echo "git clone github linux-intel-lts successfully"
    else
        echo "git clone github linux-intel-lts is failed" >> $tmplog
        exit 0
    fi
    cd linux-intel-lts

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        :
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github linux-intel-lts repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github linux-intel-lts repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github linux-intel-quilt git repos
function github_linux_intel_quilt()
{
    # because linux-intel-quilt is noy big, clone it again, which is not slow
    rm -fr linux-intel-quilt
    git clone https://github.com/intel/linux-intel-quilt
    if [ $? == 0 ];then
        :
        echo "git clone github/linux-intel-quilt successfully"
    else
        echo "git clone github/linux-intel-quilt is failed" >> $tmplog
        exit 0
    fi
    cd linux-intel-quilt

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        :
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/linux-intel-quilt repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/linux-intel-quilt repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github/innersource kernel-lts repo
function github_innersource_kernel_lts()
{
    rm -fr github_innersource_kernel_lts
    git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts github_innersource_kernel_lts
    if [ $? == 0 ];then
        echo "git clone github/innersource/kernel-lts successfully"
    else
        echo "git clone github/innersource/kernel-lts is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_kernel_lts

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/kernel-lts repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/kernel-lts repo, please check manually\n" >> ../$tmplog
    fi

    #RT will be "-rt6", "-rt25" or empty, empty means non-RT
    RT=$(echo "$single_tag" | sed -rn 's/.*(-rt[0-9]+).*/\1/p')

    #to show kernel version(Baseline_tag)
    git reset --hard $single_tag
    kernel_version=$(make kernelversion)
    kernel_version=$(echo $kernel_version |sed -e "s/\.0//")
    kernel_version="v${kernel_version}${RT}"
    echo "kernel_version=$kernel_version"
    echo "kernel version is ${kernel_version}" >> ../$tmplog
    git log --oneline -1 $kernel_version
    if [ $? == 0 ];then
        git log --oneline -1 $kernel_version >> ../$tmplog
    else
        echo "$kernel_version not pushed to innersource_kernel_lts repo, please check"
        echo "$kernel_version not pushed to innersource_kernel_lts repo, please check" >> ../$tmplog
        mail -s "Error! $kernel_version not pushed to innersource_kernel_lts repo, please check" $EMAIL_TO < ../$tmplog
        exit 1
    fi

    cd ..
}

#check tag exists or not in github/innersource kernel-dev-quilt repo
function github_innersource_kernel_dev_quilt()
{
    # because kernel-dev-quilt is not big, clone it again, which is not slow
    rm -fr github_innersource_kernel_dev_quilt
    git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt  github_innersource_kernel_dev_quilt
    if [ $? == 0 ];then
        echo "git clone github/innersource/kernel-dev-quilt successfully"
    else
        echo "git clone github/innersource/kernel-dev-quilt is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_kernel_dev_quilt

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/kernel-dev-quilt repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/kernel-dev-quilt repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github/innersource kernel-lts-quilt repo
function github_innersource_kernel_lts_quilt()
{
    # because kernel-lts-quilt is not big, clone it again, which is not slow
    rm -fr github_innersource_kernel_lts_quilt
    git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt  github_innersource_kernel_lts_quilt
    if [ $? == 0 ];then
        echo "git clone github/innersource/kernel-lts-quilt successfully"
    else
        echo "git clone github/innersource/kernel-lts-quilt is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_kernel_lts_quilt

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/kernel-lts-quilt repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/kernel-lts-quilt repo, please check manually\n" >> ../$tmplog
    fi

    #to show kernel version(Baseline_tag)
    git reset --hard $single_tag
    echo "The 1st and 2nd lines of kernel-lts-quilt/patches/series:"
    head -2 patches/series
    echo -e "\nThe 1st and 2nd lines of kernel-lts-quilt/patches/series:" >> ../$tmplog
    head -2 patches/series >> ../$tmplog

    cd ..
}

#check tag exists or not in github/innersource kernel-config repo
function github_innersource_kernel_config()
{
    #because kernel-config is small, clone it again, which is fast
    rm -fr github_innersource_kernel_config
    git clone https://github.com/intel-innersource/os.linux.kernel.kernel-config github_innersource_kernel_config
    if [ $? == 0 ];then
        echo "git clone github/innersource/kernel-config successfully"
    else
        echo "git clone github/innersource/kernel-config is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_kernel_config

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/kernel-config repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/kernel-config repo, please check manually\n" >> ../$tmplog
    fi

    cd ..  
}

#check tag exists or not in github/innersource kernel-lts-cve repo
function github_innersource_kernel_lts_cve()
{
    rm -fr github_innersource_kernel_lts_cve
    git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve github_innersource_kernel_lts_cve
    if [ $? == 0 ];then
        echo "git clone github/innersource/kernel-lts-cve successfully"
    else
        echo "git clone github/innersource/kernel-lts-cve is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_kernel_lts_cve

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/kernel-lts-cve repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/kernel-lts-cve repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github/innersource mainline-tracking repo
function github_innersource_mainline_tracking()
{
    rm -fr github_innersource_mainline_tracking
    git clone https://github.com/intel-innersource/os.linux.kernel.mainline-tracking github_innersource_mainline_tracking
    if [ $? == 0 ];then
        echo "git clone github/innersource/mainline-tracking successfully"
    else
        echo "git clone github/innersource/mainline-tracking is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_mainline_tracking

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/mainline-tracking repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/mainline-tracking repo, please check manually\n" >> ../$tmplog
    fi

    #RT will be "-rt6", "-rt25" or empty, empty means non-RT
    RT=$(echo "$single_tag" | sed -rn 's/.*(-rt[0-9]+).*/\1/p')

    #to show kernel version(Baseline_tag)
    git reset --hard $single_tag
    kernel_version=$(make kernelversion)
    kernel_version=$(echo $kernel_version |sed -e "s/\.0//")
    kernel_version="v${kernel_version}${RT}"
    echo "kernel_version=$kernel_version"
    echo "kernel version is ${kernel_version}" >> ../$tmplog

    git log --oneline -1 $kernel_version
    if [ $? == 0 ];then
        git log --oneline -1 $kernel_version >> ../$tmplog
    else
        echo "$kernel_version not pushed to innersource_mainline_tracking repo, please check"
        echo "$kernel_version not pushed to innersource_mainline_tracking repo, please check" >> ../$tmplog
        mail -s "Error! $kernel_version not pushed to innersource_mainline_tracking repo, please check" $EMAIL_TO < ../$tmplog
        exit 1
    fi

    cd ..
}

#check tag exists or not in github mainline-tracking repo
function github_mainline_tracking()
{
    rm -fr github_mainline_tracking
    git clone https://github.com/intel/mainline-tracking github_mainline_tracking
    if [ $? == 0 ];then
        echo "git clone github/mainline-tracking successfully"
    else
        echo "git clone github/mainline-tracking is failed" >> $tmplog
        exit 0
    fi
    cd github_mainline_tracking

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/mainline-tracking repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/mainline-tracking repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check bullpen tag exists or not in github/innersource iot-kernel-staging repo
function github_innersource_iot_kernel_staging()
{
    rm -fr github_innersource_iot_kernel_staging
    git clone https://github.com/intel-innersource/os.linux.kernel.iot-kernel-staging github_innersource_iot_kernel_staging
    if [ $? == 0 ];then
        echo "git clone github/innersource/iot-kernel-staging successfully"
    else
        echo "git clone github/innersource/iot-kernel-staging is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_iot_kernel_staging

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/iot-kernel-staging repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/iot-kernel-staging repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github/innersource iot-next repo
function github_innersource_iot_next()
{
    rm -fr github_innersource_iot_next
    git clone https://github.com/intel-innersource/os.linux.kernel.iot-next github_innersource_iot_next
    if [ $? == 0 ];then
        echo "git clone github/innersource/iot-next successfully"
    else
        echo "git clone github/innersource/iot-next is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_iot_next

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/iot-next repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/iot-next repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github/innersource iot-kernel-overlay repo
function github_innersource_iot_kernel_overlay()
{
    rm -fr github_innersource_iot_kernel_overlay
    git clone https://github.com/intel-innersource/os.linux.kernel.iot-kernel-overlay github_innersource_iot_kernel_overlay
    if [ $? == 0 ];then
        echo "git clone github/innersource/iot-kernel-overlay successfully"
    else
        echo "git clone github/innersource/iot-kernel-overlay is failed" >> $tmplog
        exit 0
    fi
    cd github_innersource_iot_kernel_overlay

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/innersource/iot-kernel-overlay repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/innersource/iot-kernel-overlay repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#check tag exists or not in github linux-kernel-overlay repo
function github_linux_kernel_overlay()
{
    rm -fr github_linux_kernel_overlay
    git clone https://github.com/intel/linux-kernel-overlay github_linux_kernel_overlay
    if [ $? == 0 ];then
        echo "git clone github/linux-kernel-overlay successfully"
    else
        echo "git clone github/linux-kernel-overlay is failed" >> $tmplog
        exit 0
    fi
    cd github_linux_kernel_overlay

    git tag | grep "$staging_num"
    if [ $? == 0 ];then
        full_tag=$(git tag | grep "$staging_num" )
        echo >> ../$tmplog
        echo "find the tag in github/linux-kernel-overlay repo:" >> ../$tmplog

        for single_tag in $full_tag; do
            SHA1=$(git rev-parse "$single_tag"^0)
            echo "${single_tag}  ${SHA1}" >> ../$tmplog
        done

    else
        echo -e "\ncannot find the tag in github/linux-kernel-overlay repo, please check manually\n" >> ../$tmplog
    fi

    cd ..
}

#Main/main program
if [ $# != 4 ];then
    echo "must has two options, and two coressponding paramaters, they are mandatory."
    Usage
    exit 1
fi

#scan options and parameters
while [ $# -ge 1 ]; do
    opt=$1
    case $opt in
        -l)  shift
             release_line=$1   # for option -l, parameter is release_line name
             shift
             ;;
        -tag)shift
             staging_num=$1          # for option -tag, parameter is staging_number(part of tag)
             shift
             ;;
        *)   Usage
             exit 1
             ;;
    esac         
done

echo "release line is $release_line"
echo "staging number is $staging_num"
#exit 0

#to check staging_number's format is correct
echo $staging_num | grep '[0-9]\{6\}T[0-9]\{6\}Z'
if [ $? != 0 ];then
    echo "You input a wrong tag / wrong staging_number, please check"
    Usage
    exit 1
fi

#final information(successful or failed) will be save in this file ${tmplog}
rm -fr tmplog_*
tmplog="tmplog_$$.log"
mkdir -p tmplog_$$
cd tmplog_$$

#base on release_line name, do coressponding tag-checking
if [ "$release_line" == "4.19slts" ] || [ "$release_line" == "4.19lts_s" ];then
    github_innersource_kernel_lts
    github_innersource_kernel_config
    github_innersource_kernel_dev_quilt
    github_innersource_kernel_lts_quilt
    github_innersource_kernel_lts_cve
    github_linux_intel_lts

elif [ "$release_line" == "5.15lts_u" ] || [ "$release_line" == "5.15lts_t" ]  || [ "$release_line" == "5.15tlts" ] || [ "$release_line" == "5.15ults" ];then
    github_innersource_kernel_lts
    github_innersource_kernel_config
    github_innersource_kernel_lts_cve
    github_linux_intel_lts
   
elif [ "$release_line" == "6.1lts" ] || [ "$release_line" == "6.6lts" ] || [ "$release_line" == "6.12lts" ];then
    github_innersource_kernel_lts
    github_innersource_kernel_lts_quilt
    github_innersource_kernel_lts_cve
    #github_innersource_iot_kernel_staging #for bullpen tag checking
    github_innersource_iot_kernel_overlay
    github_linux_kernel_overlay
    github_linux_intel_quilt
    github_linux_intel_lts

elif [ "$release_line" == "6.1rt" ] || [ "$release_line" == "6.6rt" ] || [ "$release_line" == "6.12rt" ];then
    github_innersource_kernel_lts
    github_innersource_kernel_lts_quilt
    #github_innersource_iot_kernel_staging #for bullpen tag checking
    github_innersource_iot_kernel_overlay
    github_linux_kernel_overlay
    github_linux_intel_quilt
    github_linux_intel_lts

elif [ "$release_line" == "mlt" ] || [ "$release_line" == "mainlinetracking" ] || [ "$release_line" == "mainline-tracking" ] ||\
    [[ "$release_line" == mlt*rt ]] || [[ "$release_line" == mainline*tracking*rt ]];then
    github_innersource_mainline_tracking
    github_innersource_kernel_lts_quilt
    github_innersource_iot_kernel_overlay
    github_linux_kernel_overlay
    github_mainline_tracking
    github_linux_intel_quilt

elif [ "$release_line" == "iot-next" ] || [ "$release_line" == "iotg-next" ] || [ "$release_line" == "iot-next-rt" ]|| [ "$release_line" == "iotg-next-rt" ];then
    github_innersource_iot_next
    github_innersource_kernel_dev_quilt
    github_innersource_iot_kernel_overlay

elif [ "$release_line" == "svl" ] || [ "$release_line" == "svl_rt" ];then
    github_innersource_iot_next
    github_innersource_iot_kernel_overlay

else
    echo "You input a wrong release line, please check"
    Usage
    exit 1
fi

which mail
if [ $? != 0 ];then
    echo "please install mail firstly, please run $0 manually"
    Usage
    exit 0
fi

mail -s "result for checking $release_line $staging_num" $EMAIL_TO < $tmplog 


