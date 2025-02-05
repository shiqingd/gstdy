#!/bin/bash -ex
shopt -s extglob

usage() {
        cat <<EOF

USAGE:
  $(basename $0) -p product -s soc -b branch_name

    p = product name
    s = soc build name
    b = staging branch name
    h|? = help (this screen)

    product,soc: ${!kernel_bkc_repos[@]}

EOF
    exit 1
}


_checkout_repo() {
    declare arg_repo_url=$1
    declare arg_remote_nm=$2
    declare arg_branch=$3
    declare arg_scmdir=$4
    declare arg_mrrdir=$5

    Is_tag=no
    if git ls-remote --heads $arg_repo_url $arg_branch | \
      grep "$arg_branch" >/dev/null; then
        echo "This is a branch, Branch exists: $arg_branch"
    elif git ls-remote --tags $arg_repo_url $arg_branch | \
      grep "$arg_branch" >/dev/null; then
        echo "This is a tag, Tag exists: $arg_branch"
	Is_tag=yes
    else
        echo "Please check manually, Branch/Tag does not exist: $arg_branch"
	exit 1
        #arg_branch=${kernel_cfg_default_branch[${product}${SUBSEP}${soc}]}
        #echo "use the default branch $arg_branch"
    fi

    if ! [ -d $arg_scmdir ] ; then
        mkdir -p $arg_scmdir
        rsync -avzq $arg_mrrdir/  $arg_scmdir || \
          git clone $arg_repo_url $arg_scmdir
    fi
    pushd $arg_scmdir
    git remote | grep "^$arg_remote_nm$" >/dev/null || \
    git remote add $arg_remote_nm $arg_repo_url
    if [ $Is_tag == 'yes' ]; then
	git fetch $arg_remote_nm --tags
        git clean -xdf
        git reset --hard
        git checkout tags/$arg_branch -b $arg_branch || \
        git checkout $arg_branch
    else
	git fetch $arg_remote_nm
        git clean -xdf
        git reset --hard
        git checkout $arg_remote_nm/$arg_branch -b $arg_branch || \
        git checkout $arg_branch
        git reset --hard $arg_remote_nm/$arg_branch
    fi
    popd
}


