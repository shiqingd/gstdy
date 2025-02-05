#!/usr/bin/env python3
import sys
import os
import argparse
import re
import logging
import shutil
import json
from pathlib import Path
if not "DJANGO_SETTINGS_MODULE" in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
    import django
    django.setup()

from django.core.exceptions import ObjectDoesNotExist

from framework.models import *

from lib.download import HttpDownloader
from lib.jenkins import (
	JenkinsArtifactFinder,
#    get_artifact_list,
    get_build_list,
    get_lastpassed_build_number,
    get_last_good_build_by_param
)
from lib.pushd import pushd
from lib.utils import (
    get_sha_last_commit,
    is_branch,
    cmd,
    cal_cpu_num,
    get_kernel_baseline,
    make_tarfile
)
from lib.dry_run import traceable_method

logger = logging.getLogger(__name__)


class KernelBuild:
    def __init__(self, **kwargs):
        # variables passed from cmdline or build env.
        self.kernel = kwargs.get('kernel')
        self.platform = kwargs.get('platform')
        self.staging_revision = kwargs.get('staging_revision').lstrip(r'origin/')
        self.arch = self.platform.architecture

        self.cpu_num = kwargs.get('cpu_num')
        self.build_number = kwargs.get('build_number')
        self.config_path = kwargs.get('config_path')
        self.initramfs_path = kwargs.get('initramfs_path')
        self.kconfigs = kwargs.get('kconfigs')
        if not self.kconfigs:
            self.kconfigs = []

        self.top_build_dir = os.path.join(os.environ["WORKSPACE"], 'kernel_build')
        self.build_timestamp = self.staging_revision.split('-')[-1]
        self.out_dir = os.path.join(self.top_build_dir, 'out')
        self.krepo = KernelRepoSet.objects.get(repo__repotype__repotype='src',
                                               repo__external=False,
                                               kernel_id=self.kernel.id)
        self.repo_url = self.krepo.repo.url()
        self._git = sh.Command("/usr/bin/git")

    def get_staging_revision(self):
        return self.staging_revision


    def get_tarball_path(self):
        return self.tarball_path


    def prepare_repo(self):
        # initialize the kernel repo.
        logger.info("Initialize or sync kernel repo: %s" % self.repo_url)
        try:
            # FIXME - for time savings, probably better to
            # test if existing worktree is compatible,
            # but removing old worktree ensures a clean cloned worktree
            # in case previous run was from another repo
            shutil.rmtree(self.top_build_dir, ignore_errors=True)
        except Exception as e:
            print("ERROR: Cannot remove", self.top_build_dir, ":", e)
            sys.exit(1)
        self.krepo.repo.initialize(scmdir=self.top_build_dir)
        ref = self.staging_revision
        if is_branch(self.repo_url, ref):
            try:
                cmd = traceable_method(self._git, "branch", "-D", ref)
            except:
                # Assume the branch doesn't exist
                pass
        with pushd(self.top_build_dir):
            # checkout kernel repo to the specified branch/tag
            traceable_method(self._git, "checkout" , ref)
            # get sha1 of the specified staging_revision
            self.kernel_sha1 = get_sha_last_commit('.')
            # get baseline kernel version
            self.baseline = get_kernel_baseline(self.kernel_sha1)[0]
            logger.info("Staging revision: %s (baseline: %s)" % \
                          (self.kernel_sha1, self.baseline))
        # compose the dest tarball name
        self.tarball_name = "kernel-%s-%s-%s.tar.bz2" % \
                              (self.platform.name, self.baseline, self.build_timestamp)
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
        if self.config_path != dest_config:
            shutil.copy(self.config_path, dest_config)
        KernelBuild._set_kconfigs(dest_config, self.kconfigs)


    def makeup_kconfigs(self):
        # the configs for LTP-DDT
        ddt_kcfgs = [
            ('CONFIG_THUNDERBOLT', 'y'),
            ('CONFIG_X86_INTEL_CET', 'y'),
            ('CONFIG_CRYPTO_AES_KL_INTEL', 'm'),
            ('CONFIG_X86_INTEL_RAR', 'y'),
            ('CONFIG_TCG_CRB', 'y'),
            ('CONFIG_TCG_TPM', 'y'),
            ('GPIO_MOCKUP', 'm'),
            ('CONFIG_QFMT_V2', 'y'),
        ]
        # the configs for Yocto build
        kcfgs = [
            ('CONFIG_LOCALVERSION', '"-IKT-OSIT-%s"' % self.build_timestamp),
            ('CONFIG_INITRAMFS_SOURCE', '"%s"' % self.initramfs_path),
            ('CONFIG_EXTRA_FIRMWARE', '""'),
            ('CONFIG_EXTRA_FIRMWARE_DIR', '""'),
        ]
        self.kconfigs.extend(kcfgs)
        self.kconfigs.extend(ddt_kcfgs)


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
        logger.info("Try to remove previous build dir: %s" % self.top_build_dir)
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
    def __init__(self, kernel, platform, build_number=None):
        self.kernel = kernel
        self.platform = platform
        try:
            self.yoctojob = JenkinsJob.objects.get(jobname__regex = r'lts\d+_build_yocto_', kernel=kernel, flags = 1)
        except Exception as e:
            print(e)
            print(f"Please check the database at {os.environ['DATABASE_HOST']} for an entry matching the upstream Jenkins job that triggered this job")
            sys.exit(1)
        url = self.yoctojob.host.url
        if build_number is None:
            build_number = get_last_good_build_by_param(url, self.yoctojob.jobname, 'PLATFORM', self.platform.name)
        # KLUDGE - hacks to allow use of old, obsolete yocto_staging.py script
        # KLUDGE - yocto_staging.py will NOT be supported in consolidated jobs
        if build_number is None:
            build_number = get_last_good_build_by_param(url, self.yoctojob.jobname, 'PROJECT', self.platform.name)
        if build_number is None:
            build_number = get_last_good_build_by_param(url, self.yoctojob.jobname, 'PROJECT', self.platform.name+'-rt')
        # KLUDGE
        if build_number is None:
            raise ValueError("No Successful build was found for platform {} in job {}".format(platform.name, self.yoctojob.jobname))
        self.build_number = build_number
        self.finder = JenkinsArtifactFinder()
        self.finder.get_artifact_list(self.yoctojob.host.url, self.yoctojob.jobname, self.build_number)
        artifacts = self.finder.artifacts
        self.build_number = str(self.build_number)
        self.artifact_dir = os.path.join(os.environ["WORKSPACE"], 'artifacts', self.build_number)
        self.artifact_url = self.finder.source_url

        self.artifacts = {}
        self.local_artifacts = {}
        print('\n'.join(a for a in artifacts))
        for a in artifacts:
            if re.search(r'/config-', a):
                self.artifacts['config'] = f"{self.artifact_url}/{a}"
                self.local_artifacts['config'] = os.path.join(
                  self.artifact_dir, a.split('/')[-1])
            elif re.search(r'mender-initramfs.+[0-9]{14}.*\.cpio', a):
                self.artifacts['initramfs'] = f"{self.artifact_url}/{a}"
                self.local_artifacts['initramfs'] = os.path.join(
                  self.artifact_dir, a.split('/')[-1])
            elif re.search(r'intel-corei7-64.wic.bz2', a):
                self.artifacts['osimage_url'] = f"{self.artifact_url}/{a}"
        self.local_artifacts['done'] = os.path.join( self.artifact_dir, '.done')
        print(json.dumps(self.artifacts, indent=4))
        print(json.dumps(self.local_artifacts, indent=4))


    def check_exist(self):
        rv = True
        for f in self.local_artifacts.values():
            if not os.path.isfile(f):
                rv = False
                break
        return rv


    def download_artifacts(self):
        shutil.rmtree(self.artifact_dir, ignore_errors=True)
        os.makedirs(self.artifact_dir)
        if 'artifactory' in self.finder.source_url:
            downloader = HttpDownloader(headers = { "Accept" : "application/json" , "X-JFrog-Art-Api" : os.environ["SYS_OAK_CRED_ARTIFACTORY_API"]})
        else:
            downloader = HttpDownloader(auth = ('sys_oak', os.environ['SYS_OAK_CRED_JENKINS_API']))

        for f in ('config', 'initramfs',):
            downloader.download(self.artifacts[f], self.local_artifacts[f])
        Path(self.local_artifacts['done']).touch()


    def get_artifacts(self):
        if not self.check_exist():
            self.download_artifacts()
        return {
            'config': self.local_artifacts['config'],
            'initramfs': self.local_artifacts['initramfs'],
            'osimage_url': self.artifacts['osimage_url']
        }


