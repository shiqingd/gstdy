#!/usr/bin/env python3
import sys
import os
import argparse
import re
import logging
import shutil
import json
#if not "DJANGO_SETTINGS_MODULE" in os.environ:
#        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
#        import django
#        django.setup()

#from django.core.exceptions import ObjectDoesNotExist
#from django.db.utils import IntegrityError
#from django.db.models import Q
#from django.utils import timezone

#from framework.models import *

from lib.pushd import pushd
from lib.utils import cmd, cal_cpu_num, is_branch
import lib.dry_run


#TODO: move these constants to config file or database
#
# schema of json:
#   {
#       'kernel': {
#           KERNEL1: {
#               'default': {...},
#               SOC: {...},
#           },
#           ...
#       },
#       'bsp': {
#           'onebsp': {...},
#           'armbsp': {...},
#       },
#   }
#
# Note: the variables set in 'SOC' block override the
# ones in 'default' block and 'bsp' block, and the 
# variables set in 'default' override the ones in 'bsp'
#
YOCTO_BUILD_CONF = {
    'kernel': {
        'svl': {
            'default': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.kernel-staging.git',
                'lic_chksum': '6bc538ed5bd9a7fc9398086aedcd7e46',
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic',
                'bsp': 'svlbsp',
            },
            'tgl-rt': {
                'kernel_pp': 'linux-intel-iot-mlt-rt',
                'dcfg_fl': 'x86-mlt-rt.conf',
                'target_prefix': 'mc:x86-mlt-rt:',
                'image_dir': 'build/tmp-x86-mlt-rt-glibc/deploy/images/intel-corei7-64',
                'bsp_patches': (
                    ('intel-innersource/os.linux.yocto.build.meta-intel-distro', 'patches/bsp/0001-config-add-mlt-rt-kernel-support.patch'),
                    ('meta-intel', 'patches/bsp/0001-Change-master-branch-to-main-branch-name.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-mlt-rt-update-kernel-recipes-metadata.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-Added-rt-config-and-rt-tests-for-mainline-tracking-R.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                ),
            },
        },
        'mlt': {
            'default': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.mainline-tracking-staging.git',
                'lic_chksum': '6bc538ed5bd9a7fc9398086aedcd7e46',
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic',
                'bsp': 'onebsp',
            },
            'tgl-ddt': {
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic initcall_debug text log_buf_len=4M no_console_suspend ignore_loglevel intel_pstate=no_hwp',
                'bspcfg_post_lines': ('DISTRO_FEATURES:remove = "kernel-compress-modules"',),
            },
            'ikt-po': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.kernel-staging.git',
            },
            'tgl-rt': {
                'bsp_patches': (
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-Added-rt-config-and-rt-tests-for-mainline-tracking-R.patch'),
                ),
            },
        },
        'lts2024': {
            'default': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git',
                'lic_chksum': '6bc538ed5bd9a7fc9398086aedcd7e46',
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic',
                'bsp': 'onebsp2023',
            },
            'tgl-rt':{
                'kernel_pp': 'linux-intel-iot-lts-rt-6.6',
                'dcfg_fl': 'x86-rt-2023.conf',
                'target_prefix': 'mc:x86-rt-2023:',
                'image_dir': 'build/tmp-x86-rt-2023-glibc/deploy/images/intel-corei7-64',
                'bsp_patches': (
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-updated-rt-config-and-added-rt-tests-for-lts-RT-kern.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                ),
            },
        },
        'lts2023': {
            'default': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git',
                'lic_chksum': '6bc538ed5bd9a7fc9398086aedcd7e46',
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic',
                'bsp': 'onebsp2023',
            },
            'tgl-rt':{
                'kernel_pp': 'linux-intel-iot-lts-rt-6.6',
                'dcfg_fl': 'x86-rt-2023.conf',
                'target_prefix': 'mc:x86-rt-2023:',
                'image_dir': 'build/tmp-x86-rt-2023-glibc/deploy/images/intel-corei7-64',
                'bsp_patches': (
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-updated-rt-config-and-added-rt-tests-for-lts-RT-kern.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                ),
            },
        },
        'lts2022': {
            'default': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git',
                'lic_chksum': '6bc538ed5bd9a7fc9398086aedcd7e46',
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic',
                'kernel_pp': 'linux-intel-iot-lts-6.1',
                'dcfg_fl': 'x86-2022.conf',
                'target_prefix': 'mc:x86-2022:',
                'image_dir': 'build/tmp-x86-2022-glibc/deploy/images/intel-corei7-64',
                'bsp': 'onebsp2021',
            },
            'tgl-rt':{
                'kernel_pp': 'linux-intel-iot-lts-rt-6.1',
                'dcfg_fl': 'x86-rt-2022.conf',
                'target_prefix': 'mc:x86-rt-2022:',
                'image_dir': 'build/tmp-x86-rt-2022-glibc/deploy/images/intel-corei7-64',
                'bsp_patches': (
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-updated-rt-config-and-added-rt-tests-for-lts-2022-RT.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                    ('meta-intel', 'patches/bsp/0001-Change-master-branch-to-main-branch-name.patch'),
                ),
            },
        },
        'lts2021': {
            'default': {
                'kernel_repo_url': r'git://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging.git',
                'lic_chksum': '6bc538ed5bd9a7fc9398086aedcd7e46',
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic',
                'bsp': 'onebsp2021',
            },
            'tgl-ddt': {
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic initcall_debug text log_buf_len=4M no_console_suspend ignore_loglevel intel_pstate=no_hwp',
                'bspcfg_post_lines': ('DISTRO_FEATURES:remove = "kernel-compress-modules"',),
            },
            'tgl-rt':{
                'kernel_pp': 'linux-intel-iot-staging-rt-5.15',
                'dcfg_fl': 'x86-rt-2021.conf',
                'target_prefix': 'mc:x86-rt-2021:',
                'image_dir': 'build/tmp-x86-rt-2021-glibc/deploy/images/intel-corei7-64',
                'bsp_patches': (
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-updated-rt-config-and-added-rt-tests-for-lts-RT-kern.patch'),
                    ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                ),
                'bsp_confs': (
                    ('IMAGE_INSTALL:remove', 'iotg-tsn-ref-sw open62541-iotg open62541-iotg'),
                    ('KERNEL_FEATURES:append', ' intel-dev-po.scc'),
                    ('KERNEL_IMAGE_INSTALL:remove', 'linux-intel-ese-mlt linux-intel-iot-bullpen-5.15 linux-intel-iot-bullpen-rt-5.15 linux-intel-iot-bullpen-5.15-networkproxy linux-intel-iot-lts-5.15 linux-intel-iot-staging-5.15 linux-intel-iot-bullpen-staging-5.15 linux-intel-iot-bullpen-staging-rt-5.15 linux-intel-iot-lts-5.15-networkproxy'),
                ),
            },
            'azb': {
                'kernel_cmd': ' intel_pmc_core.warn_on_s0ix_failures oops=panic initcall_debug text log_buf_len=4M no_console_suspend ignore_loglevel intel_pstate=no_hwp',
                'bspcfg_post_lines': ('DISTRO_FEATURES:remove = "kernel-compress-modules"',),
                'bsp': 'azbbsp',
            },
        },
    },
    'bsp': {
        'svlbsp': {
            'bsp_repo_url': r'https://github.com/intel-innersource/os.linux.yocto.build.manifest.git',
            'bsp_rev_prefix': '',
            'init_opt': '-m default.xml -g all',
            'sync_opt': '--force-sync',
            'kernel_pp': 'linux-intel-iot-mlt',
            'meta_dir': 'intel-embedded-system-enabling',
            'conf_dir': 'build/conf',
            'mc_conf_dir': 'intel-embedded-system-enabling/meta-intel-embedded-system-enabling/meta-intel-distro/conf/multiconfig',
            'lcfg_fl': 'local.conf',
            'dcfg_fl': 'x86-mlt.conf',
            'ccfg_fl': 'vanilla-kernel.conf',
            'mcfg_fl': 'x86-minimal.conf',
            'target_prefix': 'mc:x86-mlt:',
            'image_target': 'core-image-sato-sdk',
            'mini_target_prefix': 'mc:x86-minimal:',
            'mini_image_target': 'core-image-full-cmdline',
            'kernel_target': 'virtual/kernel',
            'image_dir': 'build/tmp-x86-mlt-glibc/deploy/images/intel-corei7-64',
            'image_name': 'core-image-sato-sdk-intel-corei7-64.wic',
            'log_dir': 'build/tmp-glibc/log/cooker/intel-corei7-64',
            'log_name': 'console-latest.log',
            'kernel_uri_var': 'KERNEL_SRC_URI',
            'bsp_patches': (
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                ('meta-intel', 'patches/bsp/0001-Change-master-branch-to-main-branch-name.patch'),
            ),
            'bsp_confs': (
                ('IMAGE_INSTALL:remove', 'iotg-tsn-ref-sw open62541-iotg'),
                ('KERNEL_FEATURES:append', ' intel-dev-po.scc'),
                ('RDEPENDS_perf-tests:append', ' bash'),
                ('KERNEL_IMAGE_INSTALL:remove', 'linux-intel-ese-mlt-rt-5.19 linux-intel-ese-bullpen-5.10 linux-intel-ese-preint-staging-5.10 linux-intel-ese-bullpen-rt-5.10 linux-intel-ese-lts-rt-5.10'),
            ),
            'emptied_files': (),
        },
        'onebsp': {
            'bsp_repo_url': r'https://github.com/intel-innersource/os.linux.yocto.build.manifest.git',
            'bsp_rev_prefix': '',
            'init_opt': '-m default.xml -g all',
            'sync_opt': '--force-sync',
            'kernel_pp': 'linux-intel-iot-mlt',
            'meta_dir': 'intel-embedded-system-enabling',
            'conf_dir': 'build/conf',
            'mc_conf_dir': 'intel-embedded-system-enabling/meta-intel-embedded-system-enabling/meta-intel-distro/conf/multiconfig',
            'lcfg_fl': 'local.conf',
            'dcfg_fl': 'x86-mlt.conf',
            'ccfg_fl': 'vanilla-kernel.conf',
            'mcfg_fl': 'x86-minimal.conf',
            'target_prefix': 'mc:x86-mlt:',
            'image_target': 'core-image-sato-sdk',
            'mini_target_prefix': 'mc:x86-minimal:',
            'mini_image_target': 'core-image-full-cmdline',
            'kernel_target': 'virtual/kernel',
            'image_dir': 'build/tmp-x86-mlt-glibc/deploy/images/intel-corei7-64',
            'image_name': 'core-image-sato-sdk-intel-corei7-64.wic',
            'log_dir': 'build/tmp-glibc/log/cooker/intel-corei7-64',
            'log_name': 'console-latest.log',
            'kernel_uri_var': 'KERNEL_SRC_URI',
            'bsp_patches': (
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-for-MLT-remove-append-from-LINUX_VERSION_EXTENSION.patch'),
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
                ('meta-openembedded', 'patches/bsp/0001-fix-issue-cannot-find-lnl-genl-3-lnl-3.patch'),
            ),
            'bsp_confs': (
                ('IMAGE_INSTALL:remove', 'iotg-tsn-ref-sw open62541-iotg'),
                ('KERNEL_FEATURES:append', ' intel-dev-po.scc'),
                ('RDEPENDS_perf-tests:append', ' bash'),
                ('KERNEL_IMAGE_INSTALL:remove', 'linux-intel-ese-mlt-rt-5.19 linux-intel-ese-bullpen-5.10 linux-intel-ese-preint-staging-5.10 linux-intel-ese-bullpen-rt-5.10 linux-intel-ese-lts-rt-5.10'),
            ),
            'emptied_files': (),
        },
        'onebsp2023': {
            'bsp_repo_url': r'https://github.com/intel-innersource/os.linux.yocto.build.manifest',
            'bsp_rev_prefix': '',
            'init_opt': '-m default.xml -g all',
            'sync_opt': '--force-sync',
            'kernel_pp': 'linux-intel-iot-lts-6.6',
            'meta_dir': 'intel-embedded-system-enabling',
            'conf_dir': 'build/conf',
            'mc_conf_dir': 'intel-embedded-system-enabling/meta-intel-embedded-system-enabling/meta-intel-distro/conf/multiconfig',
            'lcfg_fl': 'local.conf',
            'dcfg_fl': 'x86-2023.conf',
            'ccfg_fl': 'vanilla-kernel.conf',
            'mcfg_fl': 'x86-minimal.conf',
            'target_prefix': 'mc:x86-2023:',
            'image_target': 'core-image-sato-sdk',
            'mini_target_prefix': 'mc:x86-minimal:',
            'mini_image_target': 'core-image-full-cmdline',
            'kernel_target': 'virtual/kernel',
            'image_dir': 'build/tmp-x86-2023-glibc/deploy/images/intel-corei7-64',
            'image_name': 'core-image-sato-sdk-intel-corei7-64.wic',
            'log_dir': 'build/tmp-glibc/log/cooker/intel-corei7-64',
            'log_name': 'console-latest.log',
            'kernel_uri_var': 'KERNEL_SRC_URI',
            'bsp_patches': (
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
            ),
            'bsp_confs': (
                ('IMAGE_INSTALL:remove', 'iotg-tsn-ref-sw open62541-iotg open62541-iotg'),
                ('KERNEL_FEATURES:append', ' intel-dev-po.scc'),
                ('KERNEL_IMAGE_INSTALL:remove', 'linux-intel-ese-mlt linux-intel-iot-bullpen-5.15 linux-intel-iot-bullpen-rt-5.15 linux-intel-iot-bullpen-5.15-networkproxy linux-intel-iot-lts-rt-5.15 linux-intel-iot-staging-rt-5.15 linux-intel-iot-bullpen-staging-5.15 linux-intel-iot-bullpen-staging-rt-5.15 linux-intel-iot-lts-5.15-networkproxy linux-intel-iot-staging-6.1 linux-intel-iot-staging-rt-6.1'),
            ),
            'emptied_files': (),
        },
        'onebsp2021': {
            'bsp_repo_url': r'https://github.com/intel-innersource/os.linux.yocto.build.manifest',
            'bsp_rev_prefix': '',
            'init_opt': '-m default.xml -g all',
            'sync_opt': '--force-sync',
            'kernel_pp': 'linux-intel-iot-staging-5.15',
            'meta_dir': 'intel-embedded-system-enabling',
            'conf_dir': 'build/conf',
            'mc_conf_dir': 'intel-embedded-system-enabling/meta-intel-embedded-system-enabling/meta-intel-distro/conf/multiconfig',
            'lcfg_fl': 'local.conf',
            'dcfg_fl': 'x86-2021.conf',
            'ccfg_fl': 'vanilla-kernel.conf',
            'mcfg_fl': 'x86-minimal.conf',
            'target_prefix': 'mc:x86-2021:',
            'image_target': 'core-image-sato-sdk',
            'mini_target_prefix': 'mc:x86-minimal:',
            'mini_image_target': 'core-image-full-cmdline',
            'kernel_target': 'virtual/kernel',
            'image_dir': 'build/tmp-x86-2021-glibc/deploy/images/intel-corei7-64',
            'image_name': 'core-image-sato-sdk-intel-corei7-64.wic',
            'log_dir': 'build/tmp-glibc/log/cooker/intel-corei7-64',
            'log_name': 'console-latest.log',
            'kernel_uri_var': 'KERNEL_SRC_URI',
            'bsp_patches': (
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
            ),
            'bsp_confs': (
                ('IMAGE_INSTALL:remove', 'iotg-tsn-ref-sw open62541-iotg open62541-iotg'),
                ('KERNEL_FEATURES:append', ' intel-dev-po.scc'),
                ('KERNEL_IMAGE_INSTALL:remove', 'linux-intel-ese-mlt linux-intel-iot-bullpen-5.15 linux-intel-iot-bullpen-rt-5.15 linux-intel-iot-bullpen-5.15-networkproxy linux-intel-iot-lts-rt-5.15 linux-intel-iot-staging-rt-5.15 linux-intel-iot-bullpen-staging-5.15 linux-intel-iot-bullpen-staging-rt-5.15 linux-intel-iot-lts-5.15-networkproxy linux-intel-iot-staging-6.1 linux-intel-iot-staging-rt-6.1'),
            ),
            'emptied_files': (),
        },
        'azbbsp': {
            'bsp_repo_url': r'https://github.com/intel-innersource/os.linux.yocto.build.manifest',
            'bsp_rev_prefix': '',
            'init_opt': '-m azb.xml -g all',
            'sync_opt': '--force-sync',
            'kernel_pp': 'linux-intel-ese-mlt',
            'meta_dir': 'intel-embedded-system-enabling',
            'conf_dir': 'build/conf',
            'mc_conf_dir': 'intel-embedded-system-enabling/meta-intel-embedded-system-enabling/meta-intel-distro/conf/multiconfig',
            'lcfg_fl': 'local.conf',
            'dcfg_fl': 'x86-2021.conf',
            'ccfg_fl': 'vanilla-kernel.conf',
            'mcfg_fl': 'x86-minimal.conf',
            'target_prefix': 'mc:x86-2021:',
            'image_target': 'core-image-sato-sdk',
            'mini_target_prefix': 'mc:x86-minimal:',
            'mini_image_target': 'core-image-full-cmdline',
            'kernel_target': 'virtual/kernel',
            'image_dir': 'build/tmp-x86-2021-glibc/deploy/images/intel-corei7-64',
            'image_name': 'core-image-sato-sdk-intel-corei7-64.wic',
            'log_dir': 'build/tmp-glibc/log/cooker/intel-corei7-64',
            'log_name': 'console-latest.log',
            'kernel_uri_var': 'KERNEL_SRC_URI',
            'bsp_patches': (
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-remove-mainline-tracking.patch'),
                ('intel-innersource/os.linux.yocto.build.meta-intel-iot-bsp', 'patches/bsp/0001-set-CONFIG_GPIO_SYSFS-to-be-y.patch'),
            ),
            'bsp_confs': (
                ('IMAGE_INSTALL:remove', 'iotg-tsn-ref-sw open62541-iotg open62541-iotg'),
                ('KERNEL_FEATURES:append', ' intel-dev-po.scc'),
                ('KERNEL_IMAGE_INSTALL:remove', 'linux-intel-ese-bullpen-5.10 linux-intel-ese-preint-staging-5.10 linux-intel-ese-bullpen-rt-5.10 linux-intel-ese-lts-rt-5.10 linux-intel-iot-lts-rt-5.15 linux-intel-iot-bullpen-5.15 linux-intel-iot-bullpen-rt-5.15 linux-intel-iot-bullpen-5.15-networkproxy linux-intel-iot-staging-rt-5.15 linux-intel-iot-staging-5.15'),
            ),
            'emptied_files': (),
        },
    },
}


