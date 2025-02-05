#!/usr/bin/env python3
#
#

import sys
import os
import sh
import traceback
import re
import argparse
import time
import logging
from autologging import TRACE

HOST = "cov.ostc.intel.com"
USERNAME = 'sys_pkt'
PASSWORD = os.environ.get('SYS_PKT_CRED_AD')
BUILD_DIR="./build"
COV_PATH='/opt/cov-analysis-linux64-2018.06/bin'


class CovAnalyze():
    cov_config_file = 'coverity_config.xml'
    cov_stream = ''
    compiler = 'gcc'
    code_tag = ''
    nproc = 16

    def __init__(self,cov_info):
        self.cov_tmp_base_dir = "./cov_tmp_base"
        self.cov_report_base_dir = "./cov_report_base"
        self.cov_tmp_dir = "./cov_tmp"
        self.cov_report_dir = "./cov_report"

        self.nproc = sh.Command('/usr/bin/nproc')().stdout.decode().strip()

        self.__log = logging.getLogger(sys.argv[0] != '' and sys.argv[0] or '<console>')
        self.__log.setLevel(TRACE)
        formatter = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s', '%m/%d/%Y %H:%M:%S')
        formatter_nl = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s\n', '%m/%d/%Y %H:%M:%S')
        if "cov_host" in cov_info.keys():
            self.host = cov_info["cov_host"]
        else:
            self.host = HOST

        if "cov_username" in cov_info.keys():
            self.username = cov_info["cov_username"]
        else:
            self.username = USERNAME

        if "cov_pwd" in cov_info.keys():
            self.password = cov_info["cov_pwd"]
        else:
            self.password = PASSWORD

        if not "LOGFILE" in os.environ:
            # create file handler that logs debug and higher level messages
            ch = logging.StreamHandler(stream=sys.stdout)
            ch.setLevel(logging.DEBUG)
            ch.terminator = ''
            ch.setLevel(TRACE)
            ch.setFormatter(formatter_nl)
            self.__log.addHandler(ch)
        else:
            # create formatter and add it to the handlers
            # add the handlers to logger
            fh = logging.FileHandler(os.environ["LOGFILE"])
            fh.setLevel(TRACE)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            self.__log.addHandler(fh)
        self.__log.propagate = False

    #check the analyze bin file.
    def try_shell_command(self,command, args):
        cmd = command(args, _bg=True , _out=self.__log.info, _err=self.__log.error)
        self.__log.info(cmd.cmd)
        cmd.wait()
        self.__log.info("%s returns %d" , cmd.cmd[0], cmd.exit_code)
        if cmd.exit_code != 0:
            raise Exception("%s returns %d" % (cmd.cmd[0], cmd.exit_code))

    def preparecode(self, branch = None, tag = None):
        self.__log.info("Prepare Scan code")
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "clean", "-xdf"])
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", "master" ] )
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "pull" ] )
        if tag != None:
            self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", tag ] )
            self.code_tag = tag
        if branch != None:
            self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", branch ] )
            self.code_tag = branch

    def preparebaselinecode(self, branch = None, tag = None):
        self.__log.info("Prepease Baseline Scan")
        cmd =sh.Command('/usr/bin/git')([ "show-ref", branch], _err=print).wait()
        if cmd.exit_code != 0:
            self.__log.error(output.exit_code+'='+output.stderr.decode())
            return None
        else:
            refinfo = cmd.stdout.decode().strip().split()
            commits_on_tag = sh.Command('/usr/bin/git').describe([ refinfo[1] ], _err=print).wait().stdout.decode().strip()
            recent_tag = re.sub(r'(v[0-9]\.[0-9]{1,2}(?:-rc[0-9]{1,2}){0,1}).*', r'\1',  commits_on_tag)

        self.try_shell_command(sh.Command('/usr/bin/git'), [ "clean", "-xdf","--exclude=report*"])
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", "master" ] )
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "pull" ] )
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", recent_tag ])
        self.code_tag = recent_tag

    def covgetneweststream(self, version ):
        cov_manage_get_args1 =["--host", self.host ] \
                + ["--user" , self.username] \
                + ["--password", self.password ] \
                + ["--mode", "streams","--name", version ] \
                + ["--show" ]\
                + ["--fields", "stream"]

        try:
            cmd = sh.Command("cov-manage-im")(cov_manage_get_args1)
        except sh.ErrorReturnCode_1:
            return 0
        result = cmd.stdout.decode().strip()
        result = result.split('\n', )
        if len(result) >1 :
            streams = result[1:]
        else:
            return 0
        self.__log.info(streams)

        return  streams[-1]

    def covgetstream(self, stream_name ):
        cov_manage_get_args1 =["--host", self.host ] \
                + ["--user" , self.username ] \
                + ["--password", self.password ] \
                + ["--mode", "streams"] \
                + ["--show","--name", stream_name ]

        try:
            cmd = sh.Command("cov-manage-im")(cov_manage_get_args1)
        except sh.ErrorReturnCode_1:
            return 0
        result = cmd.stdout.decode().strip()
        self.__log.info(result)
        return  re.search(stream_name,result, re.IGNORECASE)

    def covcreatestream(self, stream_name, project_name ):
        cov_manage_create_args1 =["--host", self.host ] \
                + ["--user" , self.username] \
                + ["--password", self.password ] \
                + ["--mode", "streams"] \
                + ["--add","--set","name:"+stream_name ]

        cov_manage_create_args2 =["--host", self.host ] \
                + ["--user" , self.username] \
                + ["--password", self.password ] \
                + ["--mode", "projects"] \
                + ["--update","--name",project_name ] \
                + ["--insert", "stream:"+stream_name]

        self.try_shell_command(sh.Command("cov-manage-im"), cov_manage_create_args1)
        self.try_shell_command(sh.Command("cov-manage-im"), cov_manage_create_args2)

    def covdefectreport(self,stream_name, cov_tem_dir, report_name):
        cov_commit_args1 = ["--dir",cov_tem_dir ] \
                + ["--ticker-mode", "none"] \
                + ["--host", self.host ] \
                + ["--user" , self.username ] \
                + ["--password", self.password ] \
                + ["--preview-report-v2", report_name ] \
                + ["--stream", stream_name ] \

        self.try_shell_command(sh.Command("cov-commit-defects"), cov_commit_args1)

    def covcommitdefect(self,stream_name, snapshot_id_file, cov_tem_dir, describe):
        cov_commit_args1 = ["--dir",cov_tem_dir ] \
                + ["--ticker-mode", "none"] \
                + ["--host", self.host ] \
                + ["--user" , self.username ] \
                + ["--password", self.password ] \
                + ["--stream", stream_name ] \
                + ["--description", describe ] \
                + ["--snapshot-id-file", snapshot_id_file]

        self.try_shell_command(sh.Command("cov-commit-defects"), cov_commit_args1)


    def covconfigure(self, compiler, cov_tem_dir, cov_config_file="coverity_config.xml"):
        self.cov_config_file = cov_tem_dir+"/"+cov_config_file
        self.compiler = '--'+compiler
        self.try_shell_command(sh.Command("cov-configure"), ["--config", self.cov_config_file, self.compiler])

    def makeconfig(self, make_cmd):
        make_cmd = make_cmd.split(' ', )
        self.try_shell_command(sh.Command(make_cmd[0]),make_cmd[1:])

    def covbuild(self, tmp_dir, build_cmd):
        build_cmd=build_cmd.split(' ', )
        cov_build_args_1 = [ "--dir",  tmp_dir ] \
                + [ "--config",  self.cov_config_file ]\
                + [ "--record-with-source" ]\
                + [ "--return-emit-failures" ]\
                + [ "--parallel-translate="+self.nproc ]\
                + build_cmd\
                + [ "-j", self.nproc ]

        cov_build_args_2 = [ "--dir",  tmp_dir ] \
                + [ "--config",  self.cov_config_file ] \
                + [ "--replay-from-emit" ] \
                + [ "-j", self.nproc]

        self.try_shell_command(sh.Command("cov-build"), cov_build_args_1)
        self.try_shell_command(sh.Command("cov-build"), cov_build_args_2)

    def covanalyze(self,tmp_dir):
        cov_analyze_args = [ "--dir",  tmp_dir ] \
                + [ "--strip-path", os.getcwd() + '/' ] \
                + [ "--all" ] \
                + [ "--aggressiveness-level", "high" ] \
                + [ "--enable", "ENUM_AS_BOOLEAN" ] \
                + [ "--enable", "HFA" ] \
                + [ "--enable", "PARSE_ERROR" ] \
                + [ "--enable", "STACK_USE" ] \
                + [ "--enable", "USER_POINTER" ] \
                + [ "-j",self.nproc ]
        self.try_shell_command(sh.Command("cov-analyze"), cov_analyze_args)

    def covformaterrors(self,report_dir, tmp_dir, include_files ):
        cov_format_errors_args = [ "--dir", tmp_dir ]\
                + [ "--html-output", report_dir ] \
                + [ "--include-files", include_files ]
        self.try_shell_command(sh.Command("cov-format-errors"), cov_format_errors_args)

    def cov_scan(self, build_cmd, branch, include_file,Compare = False):
        #get the baseline to scan
        self.__log.info("cov_scan")
        self.__log.info(Compare)
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", "master" ] )
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "pull", "-r"] )
        cmd =sh.Command('/usr/bin/git')([ "show-ref", branch], _err=print).wait()
        if cmd.exit_code != 0:
            self.__log.error(output.exit_code+'='+output.stderr.decode())
            return None
        else:
            refinfo = cmd.stdout.decode().strip().split()
            commits_on_tag = sh.Command('/usr/bin/git').describe([ refinfo[1] ], _err=print).wait().stdout.decode().strip()
            recent_tag = re.sub(r'(v[0-9]\.[0-9]{1,2}(?:-rc[0-9]{1,2}){0,1}).*', r'\1',  commits_on_tag)
        self.code_tag = recent_tag
        self.cov_stream = "coe_"+commits_on_tag
        self.__log.info("commits_on_tag"+self.cov_stream)
        branch_tag = branch.replace('/','_')
        self.branch_tag = branch_tag +'_' + commits_on_tag
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "clean", "-xdf"])

        if not self.covgetstream(self.cov_stream):
            self.covcreatestream(self.cov_stream, "COE_TEST")
        if Compare == "True":
            self.__log.info("Prepease Baseline Scan")
            self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", recent_tag ])
            self.covconfigure("gcc",self.cov_tmp_base_dir)
            self.makeconfig("make O=./build ARCH=x86_64 x86_64_defconfig")
            self.covbuild(self.cov_tmp_base_dir, build_cmd)
            self.covanalyze(self.cov_tmp_base_dir)
            self.covformaterrors(self.cov_report_base_dir,self.cov_tmp_base_dir,include_file)
            self.covcommitdefect(self.cov_stream, "./snapshot_id_base", self.cov_tmp_base_dir, "base for "+self.branch_tag)

        self.__log.info("Prepare Scan code")
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "clean", "-xdf", "--exclude", "cov*"])
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", branch ] )
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "pull", "-r"] )

        self.covconfigure("gcc",self.cov_tmp_dir)
        self.makeconfig("make O=./build ARCH=x86_64 x86_64_defconfig")
        self.covbuild(self.cov_tmp_dir, build_cmd)
        self.covanalyze(self.cov_tmp_dir)
        self.covformaterrors(self.cov_report_dir,self.cov_tmp_dir,include_file)
        self.covcommitdefect(self.cov_stream, "./snapshot_id", self.cov_tmp_dir, self.branch_tag)
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "checkout", "master" ] )
        self.try_shell_command(sh.Command('/usr/bin/git'), [ "branch", "-D", branch ] )

