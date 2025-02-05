#!/usr/bin/env python3

import os
import sys
import json
import logging
import shutil
import tempfile
from lib.utils import cmd_pipe, cmd, ShCmdError, sed_inplace
from lib.config_finder import ConfigDependencyFinder

logger = logging.getLogger(__name__)


ARCH_INFO = {
    "x86_64": {
        "arch_s": "x86",
        "cc": "gcc",
        "options": "ARCH=x86_64",
        "dcfg": "x86_64_defconfig",
    },
    "arm64": {
        "arch_s": "arm64",
        "cc": "aarch64-linux-gnu-gcc",
        "options": "ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-",
        "dcfg": "defconfig",
    },
}


class CITestCase():
    def __init__(self, **kwargs):
        self.result = None
        # inherited from CI framework
        self.workspace = os.environ.get("WORKSPACE")
        self.log_dir = os.environ.get("LOG_DIR", "logs")
        self.build_dir = os.environ.get("BUILD_DIR", "build")
        self.chkpatch_dir = os.environ.get("CHKPATCH_DIR", "chkpatches")
        self.cpus_per_job = int(os.environ.get("CPUS_PER_JOB", "16"))

        gitdata_json = os.environ.get("GITDATA_JSON", "gitdata.json")
        commit_log = os.environ.get("COMMIT_LOG", "commit.log")

        # get parameters from cmd-line
        self.arch = kwargs.get("arch") if kwargs.get("arch") else "x86_64"
        if not self.out_dir:
            self.out_dir = kwargs.get("out_dir") \
                             if kwargs.get("out_dir") else "out"

        assert self.workspace
        self.log_path = os.path.join(self.workspace, self.log_dir)
        self.build_path = os.path.join(self.workspace, self.build_dir)
        self.commit_log = os.path.join(self.build_path, commit_log)
        self.out_path = os.path.join(self.build_path, self.out_dir)
        self.kconf  = os.path.join(self.out_path, ".config")
        # see json schema of gitdata in kernel-staging/githubci.jf
        with open(os.path.join(self.build_path, gitdata_json), 'r') as j:
            self.gitdata = json.load(j)


    @classmethod
    def find_configs(cls, arch, cfg_path, files_changed):
        cfg_deps = set()
        finder = ConfigDependencyFinder(target_arch=ARCH_INFO[arch]["arch_s"],
                                        cfg_path=cfg_path)
        for filename in files_changed:
            cfg = finder.Makefile_dependency(filename)
            if cfg:
                try:
                    kdeps = finder.Kconfig_dependencies(cfg)
                    cfg_deps.add(cfg)
                    cfg_deps |= kdeps
                except ValueError as e:
                    # Don't add the config it an exception is raised
                    logger.error(e)

        cfg_deps = sorted(cfg_deps)
        return cfg_deps


    def setup(self):
        commands = r"""
            set -x
            rm -rf {out_path}
            mkdir -p {out_path}
            # start with a default config
            make O={out_path} {options} {dcfg}
        """.format(out_path=self.out_path,
                   options=ARCH_INFO[self.arch]["options"],
                   dcfg=ARCH_INFO[self.arch]["dcfg"])
        cmd(commands, exit_on_fail=True)


    def get_kernelver(self):
        rc, out, err = cmd_pipe("make kernelversion")
        if rc != 0:
            raise ShCmdError("make kernelversion failed: %s" % err)
        return out


    def merge_chgcfgs(self):
        # find the related kernel config by changed c files
        chgcfgs = CITestCase.find_configs(self.arch,
                                          self.kconf,
                                          self.gitdata['files']['c'])
        logger.debug("Detect related configs: %s" % chgcfgs)
        chgcfg_tmpfl = os.path.join(tempfile.gettempdir(),
                                    "chgconfig.%i" % os.getpid())
        with open(chgcfg_tmpfl, 'w') as f:
            for c in chgcfgs:
                f.write("CONFIG_%s=y\n" % c)
            f.write("CONFIG_RETPOLINE=n\n")

        command = "./scripts/kconfig/merge_config.sh -O %s %s %s" % \
                    (self.out_path, self.kconf, chgcfg_tmpfl)
        cmd(command, exit_on_fail=True)


    def execute(self):
        os.chdir(self.build_path)
        self.setup()
        self.merge_chgcfgs()


    def parse_log(self):
        pass


    def check_result(self):
        pass