class YoctoBuild:
    def __init__(self, **kwargs):
        # variables defined in config file or database
        self.logger = kwargs.get('logger')
        self.bsp_repo_url = kwargs.get('bsp_repo_url')
        self.bsp_rev_prefix = kwargs.get('bsp_rev_prefix')
        self.image_dir = kwargs.get('image_dir')
        self.image_name =  kwargs.get('image_name')
        self.log_dir = kwargs.get('log_dir')
        self.log_name = kwargs.get('log_name')
        self.conf_dir = kwargs.get('conf_dir')
        self.mc_conf_dir = kwargs.get('mc_conf_dir')
        self.meta_dir = kwargs.get('meta_dir')
        self.image_target = kwargs.get('image_target')
        self.kernel_target = kwargs.get('kernel_target')
        self.target_prefix = kwargs.get('target_prefix')
        self.lfs_projects = kwargs.get('lfs_projects', '')
        self.init_opt = kwargs.get('init_opt', '')
        self.sync_opt = kwargs.get('sync_opt', '')
        # kernel preferred provider
        self.kernel_pp = kwargs.get('kernel_pp')
        self.lic_chksum = kwargs.get('lic_chksum', None)
        self.kernel_repo_url = kwargs.get('kernel_repo_url')
        # local conf file: conf/local.conf
        self.lcfg_fl = kwargs.get('lcfg_fl')
        # default conf file
        self.dcfg_fl = kwargs.get('dcfg_fl')
        # customized conf file which is used to set customized confs
        self.ccfg_fl = kwargs.get('ccfg_fl')
        # arch conf file for minimal target
        self.mcfg_fl = kwargs.get('mcfg_fl')
        self.mini_target_prefix = kwargs.get('mini_target_prefix')
        self.mini_image_target = kwargs.get('mini_image_target')
        self.kernel_cmd = kwargs.get('kernel_cmd', None)
        self.compress_image = kwargs.get('compress_image', 'true')
        self.kernel_uri_var = kwargs.get('kernel_uri_var')
        self.bsp_confs = kwargs.get('bsp_confs')
        self.bspcfg_post_lines = kwargs.get('bspcfg_post_lines')
        self.bsp_patches = kwargs.get('bsp_patches')
        # the files that need to be cleaned up before build
        self.emptied_files = kwargs.get('emptied_files')

        # variables passed from cmdline or build env.
        self.workspace = kwargs.get('workspace')
        self.kernel = kwargs.get('kernel')
        self.project = kwargs.get('project')
        self.yocto_release = kwargs.get('yocto_release')
        # add revision prefix(like refs/tags/) if necessary
        if self.bsp_rev_prefix and not self.yocto_release.startswith(r'refs/'):
            self.yocto_release = self.bsp_rev_prefix + self.yocto_release
        self.kernel_revision = kwargs.get('kernel_revision').replace(r'origin/', '')
        self.job_num = kwargs.get('job_num')
        self.repo_mirror = kwargs.get('repo_mirror')
        self.dl_dir = kwargs.get('dl_dir')
        self.sstate_dir = kwargs.get('sstate_dir')
        self.confs = kwargs.get('confs')
        self.log_verbose = kwargs.get('log_verbose')
        self.repo_cmd = kwargs.get('repo_cmd')

        # variables updated/defined here
        self.image_path = os.path.join(self.image_dir, self.image_name)
        self.log_path = os.path.join(self.log_dir, self.log_name)
        self.build_dirname = 'yocto_build'
        self.build_branch = "%s_temp" % (self.build_dirname)
        self.build_top_dir = os.path.join(self.workspace, self.build_dirname)
        if self.repo_mirror:
            self.init_opt += " --reference %s" % self.repo_mirror
        self.build_opt = '-v' if self.log_verbose else ''
        self.confs.append(('BB_NUMBER_THREADS', self.job_num))
        self.local_confs = []
        if self.dl_dir:
            self.confs.append(('DL_DIR', self.dl_dir))
            self.local_confs.append(('DL_DIR', self.dl_dir))
        if self.sstate_dir:
            self.confs.append(('SSTATE_DIR', self.sstate_dir))
            self.local_confs.append(('SSTATE_DIR', self.sstate_dir))
        if self.lic_chksum:
            self.confs.append((
                "LIC_FILES_CHKSUM:pn-%s" % self.kernel_pp,
                "file://COPYING;md5=%s" % self.lic_chksum))

        if self.bsp_confs:
            self.confs.extend(self.bsp_confs)
        self.unset_confs = []

        self.is_branch = is_branch(self.kernel_repo_url.replace('git://', 'https://'),
                                    self.kernel_revision)


    def get_image_path(self):
        return os.path.join(self.build_dirname, self.image_path + '.bz2')


    def get_kernel_revision(self):
        return self.kernel_revision


    def prepare_repo(self, sync_repo=True, exit_on_fail=True):
        if self.bsp_patches:
            bsp_patch_cmds = [ "\
            {repo} forall -vp {metaprj} -c git am {patch}".format(
              repo=self.repo_cmd,
              metaprj=p[0],
              patch=os.path.join(self.workspace, p[1])) \
                for p in self.bsp_patches ]
            bsp_patch_cmds = '\n'.join(bsp_patch_cmds)
        else:
            bsp_patch_cmds = ''

        # expand full path for those which use the local manifest snapshots
        init_opt = self.init_opt.replace(r'%%WORKSPACE%%', self.workspace)

        commands = r"""
            set -x

            {repo} abandon {build_branch}
            # remove previous build folder at the end of job
            test -d build && mv build build.pre.$(date '+%m%d%H%M%S')
            {repo} forall -pc 'git am --abort 2>/dev/null; \
                               git rebase --abort 2>/dev/null; \
                               git reset --hard ; \
                               git clean -ffdx'
            {repo} init -u {repo_url} -b {yocto_rel_tag} {init_opt}
            cp .repo/repo/repo {repo} || :
            {repo} sync -c -j{job_num} {sync_opt}
            {repo} start {build_branch} --all
            {repo} forall -vp {lfs_projects} -c git lfs pull
            # apply extra bsp patch(es) if necessary
{bsppatchcmds}
                   """.format(repo=self.repo_cmd,
                              build_branch=self.build_branch,
                              repo_url=self.bsp_repo_url,
                              yocto_rel_tag=self.yocto_release,
                              init_opt=init_opt,
                              job_num=self.job_num,
                              sync_opt=self.sync_opt,
                              lfs_projects=self.lfs_projects \
                                             if self.lfs_projects else '',
                              bsppatchcmds=bsp_patch_cmds)

        cmd(commands, exit_on_fail=exit_on_fail)

        # clean up the files before starting the build
        # e.g. the kernel patches list
        if self.emptied_files:
            for f in self.emptied_files:
                with open(f, 'w'): pass


    @staticmethod
    def _set_configs(cfg_fl, settings):
        if not settings:
            return

        # set conf variables in build/conf/local.conf
        # any variable set in local.conf overrides the one set elsewhere unless
        # that variable is hard-coded(e.g. by using '=' instead of '?=')

        # compose the re pattern to remove the old settings if exist
        re_ptn = r"^\s*(%s)\s*\??=.*$\n" % '|'.join([ c[0] for c in settings ])
        # compose lines of new settings
        new_cfg = '\n'.join([ "%s = \"%s\"" % (k, str(v)) \
                                for (k, v) in settings ])
        new_cfg = "# Added by kernel script\n%s\n" % new_cfg 
        if os.path.isfile(cfg_fl) and os.path.getsize(cfg_fl) > 0:
            with open(cfg_fl, 'r+') as cf:
                cfg_text = cf.read()
                # remove the original settings
                cfg_text = re.sub(re_ptn, '', cfg_text, flags=re.M)
                # append new settings
                cfg_text += new_cfg
                # overwrite the conf file
                cf.seek(0)
                cf.write(cfg_text)
                cf.truncate()
        else:
            with open(cfg_fl, 'w') as cf:
                cf.write(new_cfg)


    def set_kernel_uri(self):
        # set kernel repo url and staging revision(branch or tag)
        srcrev_var = "SRCREV_machine:pn-%s" % self.kernel_pp
        kuri_var = "%s:pn-%s" % (self.kernel_uri_var, self.kernel_pp)
        if self.is_branch:
            # if revision is a branch
            self.confs.append((
                kuri_var,
                "%s;branch=%s;name=machine;protocol=ssh" % \
                  (self.kernel_repo_url, self.kernel_revision)))
            self.confs.append((srcrev_var, r'${AUTOREV}'))
        else:
            # if revision is a tag
            self.confs.append((
                kuri_var,
                "%s;nobranch=1;name=machine;protocol=https" % \
                  self.kernel_repo_url))
            self.confs.append((srcrev_var, self.kernel_revision))

        self.confs.append(("KBRANCH:pn-%s" % self.kernel_pp,
                           r'${%s}' % srcrev_var))


    def set_kernel_conf(self):
        # set build/conf/multiconfig/x86.conf
        #   PREFERRED_PROVIDER_virtual/kernel = "{kernel_pp}"
        #   KERNEL_SRC_URI:pn-{kernel_pp} = "{kernel_repo_url};nobranch=1;name=machine;protocol=ssh"
        #   SRCREV_machine:pn-{kernel_pp} = "{kernel_revision}"
        #   KERNEL_PACKAGE_NAME:pn-{kernel_pp} = "kernel"
        #   KERNEL_PROVIDERS_EXTRA_MODULES = ""
        #   KERNEL_PROVIDERS_EXTRA_MODULES_forcevariable = ""
        self.confs.append((
            'PREFERRED_PROVIDER_virtual/kernel', self.kernel_pp))
        # set kernel repo url and staging revision(branch or tag)
        self.set_kernel_uri()

        m = re.search(r'-(v[4-9]\.\d[\d\.rc\-]*)-', self.kernel_revision)
        if m:
            self.confs.append((
                "LINUX_VERSION:pn-%s" % self.kernel_pp, m.group(1)))

        self.confs.append((
            "KERNEL_PACKAGE_NAME:pn-%s" % self.kernel_pp, 'kernel'))

        if not self.is_branch:
            logger.debug("kernel pp: %s, kernel rev: %s" % 
                         (self.kernel_pp , self.kernel_revision))
            self.confs.append(("LINUX_VERSION_EXTENSION:pn-%s" %
                          self.kernel_pp, self.kernel_revision.replace('-preempt-rt', '').replace('sandbox-', ''),))

        #self.confs.append((
        #    "LINUX_KERNEL_TYPE:pn-%s" % self.kernel_pp,
        #    self.kernel_pp.split('-')[-1]))
        self.confs.append(('KERNEL_VERSION_SANITY_SKIP', '1'))
        # add unset variables
        self.unset_confs.append('KERNEL_PROVIDERS_EXTRA_MODULES')
        self.unset_confs.append('KERNEL_PROVIDERS_EXTRA_MODULES_forcevariable')


    def set_confs(self):
        conf_dir = self.mc_conf_dir or self.conf_dir

        #if self.dcfg_fl != self.ccfg_fl:
        #    def_cfg = os.path.join(self.build_top_dir, conf_dir, self.dcfg_fl)
        #    # change SELECTABLE_KERNEL_DEFAULT to customized config file
        #    with open(def_cfg, 'r+') as cf:
        #        cfg_text = cf.read()
        #        cfg_text = re.sub(
        #            r'^\s*SELECTABLE_KERNEL_DEFAULT\s*.?=.*$',
        #            'SELECTABLE_KERNEL_DEFAULT = "%s"' % self.ccfg_fl,
        #            cfg_text,
        #            flags=re.M)
        #        # overwrite the conf file
        #        cf.seek(0)
        #        cf.write(cfg_text)
        #        cf.truncate()

        # include customized conf file in the default conf file
        for dcf in (self.dcfg_fl, self.mcfg_fl,):
            if dcf and dcf != self.ccfg_fl:
                dcf_path = os.path.join(self.build_top_dir, conf_dir, dcf)
                with open(dcf_path, 'a') as cf:
                    cf.write("\n# Added by Kernel script\ninclude ./%s\n" % \
                               self.ccfg_fl)

        # unique variables in confs:
        # 1. if a variable is defined twice, the later overwrites the former
        # 2. the sequence of the variable depends on its first occurrence
        ckeys = []
        cdict = {}
        for (k, v) in self.confs:
            if k not in cdict:
                ckeys.append(k)
            cdict[k] = v
        confs = [ (k, cdict[k]) for k in ckeys ]
        # put all conf settings in the customized conf file
        cstm_cfg = os.path.join(self.build_top_dir, conf_dir, self.ccfg_fl)
        YoctoBuild._set_configs(cstm_cfg, confs)
        # add APPEND += <kernel_cmd> and unset variables in customized conf file
        cfg_txt = ""
        if self.kernel_cmd:
            cfg_txt += "APPEND += \"%s\"\n" % self.kernel_cmd
        if self.bspcfg_post_lines:
            cfg_txt += "%s\n" % '\n'.join(self.bspcfg_post_lines)
        if self.unset_confs:
            cfg_txt += '\n'.join([ "unset %s" % c for c in self.unset_confs ])
            cfg_txt += '\n'
        if cfg_txt:
            with open(cstm_cfg, 'a') as cf:
                cf.write(cfg_txt)

        # add SSTATE_DIR, DL_DIR in conf/local.conf anyway
        if self.lcfg_fl != self.ccfg_fl:
            loc_cfg = os.path.join(
                self.build_top_dir, self.conf_dir, self.lcfg_fl)
            YoctoBuild._set_configs(loc_cfg, self.local_confs)


    def build(self, exit_on_fail=True):
        commands = r"""
            set -x
            cd build
            source ../{meta_dir}/oe-init-build-env .
            # just clean kernel's output and sstate so that:
            #   1. kernel's do_fetch can be triggered
            #   2. the rest of sstate cache can be reused
            bitbake -c do_cleanall {target_prefix}{kernel_target}
            source ../{meta_dir}/oe-init-build-env .
            bitbake -e {build_opt} {target_prefix}{image_target} > yocto_env.txt
            bitbake {build_opt} {target_prefix}{image_target}
            test -f ../{img_path}
                    """.format(meta_dir=self.meta_dir,
                               target_prefix=self.target_prefix,
                               kernel_target=self.kernel_target,
                               build_opt=self.build_opt,
                               image_target=self.image_target,
                               mini_target_prefix=self.mini_target_prefix,
                               mini_image_target=self.mini_image_target,
                               img_path=self.image_path)
        cmd(commands, exit_on_fail=exit_on_fail)


    def post_build(self, exit_on_fail=True):
        commands = r"""
            set -x
            cp {log_path} {log_dir}/build.log
            test "{compress_image}" == "false" || bzip2 -zkf {img_path}
            bd_base=$(pwd)
            log_pre=/tmp/delete-build.pre
            rm -f ${{log_pre}}.*
            for d in $(ls | grep build.pre); do
                nohup sudo rm -rf $bd_base/$d > ${{log_pre}}.$d 2>&1 &
            done
                    """.format(img_path=self.image_path,
                               log_path=self.log_path,
                               log_dir=self.log_dir,
                               compress_image=self.compress_image)
        cmd(commands, exit_on_fail=exit_on_fail)


    def do_all(self):
        self.logger.info("PWD={}".format(os.getcwd()))
        self.logger.info("UID={}".format(os.geteuid()))
        self.logger.info("build_top_dir={}".format(self.build_top_dir))
        os.makedirs(self.build_top_dir, exist_ok=True)
        os.chdir(self.build_top_dir)
        self.logger.info("Prepare Yocto repository")
        self.prepare_repo()
        self.logger.info("Set kernel related conf")
        self.set_kernel_conf()
        self.logger.info("Set extra confs in conf file(s)")
        self.set_confs()
        self.logger.info("Start Yocto build")
        self.build()
        self.logger.info("Compress the image and rename the log")
        self.post_build()