#
# arg1: arg_prod
# arg2: arg_soc
# arg3: arg_branch
#
checkout_kernel() {
    declare arg_prod=$1
    declare arg_soc=$2
    declare arg_branch=$3

    # checkout config repo
    cfg_branch=${kernel_cfg_other_branch[${arg_prod}${SUBSEP}${arg_soc}]}
    if [[ "$arg_prod" = 4.19* ]]; then
        test -z "$cfg_branch" && cfg_branch=${arg_branch/\/@(android|base)/}
    else
        test -z "$cfg_branch" && cfg_branch=${arg_branch/@(android)-/}
    fi
    cfg_repo_url=${kernel_cfg_repos[${arg_prod}${SUBSEP}${arg_soc}]}
    cfg_mrrdir=$mirror_base/${cfg_repo_url##*/}
    _checkout_repo $cfg_repo_url 'z_config' $cfg_branch $cfgdir $cfg_mrrdir

    # checkout kernel repo
    bkc_repo_url=${kernel_bkc_repos[${arg_prod}${SUBSEP}${arg_soc}]}
    bkc_mrrdir=$mirror_base/${bkc_repo_url##*/}
    _checkout_repo $bkc_repo_url 'z_bkc' $arg_branch $bkcdir $bkc_mrrdir
}


#
# arg1: sha1_var - the var will be assigned sha1 value
#
get_sha() {
    # sha for changing kernel version
    eval "$1=\"$(cd $bkcdir; git log --pretty=format:%h -n1 --abbrev=8 2>/dev/null)\""
}


#
# arg1: kernelversion_var - the var will be assigned kernel version value
#
get_kernelversion() {
    # kernel version
    eval "$1=\"$(cd $bkcdir; make kernelversion 2>/dev/null)\""
}


#
# remove android/yocto specific entries and add extra
# ones that desired when compiling kernel for OSI
#
# arg1: soc
# arg2: configuration file that needs to be updated
#
update_config_for_osi() {
    extra_common_cfgs="CONFIG_FHANDLE=y
CONFIG_USER_NS=y
CONFIG_UEVENT_HELPER_PATH=''
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
CONFIG_DM_VERITY_HASH_PREFETCH_MIN_SIZE=1
CONFIG_VT=y
CONFIG_CONSOLE_TRANSLATIONS=y
CONFIG_VT_CONSOLE=y
CONFIG_VT_CONSOLE_SLEEP=y
CONFIG_HW_CONSOLE=y
CONFIG_VT_HW_CONSOLE_BINDING=y
CONFIG_VGA_CONSOLE=y
CONFIG_DUMMY_CONSOLE=y
CONFIG_DUMMY_CONSOLE_COLUMNS=80
CONFIG_DUMMY_CONSOLE_ROWS=25
CONFIG_FRAMEBUFFER_CONSOLE=y
CONFIG_FRAMEBUFFER_CONSOLE_DETECT_PRIMARY=y
CONFIG_LOGO=y
CONFIG_LOGO_LINUX_MONO=y
CONFIG_LOGO_LINUX_VGA16=y
CONFIG_LOGO_LINUX_CLUT224=y
CONFIG_EXPORTFS=y
CONFIG_CRYPTO_USER_API=y
CONFIG_CRYPTO_USER_API_HASH=y
CONFIG_FONT_8x8=y
CONFIG_SYSVIPC=y
CONFIG_SYSVIPC_SYSCTL=y
CONFIG_PM_TEST_SUSPEND=y
CONFIG_DMATEST=y
CONFIG_INTEL_TELEMETRY=y
CONFIG_KPROBES=y
CONFIG_KPROBES_ON_FTRACE=y
CONFIG_KPROBES=y
CONFIG_CRYPTO_SHA1_MB=y
CONFIG_CRYPTO_SHA256_MB=y
CONFIG_CRYPTO_SHA512_MB=y
CONFIG_CRYPTO_TEST=m
CONFIG_USB_UAS=y
CONFIG_INTEL_RAPL=y
CONFIG_DEBUG_KMEMLEAK=y
CONFIG_DEBUG_KMEMLEAK_EARLY_LOG_SIZE=4000
CONFIG_MODULES=y"

    cfgs=""
    test "$1" != "joule" && cfgs="CONFIG_X86_MSR=y"
    cfgs="$extra_common_cfgs $cfgs"

    tmp_clean_sed="/tmp/$(basename $0).sed.clean"
    tmp_insert_sed="/tmp/$(basename $0).sed.insert"
    cat<<EO_SED >$tmp_clean_sed
/^CONFIG_TRUSTY.*=/d
/^CONFIG_ANDROID.*=/d
/^CONFIG_ABL_BOOTLOADER.*=/d
$(for c in $cfgs; do echo "/^${c//=*/=}/d"; done)
EO_SED

    cat<<EO_SED >$tmp_insert_sed
\$a\\
\\
#\\
# Extra configurations for OSI\\
#\\
$(for c in $cfgs; do echo "${c}\\"; done)

EO_SED

    sed -i -f $tmp_clean_sed $2
    sed -i -f $tmp_insert_sed $2
}


#########################
# main
#########################
KERNEL_BKC_REPO='ssh://git-amr-4.devtools.intel.com/kernel-bkc'
KERNEL_CFG_REPO='ssh://git-amr-4.devtools.intel.com/kernel-config'
KERNEL_BKC_GLB_REPO='https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git'
KERNEL_CFG_GLB_REPO='https://github.com/intel-innersource/os.linux.kernel.kernel-config.git'

SUBSEP=','
ARCH=x86_64
DEBUG=yes
declare -A kernel_bkc_repos=(
    [devbkc,joule]=$KERNEL_BKC_REPO
    [devbkc,joule_iot]=$KERNEL_BKC_REPO
    [devbkc,icl]=$KERNEL_BKC_REPO
    [devbkc,kbl]=$KERNEL_BKC_REPO
    [devbkc,bxt_gp]=$KERNEL_BKC_REPO
    [devbkc,clear_linux]=$KERNEL_BKC_REPO
    [mainline_tracking,bxt_gp]='https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git'
    [mainline_tracking,clear_linux]='https://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git'
    [4.9bkc,joule]=$KERNEL_BKC_REPO
    [4.9bkc,joule_iot]=$KERNEL_BKC_REPO
    [4.9bkc,bxt_gp]=$KERNEL_BKC_GLB_REPO
    [4.14bkc,bxt_gp]=$KERNEL_BKC_GLB_REPO
    [4.14bkc,clear_linux]=$KERNEL_BKC_GLB_REPO
    [4.19-lts,clear_linux]=$KERNEL_BKC_GLB_REPO
    [4.19-lts,clear_linux_sos]=$KERNEL_BKC_GLB_REPO
    [5.4bkc,tgl]=$KERNEL_BKC_GLB_REPO
)
declare -A kernel_cfg_repos=(
    [devbkc,joule]='ssh://git-amr-4.devtools.intel.com/kernel-meta-intel-dev'
    [devbkc,joule_iot]=$KERNEL_CFG_REPO
    [devbkc,icl]=$KERNEL_CFG_REPO
    [devbkc,kbl]=$KERNEL_CFG_REPO
    [devbkc,bxt_gp]=$KERNEL_CFG_REPO
    [devbkc,clear_linux]=$KERNEL_CFG_REPO
    [4.9bkc,joule]='ssh://git-amr-4.devtools.intel.com/kernel-meta-intel-dev'
    [4.9bkc,joule_iot]=$KERNEL_CFG_REPO
    [4.9bkc,bxt_gp]=$KERNEL_CFG_GLB_REPO
    [4.14bkc,bxt_gp]=$KERNEL_CFG_GLB_REPO
    [4.14bkc,clear_linux]=$KERNEL_CFG_GLB_REPO
    [mainline_tracking,bxt_gp]=$KERNEL_CFG_GLB_REPO
    [mainline_tracking,clear_linux]=$KERNEL_CFG_GLB_REPO
    [4.19-lts,clear_linux]=$KERNEL_CFG_GLB_REPO
    [4.19-lts,clear_linux_sos]=$KERNEL_CFG_GLB_REPO
    [5.4bkc,tgl]=$KERNEL_CFG_GLB_REPO
)
declare -A kernel_cfg_other_branch=(
    [devbkc,joule]='pyro'
    [4.9bkc,joule]='pyro'
)
declare -A kernel_cfg_default_branch=(
    [devbkc,joule]='dev-bkc-embargoed'
    [devbkc,joule_iot]='dev-bkc-embargoed'
    [devbkc,icl]='dev-bkc-embargoed'
    [devbkc,kbl]='dev-bkc-embargoed'
    [devbkc,bxt_gp]='dev-bkc-embargoed'
    [devbkc,clear_linux]='mainline-tracking'
    [4.9bkc,joule]='4.9/lts'
    [4.9bkc,joule_iot]='4.9/lts'
    [4.9bkc,bxt_gp]='4.9/config'
    [4.14bkc,bxt_gp]='4.14/config'
    [4.14bkc,clear_linux]='4.14/config'
    [mainline_tracking,bxt_gp]='mainline-tracking'
    [mainline_tracking,clear_linux]='mainline-tracking/config'
    [5.4bkc,tgl]='5.4/config'
)

while getopts "p:b:s:h?" opt; do
    case $opt in
      p)
        product=${OPTARG}
        ;;
      b)
        branch=${OPTARG}
        ;;
      s)
        soc=${OPTARG}
        ;;
      h|?)
        usage
        ;;
    esac
