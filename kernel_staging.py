#!/usr/bin/env python3
import sys
import os
import argparse
import re
import logging
import shutil
from pathlib import Path
import yaml
import requests
from bs4 import BeautifulSoup
if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

#from django.core.exceptions import ObjectDoesNotExist
from framework.models import Kernel, KernelRepoSet

from lib.download import HttpDownloader
from lib.pushd import pushd
from lib.utils import (
    get_sha_last_commit,
    checkout,
    is_branch,
    cmd,
    cal_cpu_num,
    get_kernel_baseline,
    make_tarfile,
    unpack_archive
)

logger = logging.getLogger(__name__)


# strip the duplicated '/' from 'https://aaa.com//bbb/...'
def urldedup(url):
    return re.sub(r'[^:]/{2,}', '', url)


class KernelBuild:
    def __init__(self, **kwargs):
        # variables passed from cmdline or build env.
        self.kernel = kwargs.get('kernel')
        self.soc = kwargs.get('soc')
        self.staging_revision = kwargs.get('staging_revision').lstrip('origin/')
        self.arch = kwargs.get('arch', 'x86_64')
        self.workspace = kwargs.get('workspace')
        self.cpu_num = kwargs.get('cpu_num')
        self.kconfigs = kwargs.get('kconfigs', [])
        self.kconf_path = kwargs.get('kconf_path')
        self.initramfs_path = kwargs.get('initramfs_path')

        self.top_build_dir = os.path.join(self.workspace, 'kernel_build')
        self.build_timestamp = self.staging_revision.split('-')[-1]
        self.out_dir = os.path.join(self.top_build_dir, 'out')
        self.repo = KernelRepoSet.objects.get(repo__repotype__repotype='src',
                                              repo__external=False,
                                              kernel_id=self.kernel.id).repo
        self.repo_url = self.repo.url()


    def get_staging_revision(self):
        return self.staging_revision


    def get_tarball_path(self):
        return self.tarball_path


    def prepare_repo(self):
        # initialize the kernel repo.
        logger.info("Initialize or sync kernel repo: %s" % self.repo_url)
        self.repo.initialize(scmdir=self.top_build_dir)
        rmt_ref = self.staging_revision
        loc_ref = None
        if is_branch(self.repo_url, self.staging_revision):
            # for branch
            rmt_ref = 'origin/' + rmt_ref
            loc_ref = self.staging_revision
        else:
            # for tag
            loc_ref = rmt_ref + '_local'
        with pushd(self.top_build_dir):
            # checkout kernel repo to the specified branch/tag
            logger.info("Checkout to the staging revision")
            checkout(rmt_ref, loc_ref)
            # get sha1 of the specified staging_revision
            self.kernel_sha1 = get_sha_last_commit('.')
            # get baseline kernel version
            self.baseline = get_kernel_baseline(self.kernel_sha1)[0]
            logger.info("Staging revision: %s (baseline: %s)" % \
                          (self.kernel_sha1, self.baseline))
        # compose the dest tarball name
        self.tarball_name = "kernel-%s-%s-%s.tar.bz2" % \
                              (self.soc, self.baseline, self.build_timestamp)
        # compose the dest tarball path
        self.tarball_path = os.path.join(self.out_dir, self.tarball_name)


    @staticmethod
    def _set_kconfigs(cfg_fl, configs):
        # compose the re pattern to remove the old configs if exist
        re_ptn = r"^\s*(%s)=.*$" % '|'.join([ c[0] for c in configs ])
        # compose lines of new config settings
        new_cfg = '\n'.join([ "%s=%s" % (k, str(v)) for (k, v) in configs ])
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


    def set_kconfigs(self):
        dest_config = os.path.join(self.top_build_dir, '.config')
        shutil.copy(self.kconf_path, dest_config)
        KernelBuild._set_kconfigs(dest_config, self.kconfigs)


    def makeup_kconfigs(self):
        # the configs for Yocto build
        kconfs = [
            ('CONFIG_LOCALVERSION', '"-IKT-%s"' % self.build_timestamp),
            ('CONFIG_INITRAMFS_SOURCE', '"%s"' % self.initramfs_path),
            ('CONFIG_EXTRA_FIRMWARE', '""'),
            ('CONFIG_EXTRA_FIRMWARE_DIR', '""'),
        ]
        self.kconfigs.extend(kconfs)


    def build(self, exit_on_fail=True):
        commands = r"""
            set -x

            rm -rf {outdir}
            mkdir -p {outdir}/{arch}
            touch .scmversion
            make ARCH={arch} olddefconfig
            make ARCH={arch} clean
            make ARCH={arch} -j {cpunum}
            make ARCH={arch} -j {cpunum} modules
            make ARCH={arch} INSTALL_PATH={outdir}/{arch} install
            make ARCH={arch} INSTALL_MOD_PATH={outdir}/{arch} modules_install
            rm -f {outdir}/{arch}/lib/modules/*/build
            rm -f {outdir}/{arch}/lib/modules/*/source
                    """.format(outdir=self.out_dir,
                               arch=self.arch,
                               cpunum=self.cpu_num)
        cmd(commands, exit_on_fail=exit_on_fail)


    def post_build(self):
        kernel_out = os.path.join(self.out_dir, self.arch)
        make_tarfile(self.tarball_path,
                     kernel_out,
                     self.tarball_name.split('.')[-1])


    def do_all(self):
        logger.info("Try to remove previous build dir: %s" % self.out_dir)
        shutil.rmtree(self.out_dir, ignore_errors=True)
        logger.info("Prepare Kernel repository: %s" % self.repo_url)
        self.prepare_repo()
        with pushd(self.top_build_dir):
            logger.info("Make up kernel config")
            self.makeup_kconfigs()
            self.set_kconfigs()
            logger.info("Start Kernel build")
            self.build(exit_on_fail=True)
        logger.info("Compress tarball: %s" % self.tarball_path)
        self.post_build()


