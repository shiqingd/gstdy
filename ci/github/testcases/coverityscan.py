#!/usr/bin/env python3

import os
import sys
import re
import logging
#import tempfile
#import shutil
#import kconfiglib
from lib.utils import cmd
from ci.github.testcases import CITestCase, ARCH_INFO

logger = logging.getLogger(__name__)


class CoverityScan(CITestCase):
    def get_stream(self):
        stream = None
        m = re.search(r'(mainline-tracking|iotg-next)',
                      self.gitdata["github_base_ref"])
        if m:
            stream = m.group(1)
        else:
            kver = self.get_kernelver()
            m = re.search(r'v?(\d\.\d+)([\.-]|$)', kver)
            stream = m.group(1)
        return "%s_%s" % (stream, self.arch)


    def __init__(self, **kwargs):
        #self.cov_host = "coverityent.devtools.intel.com"
        self.cov_host = "coverity.devtools.intel.com"
        #self.cov_port = 443
        self.cov_url = "https://%s/prod7" % self.cov_host
        self.user = "sys_oak"
        self.passwd = os.getenv("SYS_OAK_CRED_COVERITY_API")
        # set coverityscan specific out_dir
        self.out_dir = kwargs.get("out_dir", "cov_out")
        super().__init__(**kwargs)

        # self.out_path, self.kconf are initialized in CITestCase
        self.idir = os.path.join(self.out_path, "cov_idir")
        self.cov_conf_path = os.path.join(self.out_path, "cov_config")
        self.cov_conf = os.path.join(self.cov_conf_path, "coverity_config.xml")
        self.cov_stream = self.get_stream()
        log_base = os.path.join(self.log_path,
                                "cov_desktop_scan_pr_%s_%s" % \
                                  (self.gitdata["github_event_number"],
                                   self.arch))
        self.text_out = "%s.txt" % log_base
        self.json_out = "%s.json" % log_base
        self.result = self.json_out


    # override this method
    def setup(self):
        commands = r"""
            set -x
            rm -rf {out_path}
            mkdir -p {idir}
            mkdir -p {cov_conf_path}
            cov-configure --config {cov_conf} \
                          --compiler {cc} \
                          --comptype gcc \
                          --template
            # Start with a default config
            make O={out_path} {options} {dcfg}
        """.format(out_path=self.out_path,
                   idir=self.idir,
                   cov_conf_path=self.cov_conf_path,
                   cov_conf=self.cov_conf,
                   cc=ARCH_INFO[self.arch]["cc"],
                   options=ARCH_INFO[self.arch]["options"],
                   dcfg=ARCH_INFO[self.arch]["dcfg"])
        cmd(commands, exit_on_fail=True)


    def execute(self):
        os.chdir(self.build_path)
        self.setup()
        self.merge_chgcfgs()
        commands = r"""
            set -x
            yes "" | \
              cov-build \
                --dir {idir} \
                --config {cov_conf} \
                --record-with-source \
                --parallel-translate={cpus_per_job} \
                make O={out_path} {options} -j{cpus_per_job}
            cov-run-desktop \
                --user {user} \
                --password {passwd} \
                --dir {idir} \
                --url {cov_url} \
                --stream {cov_stream} \
                --disable-parse-warnings \
                --ignore-uncapturable-inputs true \
                --strip-path $(pwd)/ \
                --text-output {text_out} \
                --text-output-style oneline \
                --json-output-v7 {json_out} \
                --set-new-defect-owner false \
                {changed_files}
        """.format(idir=self.idir,
                   user=self.user,
                   passwd=self.passwd,
                   cov_conf=self.cov_conf,
                   cpus_per_job=self.cpus_per_job,
                   options=ARCH_INFO[self.arch]["options"],
                   out_path=self.out_path,
                   cov_url=self.cov_url,
                   cov_stream=self.cov_stream,
                   text_out=self.text_out,
                   json_out=self.json_out,
                   changed_files=' '.join(self.gitdata['files']['c']))
        cmd(commands, exit_on_fail=True)