def handle_args(args):
    parser = argparse.ArgumentParser(prog = sys.argv[0], epilog = """\
The yocto_staging script will build the kernel from the branch named on
the commandline with various version of Poky.  It will always use the
dev-bkc repo.""")
    parser.add_argument("--kernel", "-k", required=True, type=str,
                        help="Kernel version for which the Yocto is built")
    parser.add_argument("--project", required=True, type=str,
                        help="Specify the project name (tgl, ehl)")
    parser.add_argument("--kernel-branch", "-b", required=True, type=str,
                        help="Staging branch name - this provides the kernel version.")
    parser.add_argument("--yocto-release", "-p", dest = "yocto_release", type=str,
                        help="Yocto project release name (rocko, sumo, master (default))")
    #parser.add_argument("--build-preempt-rt", "-r", action = "store_true", default=False,
    #                    help="build Preempt-RT Version")
    #parser.add_argument("--cpu", "-s", type=CPU.validate,
    #                    help="CPU Type - valid values: "+CPU.list())
    # these are for the new builds
    parser.add_argument("--repo-mirror", "-m", dest = "repo_mirror", type=str,
                        help="The mirror path to Yocto repository")
    parser.add_argument("--dl-dir", "-d", dest = "dl_dir", type=str,
                        help="Path to the downloads directory for Yocto build")
    parser.add_argument("--sstate-dir", "-s", dest = "sstate_dir", type=str,
                        help="Path to the sstate-cache directory for Yocto build")
    parser.add_argument("--dry_run", action="store_true",
                        help="Do not actually do anything; just print what would happen")
    parser.add_argument("--repo-cmd", "-c", dest = "repo_cmd", type=str,
                        help="The path to repo command")
    parser.add_argument("--log-verbose", "-v", action="store_true",
                        help="Log the output of bitbake in verbose mode")
    parser.add_argument("--conf", "-l", dest = "confs", type=json.loads,
                        help="Dict of variables set in conf file(s)")
    return parser.parse_args()


