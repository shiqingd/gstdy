#!/usr/bin/env python3
#
#

import sys
import os
import sh
import re
import argparse
import time
import logging
import json
import xmlrpc.client
from autologging import TRACE
from collections import OrderedDict

class CheckPatch:
    # please run it in root kernel path
    #tools = "./kernel-coe-tracker/scripts/checkpatch.pl --ignore GERRIT_CHANGE_ID"
    checkresult = {}
    log = ''

    def __init__(self,tools,config):
        self.log = logging.getLogger(sys.argv[0] != '' and sys.argv[0] or '<console>')
        self.log.setLevel(TRACE)
        formatter = logging.Formatter( '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s', '%m/%d/%Y %H:%M:%S')
        ch = logging.StreamHandler(stream=sys.stdout)
        self.log.addHandler(ch)
        #self.tools = tools+ " --no-signoff --ignore GERRIT_CHANGE_ID"
        self.tools = tools+ ' ' + config
    def checkindir(self, dirname):
        result_log = ''
        result = 0
        patches = 0
        report = OrderedDict()
        report_detail = OrderedDict()
        try:
            patchfiles = os.listdir(dirname)
            for pfile in patchfiles:
                out = os.popen(self.tools+" "+ dirname+'/'+pfile).readlines()
                status = OrderedDict()
                out_summary = ""
                patches +=1
                status["PatchName"] = pfile[5:]

                status["Result"] = "good"
                for line in out:
                    self.log.info(line)
                    if re.search("WARNING|ERROR" , line):
                        self.log.info(pfile +" is bad patch")
                        status["Result"] = "fail"
                    if re.search("total" , line):
                        out_summary = line
                if status["Result"] == "fail":
                    result += 1
                status["Log"] = out
                #result_log += pfile[5:] +': ' + out_summary
                report_detail[pfile[5:]] = status
        except Exception as e:
            result = -1
            result_log = "the checkpatch tools error, please ask for admin"

        report = OrderedDict()
        report["name"] = "checkpatch"
        if result == 0:
            report["result"] = "pass"
        elif result == -1:
            report["result"] = "block"
        else:
            report["result"] = "fail"
        report["log"] = "Find %s commits have checkpatch error in total %s commits checked." %(result,patches)

        fd = open('./checkpatch_result.json', "w")
        fd.write(json.dumps(report_detail,indent=4))
        fd.close()

        return  report

    def check(self, commit_list):
        checkstatus = {}
        for commit in commit_list:
            patchfile = sh.Command("git")(["format-patch","-1",commit]).wait()
            patchfile = patchfile.stdout.decode()
            out = os.popen(self.tools+" "+ str(patchfile)).read()

            if re.search("WARNING|ERROR" , out):
                self.log.info(patchfile +" is bad patch")
                self.log.info("-----------------------output-------------------------")
                self.log.info(out)
                self.log.info("----------------------end-output----------------------")
                result = "bad"
            else:
                self.log.info(patchfile +" is good patch")
                result = "good"

            checkstatus["Name"] = patchfile
            checkstatus["Result"] = result
            checkstatus["Log"] = out
            self.checkresult[commit] = checkstatus


def main(argv):

    #server = 'http://localhost:8000'
    #patch_file = './patch.json'
    # /home/hongli/MyWork/metronome/dev_branch/test/pk_qa-coverity/pathes/
    test = CheckPatch()

    test.checkindir("/home/hongli/MyWork/metronome/dev_branch/test/pk_qa-coverity/pathes")
"""
    server = argv[0]
    quilt_file = argv[1]
    new_patch_id = {}
    revised_patch_id = {}

    test = CheckPatch()
    test.log.info(server)
    test.log.info(quilt_file)

    s = xmlrpc.client.ServerProxy(server)
    quilt_json =s.transfer(quilt_file)

    quilt_dic = json.loads(quilt_json)

    change = quilt_dic["changes"]
    change_list = change.keys()

    test.log.info(change_list)
    for ll in change_list:
        test.log.info("list "+ll)
        if ll == 'new':
            new_patch_id = change['new'].keys()
        if ll == 'revised':
            revised_patch_id = change['revised'].keys()
    if new_patch_id:
        test.check(new_patch_id)
    if revised_patch_id:
        test.check(revised_id)

    test.log.info(new_patch_id)
    test.log.info(revised_patch_id)
    fd = open("./checkresult.json","w")
    tmp_result = json.dumps(test.checkresult)
    fd.write(tmp_result)
    fd.close()
"""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


