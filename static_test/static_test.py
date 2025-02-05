#!/usr/bin/python

import os
import sh
import re
import sys
import logging as log
import getopt
import json
import prepare_code
import compile_test
import cov_test
import banned_words_check
from checkpatch import CheckPatch
from Git import Git
from collections import OrderedDict

prj_root = os.path.dirname(os.path.abspath(__file__))
jenscript_dir = os.path.join(prj_root, "../../jenkins-scripts")
sys.path.insert(0, jenscript_dir)

import metronome_client

def console_out(logFilename):
    ''' Output log to file and console '''
    # Define a Handler and set a format which output to file
    log.basicConfig(
                    level    = log.DEBUG,
                    format   = '%(message)s',
                    datefmt  = '%Y-%m-%d %A %H:%M:%S',
                    filename = logFilename,
                    filemode = 'w')

    # Define a Handler and set a format which output to console
    console = log.StreamHandler()
    console.setLevel(log.INFO)
    formatter = log.Formatter('%(message)s')
    console.setFormatter(formatter)
    # Create an instance
    log.getLogger().addHandler(console)


def static_loginit(testname,url):
    report = OrderedDict()
    #{"name": "xxx", "result": "fail|pass|block", "log": "", "url": ""}
    report['name'] = testname
    report["result"] = "unknow"
    report["log"] = testname + " has not start!\n"
    report["url"] = url
    return report