class YoctoArtifacts():
    @classmethod
    def get_artifact_url(cls, dir_url, rep, auth):
        arti_re = re.compile(rep)
        r = requests.get(dir_url, auth=auth)
        bs = BeautifulSoup(r.text, 'html.parser')
        arti_url = None
        for a in bs.find_all('a'):
            filename = a.text.strip()
            m = arti_re.search(filename)
            if m:
                arti_url = '/'.join((dir_url, filename,))
                arti_url = urldedup(arti_url)
                break
        return arti_url


    def __init__(self, **kwargs):
        self.conf = kwargs.get('conf')
        self.workspace = kwargs.get('workspace')
        self.yocto_artifacts_url = None
        arti_usr = os.environ.get('ARTI_USR', None)
        arti_pwd = os.environ.get('ARTI_PWD', None)
        if arti_usr and arti_pwd:
            self.auth = (arti_usr, arti_pwd,)
        else:
            self.auth = None

        self.artifacts = {}
        for artifact, conf in self.conf['artifacts'].items():
            arti_var = "yocto_%s_url" % artifact
            if arti_var in kwargs:
                arti_url = kwargs.get(arti_var)
            else:
                if not self.yocto_artifacts_url:
                    self.yocto_artifacts_url = kwargs.get('yocto_artifacts_url',
                                                          None)
                    assert self.yocto_artifacts_url, \
                             "No yocto artifacts url specified"
                if conf['dir']:
                    dir_url = '/'.join((self.yocto_artifacts_url, conf['dir'],))
                    dir_url = urldedup(dir_url)
                else:
                    dir_url = self.yocto_artifacts_url
                arti_url = YoctoArtifacts.get_artifact_url(dir_url,
                                                           conf['rep'],
                                                           self.auth)
            assert arti_url, "Cannot get url of %s" % artifact
            self.artifacts[artifact] = {
                'url': arti_url,
            }
            if 'archive' in conf and conf['archive']:
                self.artifacts[artifact]['archive'] = conf['archive']

        m = re.search(self.conf['build_number_rep'],
                      self.artifacts['img']['url'])
        assert m, "Cannot get build no.: %s" % self.artifacts['img']['url']
        self.build_number = m.group(1)

        self.artifact_dir = os.path.join(
          self.workspace, 'artifacts', self.build_number)
        for artifact, arti_val in self.artifacts.items():
            # don't need to download yocto image
            if artifact == 'img':
                continue
            filename = os.path.basename(arti_val['url'])
            arti_val['path'] = os.path.join(self.artifact_dir, filename)
        self.artifacts_done = os.path.join(self.artifact_dir, '.done')


    def check_exist(self):
        rv = True
        for v in self.artifacts.values():
            if 'path' in v and not os.path.isfile(v['path']):
                rv = False
                break
        if rv and not os.path.isfile(self.artifacts_done):
            rv = False

        return rv


    def download_artifacts(self):
        shutil.rmtree(self.artifact_dir, ignore_errors=True)
        os.makedirs(self.artifact_dir)
        downloader = HttpDownloader(self.auth)
        for v in self.artifacts.values():
            if 'path' in v:
                downloader.download(v['url'], v['path'])
                if 'archive' in v:
                    logger.info("Decompress the archive")
                    unpack_archive(v['path'])
        Path(self.artifacts_done).touch()


    def get_artifacts(self):
        if not self.check_exist():
            self.download_artifacts()
        return self.artifacts