done

if [ -z "$product" ] ; then
    echo "No product specified!"
    usage
fi
if [ -z "$soc" ] ; then
    echo "No soc specified!"
    usage
fi
if [ -z "$branch" ] ; then
    echo "Need a branch!"
    usage
fi

test -z "${kernel_bkc_repos[${product}${SUBSEP}${soc}]}" && usage

if [ -z "$WORKSPACE" ] ; then
    WORKSPACE=$PWD
fi
mirror_base=$(cd /mirrors; pwd)
myws=$WORKSPACE/osit/${product}-${soc}
bkcdir=$myws/bkc
cfgdir=$myws/cfg
outdir=$myws/out

revise_cfg_flag=true
case "${product}${SUBSEP}${soc}" in
  devbkc,joule)
    cfg_fls_dir="$cfgdir/recipes-kernel/linux/files"
    cfg_fls="$cfg_fls_dir/defconfig $cfg_fls_dir/intel-dev.cfg"
    debug_cfg_fls=""
    revise_cfg_flag=false
    ;;
  devbkc,joule_iot)
    cfg_fls_dir="$cfgdir/bxt/iot/embargoed"
    cfg_fls="$cfg_fls_dir/joule.kconf"
    debug_cfg_fls=""
    ;;
  devbkc,icl)
    cfg_fls_dir="$cfgdir/icl/android/embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  devbkc,kbl)
    cfg_fls_dir="$cfgdir/kbl/android/embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  devbkc,bxt_gp)
    cfg_fls_dir="$cfgdir/bxt/android/embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  devbkc,clear_linux)
    cfg_fls_dir="$cfgdir/bxt/clear/bare_metal/embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  mainline_tracking,bxt_gp)
    cfg_fls_dir="$cfgdir/bxt/android"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  mainline_tracking,clear_linux)
    cfg_fls_dir="$cfgdir/bxt/clear/bare_metal"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  4.14bkc,bxt_gp)
    cfg_fls_dir="$cfgdir/bxt/android"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  4.14bkc,clear_linux)
    cfg_fls_dir="$cfgdir/bxt/clear/bare_metal/non-embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  4.19-lts,clear_linux)
    cfg_fls_dir="$cfgdir/bxt/clear/bare_metal/non-embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  4.19-lts,clear_linux_sos)
    cfg_fls_dir="$cfgdir/bxt/clear/service_os/non-embargoed"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  4.9bkc,joule)
    cfg_fls_dir="$cfgdir/recipes-kernel/linux/files"
    cfg_fls="$cfg_fls_dir/defconfig $cfg_fls_dir/intel-dev.cfg"
    debug_cfg_fls=""
    revise_cfg_flag=false
    ;;
  4.9bkc,joule_iot)
    cfg_fls_dir="$cfgdir/bxt/iot"
    cfg_fls="$cfg_fls_dir/joule.kconf"
    debug_cfg_fls=""
    ;;
  4.9bkc,bxt_gp)
    cfg_fls_dir="$cfgdir/bxt/android"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  5.4bkc,tgl)
    cfg_fls_dir="$cfgdir/tgl/yocto"
    cfg_fls="$cfg_fls_dir/x86_64_defconfig"
    debug_cfg_fls=""
    ;;
  *)
    usage
    ;;