def main(argv):
    console_out('logging.log')
    build_url = ''
    job_id = ''
    job_name = ''
    system_info = ''
    check_items = ''
    collect_server = ''
    kernel_test_repo = ''
    kernel_patch_list = ''
    kernel_test_branch = ''
    kernel_code_location = ''
    cov_project = ''
    download_auto = True
    result_report = OrderedDict()
    details_log = []
    result = 0 # 0 means pass, !0 means fail
    report = os.getcwd()+'/result_report.json'
    try:
        opts, args = getopt.getopt(argv,"hp:i:d:u:s:c:k:n:")
    except getopt.GetoptError:
        log.info("get the input parameter error ")
        sys.exit(2)

    for opt, arg in opts:
      if opt == '-h':
         log.info("\n\
            Please input the paramter, ep: \n\
            python3 staic_check.py -p '\"36415/1\"' -i\"https://\" -k def_system_config.json  \n\
            -p : the patch in gerrit to be merge \n\
            -d : the kernel folder dir, if input the folder dir, not download the code, directly compile \n\
            -u : the jenkins build url \n\
            -i : job id \n\
            -s : result collect server \n\
            -c : coverity scan compare project \n\
            -n : jenkins job \n\
            -k : the system config paremeter it should be a json file \n\
                 please refer the def_system_config.json \n\
            -h : help")
         sys.exit()
      elif opt == "-p":
          kernel_patch_list = eval(arg)
      elif opt == "-d":
          kernel_code_location=arg
          download_auto = False
      elif opt == "-u":
          build_url = arg
      elif opt == "-i":
          job_id = arg
      elif opt == "-s":
          collect_server = arg
      elif opt == "-c":
          cov_project = arg
      elif opt == "-n":
          job_name = arg
      elif opt == "-k":
          files = open(arg,'r')
          system_info = json.loads(files.read())
          files.close()
      else:
          log.info("unknow the input parameter")

    log.info(system_info)
    if system_info != '':
        check_items = system_info['check_items'].split(',',)
        make_info = system_info['compile_config']
        kernel_test_repo = make_info['kernel_repo']
        kernel_test_branch = make_info['kernel_branch']
        checkpatch_info = system_info['checkpatch_config']
        cov_info = system_info["coverity_config"]
        summary_items = system_info["summary_items"]

    log.info( make_info )
    log.info( check_items )

    log.info("kernel_test_repo="+kernel_test_repo)
    log.info("kernel_patch_list=")
    log.info(kernel_patch_list)
    log.info("kernel_test_branch="+kernel_test_branch)
    log.info("kernel_code_location="+kernel_code_location)
    log.info("build_url="+ build_url )

    getcode_result = static_loginit("getcode",build_url)
    banned_result = static_loginit("bannedwords",build_url)
    ckpatch_result = static_loginit("checkpatch.pl",build_url)
    coverity_result = static_loginit("coverity_scan",build_url)
    compile_result = static_loginit("compile",build_url)



    #first report to core
	#send(SERVER, args.result, args.job_id, args.msg, args.vendor, data)
    data1 = dict()
    msg_rpt1 = "static test has start on:"+ build_url
    data1["msg"] = msg_rpt1
    metronome_client.send(collect_server, 'pass',job_id, msg_rpt1, "Jenkins", data1)

    #prepare code
    if kernel_code_location == '':
        if kernel_test_branch == '':
            kernel_test_branch = "master"
        #removn the space
        kernel_test_repo = re.sub(r"^(\s+)|(\s+)$", "", kernel_test_repo)
        kernel_test_branch = re.sub(r"^(\s+)|(\s+)$", "", kernel_test_branch)

        if kernel_patch_list == '':
            out = prepare_code.getcode(kernel_test_repo, kernel_test_branch)
        else:
            out = prepare_code.getcode(kernel_test_repo, kernel_test_branch,kernel_patch_list)

        if out != -1:
            kernel_code_location = os.path.abspath(out)
            getcode_result["result"] = "pass"
            getcode_result["log"] = "no conflict, good patch "
        else:
            result += 1
            getcode_result["result"] = "fail"
            getcode_result["log"] = "pull patch failed, please check it.\n"
            log.error("Error get the source code")
    log.info("kernel_code_location="+kernel_code_location)
    details_log.append(getcode_result)

    for checker in check_items:
        if checker == "bannedwords":
            log.info("bannedwords")
            if result == 0:
                if kernel_patch_list != '':
                    git = Git( kernel_test_repo )
                    #git log --pretty=medium origin/base..HEAD
                    commit_data = git.log("--pretty=medium","origin/"+kernel_test_branch+"..HEAD").stdout.decode()
                    log.info(commit_data)
                    banned_report = OrderedDict()
                    banned_report["Name"] = "bannedwords"
                    if commit_data !='':
                        ban_result, msg, commit_error = banned_words_check.main(commit_data.splitlines())
                        banned_result["result"] = ban_result
                        banned_result["log"] = msg
                        banned_result["url"] = build_url+'artifact/bannedword_result.json '
                        details_log.append(banned_result)

                        banned_report["result"] = ban_result
                        banned_report["log"] = commit_error
                    else:
                        banned_result["log"] = "there isn't any commit message to check, please infor the admin"
                        banned_result["url"] = build_url+'artifact/bannedword_result.json '
                        details_log.append(banned_result)
                        banned_report["result"] = "fail"
                        banned_report["log"] = "there isn't any commit message to check, please infor the admin"

                    banned_json=json.dumps(banned_report,indent=4)
                    fd = open(os.getcwd()+'/bannedword_result.json', "w")
                    fd.write(banned_json)
                    fd.close()

        elif checker == "checkpatch":
            log.info("checkpatch")
            #checkpatch
            if result == 0:
                if kernel_patch_list != '':
                    tools = os.path.join( kernel_code_location, checkpatch_info["tool"])
                    ckpatch = CheckPatch(tools, checkpatch_info["config"])
                    ckpatch_result = ckpatch.checkindir(kernel_code_location+"/patches/")
                    #if ckpatch_result["result"] != "pass":
                    #    result += 1
                    ckpatch_result["url"] = build_url+'artifact/checkpatch_result.json '
                    details_log.append(ckpatch_result)

        elif checker == "compile":
            log.info("compile")
            #compilt_test
            if result == 0:
            #prepare the config
                if (make_info["config_repo"]!='') and (make_info["config_repo"]!=''):
                    out = prepare_code.getcode(make_info["config_repo"], make_info["config_branch"])
                    if out != -1:
                        config_location = os.path.abspath(out)

                log.info(config_location)
                compile_result = compile_test.compile_staging_test(kernel_code_location,config_location,make_info)
                compile_result["url"] = build_url
                if compile_result["result"] != 'pass':
                    result += 1
                details_log.append(compile_result)

        elif checker == "coverity":
            log.info("coverity")
            #coverity
            if result == 0:
                if kernel_patch_list != '':
                    coverity_result = cov_test.cov_topic(kernel_test_repo, kernel_test_branch, kernel_patch_list[0][:5], kernel_code_location,cov_info)
                    #not block the list test, only report error:
                    coverity_result["url"] = build_url+'artifact/coverity_result.json '
                    details_log.append(coverity_result)

        else:
            log.info("now this checker:%s not support" %checker)



    fail_detail = ''
    summary_result = 0
    log.info(summary_items)
    for details in details_log:
        fail_detail += details["name"] + " result is " + details["result"]+". \n"
        if details["name"] in summary_items:
            if (details["result"]=='fail'):
                summary_result +=1

    data2 = dict()
    result_report["job_name"] = job_name
    if summary_result == 0:
        result_report["result"] = "pass"
        data2["vendor_stop_next"] = False
    else:
        result_report["result"] = "fail"
        data2["vendor_stop_next"] =  True


    result_report["msg"] = "the static test is %s:\n %s the detail log is in the jenkins build job:%s" %(result_report["result"], fail_detail, build_url)

    result_report['details'] = details_log
    #log.info(result_report)


    result_json=json.dumps(result_report,indent=4)
    data2["msg"] = result_json
    msg_rpt2 = result_json
    metronome_client.send(collect_server, "pass" ,job_id, msg_rpt2, "Jenkins", data2)

    log.info(result_json)
    fd = open(report, "w")
    fd.write(result_json)
    fd.close()

if __name__ == '__main__':
      sys.exit(main(sys.argv[1:]))