def handle_args(args):
    parser = argparse.ArgumentParser(prog = sys.argv[0], epilog = """\
The kernel_staging script will build the kernel from the branch/tag
named on the commandline.""")
    parser.add_argument(
        '--kernel', '-k', dest='kernel_name', required=True,
        help='Which kernel is going to built')
    parser.add_argument(
        '--soc', '-s', required=True,
        choices=['tgl', 'ehl', 'kmb'],
        help="SoC name, e.g. tgl, ehl")
    parser.add_argument(
        '--staging-revision', '-r', required=True,
        type=str, help='The branch/tag of staging build')
    parser.add_argument(
        '--arch', '-a',
        help='For which ARCH kernel is built')
    parser.add_argument(
        '--kernel-conf', '-c', dest='kconfs', action='append',
        help='Kernel config, e.g. CONFIG_XXX=y')
    parser.add_argument(
        '--cherry-pick', '-p', action='append',
        help='The commit that need to be cherry-picked')
    parser.add_argument(
        '--yocto-artifacts-url', '-u',
        help='All Yocto artifacts url')
    parser.add_argument(
        '--yocto-kconf-url', '-y',
        help='Yocto kernel config file url')
    parser.add_argument(
        '--yocto-initramfs-url', '-m',
        help='Yocto imitramfs url')
    parser.add_argument(
        '--yocto-img-url', '-i',
        help='Yocto build image url')
    parser.add_argument(
        '--log-verbose', '-v', action='store_true',
        help='Log in verbose mode')
    return parser.parse_args()


if __name__ == '__main__':
    assert "WORKSPACE" in os.environ, "No WORKSPACE specified"
    args = handle_args(sys.argv[0])

    loglevel = 'DEBUG' if args.log_verbose else 'INFO'
    logging.basicConfig(level=loglevel, format='%(levelname)-5s: %(message)s')

    kernel = Kernel.objects.get(name=args.kernel_name)
    # calculate the number of parallel jobs per available cpu and mem
    cpu_num = cal_cpu_num()

    kwargs_dict = {
        'kernel': kernel,
        'soc': args.soc,
        'cpu_num': cpu_num,
        'staging_revision': args.staging_revision,
        'yocto_artifacts_url': args.yocto_artifacts_url,
        'workspace': os.environ['WORKSPACE'],
    }
    if args.arch:
        kwargs_dict['arch'] = args.arch

    # load conf from yaml file
    CONF_YAML = "kernel_staging.yaml"
    with open(CONF_YAML, 'r') as y:
        CONF = yaml.safe_load(y)
    conf = CONF['kernel'][args.kernel_name]
    soc_conf = conf.get(args.soc, None)
    def_conf = conf.get('default', None)
    args_conf = {}
    if soc_conf:
        for k, v in soc_conf.items():
            args_conf[k] = v
    if def_conf:
        for k, v in def_conf.items():
            if k not in args_conf:
                args_conf[k] = v
    kwargs_dict['conf'] = args_conf

    # download artifacts and get urls of kconf_path/initramfs_path/yocto_img_url
    artifacts = YoctoArtifacts(**kwargs_dict).get_artifacts()

    # get settings from cmdline/env arguments
    kwargs_dict['kconf_path'] = artifacts['kconf']['path']
    kwargs_dict['initramfs_path'] = artifacts['initramfs']['path']

    # take the kernel config entries from cmd-line arguments
    if args.kconfs:
        if 'kconfigs' in kwargs_dict and kwargs_dict['kconfigs']:
            new_confs = []
            args_kc_dict = { kc.split('=')[0]: True for kc in args.kconfs }
            for kc in kwargs_dict['kconfigs']:
                k = kc.split('=')[0]
                if k not in args_kc_dict:
                    new_confs.append(kc)
            new_confs.extend(args.kconfs)
            kwargs_dict['kconfigs'] = new_confs
        else:
            kwargs_dict['kconfigs'] = args.kconfs

    kb = KernelBuild(**kwargs_dict)
    kb.do_all()

    # save kernel_img/kernel tarball url in the downstream.prop file
    tb_relative_path = kb.get_tarball_path()[len(os.environ['WORKSPACE'])+1:]
    kernel_tarball_url = '/'.join((
        os.environ['BUILD_URL'], 'artifact', tb_relative_path))
    kernel_tarball_url = urldedup(kernel_tarball_url)
    propfl = os.path.join(os.environ['WORKSPACE'], 'downstream.prop')
    with open(propfl, 'w') as pf:
        pf.write("staging_revision=%s\n" % kb.get_staging_revision())
        pf.write("yocto_img_url=%s\n" % artifacts['img']['url'])
        pf.write("kernel_tarball_url=%s\n" % kernel_tarball_url)