esac

rm -fr ${myws} #delete the last build's directory

checkout_kernel $product $soc $branch
bkc_sha1=""
get_sha bkc_sha1

# copy kernel config into bkc dir
target_cfg=$bkcdir/.config
cat $cfg_fls > $target_cfg
test "$DEBUG"=="yes" -a -n "$debug_cfg_fls" && cat $debug_cfg_fls >> $target_cfg
sed -i -e "/^CONFIG_LOCALVERSION/ s/CONFIG_LOCALVERSION=.*/CONFIG_LOCALVERSION=\"-$bkc_sha1\"/" \
  $target_cfg
# update config for OSI if necessary. clear linux does not neeed OSI modification
if [ $soc != 'clear_linux' ]; then
test "$revise_cfg_flag" == "true" && update_config_for_osi $soc $target_cfg
fi

# make kernel
rm -rf $outdir
mkdir -p $outdir/$ARCH
pushd $bkcdir
touch .scmversion
make ARCH=$ARCH olddefconfig
make ARCH=$ARCH clean
make ARCH=$ARCH -j $(nproc)
make ARCH=$ARCH -j $(nproc) modules
make ARCH=$ARCH INSTALL_PATH=$outdir/$ARCH install
make ARCH=$ARCH INSTALL_MOD_PATH=$outdir/$ARCH modules_install
rm -f $outdir/$ARCH/lib/modules/*/build
rm -f $outdir/$ARCH/lib/modules/*/source
popd

get_kernelversion kernel_ver
tarball_nm=${product}-${soc}-${kernel_ver}-${BUILD_NUMBER}.tar.bz2
tar -C $outdir/$ARCH -jcf $outdir/$tarball_nm .