if __name__ == '__main__':
    assert("WORKSPACE" in os.environ)
    logger = logging.getLogger(__name__)
    LOGLEVEL = os.environ.get('LOGLEVEL', 'DEBUG')
    logging.basicConfig(level=LOGLEVEL, format='%(levelname)-5s: %(message)s')

    args = handle_args(sys.argv[0])
    lib.dry_run.dry_run = args.dry_run

    # calculate the number of parallel jobs per available cpu and mem
    job_num = cal_cpu_num()

    # convert dict to list for confs
    if args.confs:
        confs = [ (k, v) for (k, v) in args.confs.items() ]
    else:
        confs = []
    # get settings from cmdline arguments
    kwargs_dict = {
        'workspace': os.environ["WORKSPACE"],
        'kernel': args.kernel,
        'project': args.project.lower(),
        'kernel_revision': args.kernel_branch,
        'yocto_release': args.yocto_release,
        'job_num': job_num,
        'repo_mirror': args.repo_mirror,
        'dl_dir': args.dl_dir,
        'sstate_dir': args.sstate_dir,
        'log_verbose': args.log_verbose,
        'repo_cmd': args.repo_cmd if args.repo_cmd \
                                  else '/home/jenkins/bin/repo.google',
        'confs': confs,
        'logger': logger,
    }
    kernel_conf = YOCTO_BUILD_CONF['kernel']
    bsp_conf = YOCTO_BUILD_CONF['bsp']
    # get configs from YOCTO_BUILD_CONF json
    # first, get SOC specific configs if exist
    if args.project in kernel_conf[args.kernel]:
        for (k, v) in kernel_conf[args.kernel][args.project].items():
            kwargs_dict[k] = v
    # second, get KERNEL['default'] config one by one if it's not available
    for (k, v) in kernel_conf[args.kernel]['default'].items():
        if k not in kwargs_dict:
            kwargs_dict[k] = v
    # last, get bsp default config one by one if it's not available
    for (k, v) in bsp_conf[kwargs_dict['bsp']].items():
        if k not in kwargs_dict:
            kwargs_dict[k] = v

    logger.info(kwargs_dict)

    yb = YoctoBuild(**kwargs_dict)
    yb.do_all()

    # save image url in the downstream.prop file
    image_url = os.path.join(
        os.environ['BUILD_URL'], 'artifact', yb.get_image_path())
    propfl = os.path.join(os.environ['WORKSPACE'], 'downstream.prop')
    with open(propfl, 'w') as pf:
        pf.write("IMAGE_URL=%s\n" % image_url)
        pf.write("STAGING_REVISION=%s\n" % yb.get_kernel_revision())