def handle_args(args):
    parser = argparse.ArgumentParser(prog = sys.argv[0], epilog = """\
The osit_staging script will build the kernel from the branch/tag
named on the commandline.""")
    parser.add_argument(
        '--kernel', '-k', dest='kernel_name', required=True, type=Kernel.validate,
        help='Which kernel is going to built:'+Kernel.list())
    parser.add_argument(
        '--soc', '-s', dest='soc', required=True, type=Platform.validate,
        help="SoC name: "+Platform.list())
    parser.add_argument(
        '--staging-revision', '-r', dest='staging_revision', required=True,
        type=str, help='The branch/tag of staging build')
    parser.add_argument(
        '--kernel-conf', '-c', dest='kconf', type=str,
        help='Kernel config file path')
    parser.add_argument(
        '--yocto-buildno', '-b', dest='yocto_buildno', type=int,
        help='The referenced yocto build number')
    parser.add_argument(
        '--log-verbose', '-v', action='store_true', help='Log in verbose mode')
    return parser.parse_args()


if __name__ == '__main__':
    assert("WORKSPACE" in os.environ)
    args = handle_args(sys.argv[0])

    loglevel = 'DEBUG' if args.log_verbose else 'INFO'
    logging.basicConfig(level=loglevel, format='%(levelname)-5s: %(message)s')

    kernel = Kernel.objects.get(name=args.kernel_name)
    platform = Platform.objects.get(name=args.soc)
    # calculate the number of parallel jobs per available cpu and mem
    cpu_num = cal_cpu_num()

    # download artifacts and get urls of config_path/initramfs_path/osimage_url
    artifacts = YoctoArtifacts(kernel, platform, args.yocto_buildno).get_artifacts()

    # get settings from cmdline/env arguments
    kwargs_dict = {
        'kernel': kernel,
        'platform': platform,
        'staging_revision': args.staging_revision,
        'build_number': os.environ['BUILD_NUMBER'],
        'cpu_num': cpu_num,
        'config_path': artifacts['config'],
        'initramfs_path': artifacts['initramfs'],
    }

    # take the kernel config entries from the specified kernel config file
    if args.kconf:
        with open(args.kconf, 'r') as kc:
            kc_text = kc.read()

        extra_kcfg = []
        rep = re.compile(r'^\s*([^#].*)\s*=\s*(.*)\s*$')
        for c in kc_text.splitlines():
            m = rep.match(c)
            if m:
                extra_kcfg.append((m.group(1), m.group(2),))
        if extra_kcfg:
            kwargs_dict['kconfigs'] = extra_kcfg

    kb = KernelBuild(**kwargs_dict)
    kb.do_all()

    # save osimage/kernel tarball url in the downstream.prop file
    tb_relative_path = kb.get_tarball_path()[len(os.environ['WORKSPACE'])+1:]
    kernel_tarball_url = os.path.join(
        os.environ['BUILD_URL'], 'artifact', tb_relative_path)
    propfl = os.path.join(os.environ['WORKSPACE'], 'downstream.prop')
    with open(propfl, 'w') as pf:
        pf.write("OSIMAGE_URL=%s\n" % artifacts['osimage_url'])
        pf.write("KERNEL_TARBALL_URL=%s\n" % kernel_tarball_url)
        # required by the downstream job: CVE_BDBA_Auto-Scan_BJ
        pf.write("image_url=%s\n" % kernel_tarball_url)
        pf.write("STAGING_REVISION=%s\n" % kb.get_staging_revision())
