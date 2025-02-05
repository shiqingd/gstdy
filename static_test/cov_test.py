#!/usr/bin/python3
#
#
import os
import sys
from coverity import CovAnalyze
import logging
import getopt
import re
import sh
import json
from Git import Git
from collections import OrderedDict

logger = logging.getLogger("GitAction")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def is_file_contain_word(file_, query_word):
    if((file_[-2:]) == '.c')|((file_[-2:]) == '.h'):
        files = open(file_,'r').read()
        if re.search(query_word, files):
            print(file_)

def find_hfile_include(hfile, rootdir):
    hfile_basename = os.path.basename(hfile)
    dir_basename = os.path.basename(rootdir)
    included =[]
    for parent,dirnames,filenames in os.walk(rootdir):
        for filename in filenames:
            if filename == hfile_basename:
                continue
            file_ = os.path.join(parent,filename)
            if((file_[-2:]) == '.c'):
                filedata = open(file_,'r').read()
                if re.search(hfile_basename, filedata):
                    included.append(os.path.relpath(file_, dir_basename))
    return included


#input the patch file, return the file path
#the out path is list, and the path in include the Makefile
def getdirfrompatch(p_filename, kernel_root):
    logger.info(p_filename)
    try:
        fd = open(p_filename, 'r')
    except:
        logger.info("the input para error")
        return 0
    pfile = fd.read()
    revfiles = []
    revdirs = []
    pfile_inline = pfile.splitlines(False)

    #find all the revised files in this patch
    for line in pfile_inline:
        if re.search("\+\+\+ b", line):
            revfiles.append(line[6:])
    logger.info("this patch include the list files:")
    logger.info(revfiles)


    #check its fold include "Makefile", make need "Makefile"
    for fl in revfiles:
        # only check the *.c and *.h other files ignore
        # *.c file
        if (fl[-2:] == '.c')|(fl[-2:] == '.h'):
            while 1:
                fl_path = os.path.dirname(fl)
                files = os.listdir( os.path.join(kernel_root, fl_path ))
                if re.search("Makefile", str(files)):
                    revdirs.append( fl_path+'/' )
                    break
                else:
                    fl = fl_path
                    if fl == '':
                        revdirs.append( fl )
                        break

    #remove the double folder
    for rdir in revdirs:
        while revdirs.count( rdir ) != 1:
            revdirs.remove( rdir )

    logger.info(revdirs)

    #remove include folder

    key_included = "xxxx_is_include/"
    if len(revdirs) > 1 :
        for rdir in revdirs:
            if (rdir ==  '/')|(rdir == ''): #means it should be make in the root path
                revdirs[0] = '/'
                del revdirs[1:]
                break
            for j in range(len(revdirs)):
                if rdir[-1] != '/':
                    rdir = rdir + '/'
                if revdirs[j][-1:] != '/':
                    revdirs[j] = revdirs[j] + '/'
                if rdir != revdirs[j]:
                    if revdirs[j].find(rdir) != -1:
                        revdirs[j]= key_included
                        break;
        while(revdirs.count( key_included)):
            revdirs.remove( key_included )

    logger.info("these folders should be scan")
    logger.info(revdirs)

    return revfiles, revdirs

def getdirfromrepo( test_repo, test_branch ,kernel_root ):
    revfiles = []
    revdirs = []

    #find all the revised files in this patch
    #get the changed files
    #os.chdir( root_path )
    git = Git( test_repo )
    files = git.show("origin/"+test_branch+"..HEAD","--stat-width=500").stdout.decode()
    for l in files.splitlines():
        match = re.search(" \| ", l)
        if match:
            fds = l.split()
            if "=>" in fds:
                #hit a rename file
                fname = fds[0][:fds[0].index("{")] #drivers/usb/{common/roles.c => drivers/usb/
                fname += fds[2][:-1]
                logger.info("File renamed: %s", fname)
                revfils.append(fname)
            elif fds[0][-1] in ('c', 'h', ):
                logger.info("File modified: %s", fds[0])
                revfiles.append(fds[0])
    logger.info("this patch include the list files:")
    logger.info(revfiles)


    #check its fold include "Makefile", make need "Makefile"
    for fl in revfiles:
        # only check the *.c and *.h other files ignore
        # *.c file
        if (fl[-2:] == '.c')|(fl[-2:] == '.h'):
            while 1:
                fl_path = os.path.dirname(fl)
                files = os.listdir( os.path.join(kernel_root, fl_path ))
                if "Makefile" in files:
                    revdirs.append( fl_path+'/' )
                    break
                else:
                    fl = fl_path
                    if fl == '':
                        revdirs.append( fl )
                        break

    #remove the double folder
    for rdir in revdirs:
        while revdirs.count( rdir ) != 1:
            revdirs.remove( rdir )

    logger.info(revdirs)

    #remove include folder

    key_included = "xxxx_is_include/"
    if len(revdirs) > 1 :
        for rdir in revdirs:
            if (rdir ==  '/')|(rdir == ''): #means it should be make in the root path
                revdirs[0] = '/'
                del revdirs[1:]
                break
            for j in range(len(revdirs)):
                if rdir[-1] != '/':
                    rdir = rdir + '/'
                if revdirs[j][-1:] != '/':
                    revdirs[j] = revdirs[j] + '/'
                if rdir != revdirs[j]:
                    if revdirs[j].find(rdir) != -1:
                        revdirs[j]= key_included
        while(revdirs.count( key_included)):
            revdirs.remove( key_included )

    logger.info("these folders should be scan")
    logger.info(revdirs)

    return revfiles, revdirs

def cov_patchlist(test_repo, test_branch, topic, root_path,cov_stream,cov_info):
    scan_files = []
    build_folders =[]
    pwd = os.getcwd()
    report = OrderedDict()
    report["patch-subject"] = topic

    scan_files, build_folders = getdirfromrepo(test_repo, test_branch, root_path)
    if len(build_folders) == 0:
        report["result"] = "pass"
        report["summary"]= "there are no revised *.c or *.h files need to scan\n"
        return report

    logger.info(scan_files)
    logger.info(build_folders)
    cov_scan = CovAnalyze( cov_info )
    cov_tmp_dir = pwd + "/cov_tmp_" + topic
    cov_report = pwd + "/cov_report_" + topic
    cov_report_dir = pwd + "/cov_report_dir_" + topic

    os.chdir(root_path)
    if os.path.exists(cov_tmp_dir):
        logger.info(os.listdir(cov_tmp_dir))
        sh.Command('/bin/rm')(["-rf",cov_tmp_dir])
    os.mkdir(cov_tmp_dir)
    if os.path.exists(cov_report_dir):
        logger.info(os.listdir(cov_report_dir))
        sh.Command('/bin/rm')(["-rf",cov_report_dir])
    os.mkdir(cov_report_dir)
    logger.info(os.listdir(cov_tmp_dir))
    cov_scan.makeconfig("make O=%s ARCH=x86_64 x86_64_defconfig" %cov_tmp_dir)
    cov_scan.covconfigure("gcc",cov_tmp_dir)
    build_cmd = "make O=%s ARCH=x86_64" %(cov_tmp_dir)
    for folder in build_folders:
        if folder != '/': #'/' means root, compile all
            build_cmd += " %s" %folder
        else:
            break

    cov_scan.covbuild(cov_tmp_dir, build_cmd)
    cov_scan.covanalyze(cov_tmp_dir)

    cov_scan.covdefectreport(cov_stream, cov_tmp_dir, cov_report)
    #filter the error located in the revised files
    fd = open(cov_report,'r')
    cov_report_json = fd.read()
    cov_report_dict = json.loads(cov_report_json)

    issue_info = []
    defect = 0
    for issue in cov_report_dict["issueInfo"]:
        find_issue = {}
        for s_file in scan_files:
            if issue["occurrences"][0]["file"][1:]== s_file:
                defect += 1
                find_issue["cid"] = issue["cid"]
                find_issue["occurrences"] = issue["occurrences"]
                issue_info.append(find_issue)

    new_defect = 0
    newissue_info =[]
    for issue in cov_report_dict["issueInfo"]:
        if issue["presentInComparisonSnapshot"] == "true":
            new_issue = {}
            for s_file in scan_files:
                if issue["occurrences"][0]["file"][1:]== s_file:
                    new_defect += 1
                    new_issue["cid"] = issue["cid"]
                    new_issue["occurrences"] = issue["occurrences"]
                    newissue_info.append(new_issue)

    result_log = OrderedDict()
    result_log["analysisInfo"] = cov_report_dict["analysisInfo"]
    result_log["newissueInfo"] = newissue_info
    result_log["issueInfo"] = issue_info

    if new_defect == 0:
        report["result"] = "pass"
    else:
        report["result"] = "fail"
    report["summary"]= "there are %d new defect of all the %d defect issue about your revised files\n" %(new_defect, defect)
    report["log"]= result_log

    logger.info("defect is %d" %defect)
    logger.info("new_defect is %d" %new_defect)

    os.chdir( pwd )
    return report


def cov_patch(patch, root_path,cov_stream,cov_info):
    scan_files = []
    build_folders =[]
    pwd = os.getcwd()
    pfile =  os.path.basename(patch)
    report = OrderedDict()
    report["patch-subject"] = pfile[5:]

    scan_files, build_folders = getdirfrompatch(patch, root_path)
    if len(build_folders) == 0:
        report["result"] = "pass"
        report["summary"]= "there are no revised *.c or *.h files need to scan\n"
        return report

    logger.info(scan_files)
    logger.info(build_folders)
    cov_scan = CovAnalyze( cov_info )
    cov_tmp_dir = pwd + "/cov_tmp_" + pfile
    cov_report = pwd + "/cov_report_" + pfile
    cov_report_dir = pwd + "/cov_report_dir_" + pfile

    os.chdir(root_path)
    if os.path.exists(cov_tmp_dir):
        logger.info(os.listdir(cov_tmp_dir))
        sh.Command('/bin/rm')(["-rf",cov_tmp_dir])
    os.mkdir(cov_tmp_dir)
    if os.path.exists(cov_report_dir):
        logger.info(os.listdir(cov_report_dir))
        sh.Command('/bin/rm')(["-rf",cov_report_dir])
    os.mkdir(cov_report_dir)
    logger.info(os.listdir(cov_tmp_dir))
    cov_scan.makeconfig("make O=%s ARCH=x86_64 x86_64_defconfig" %cov_tmp_dir)
    cov_scan.covconfigure("gcc",cov_tmp_dir)
    build_cmd = "make O=%s ARCH=x86_64" %(cov_tmp_dir)
    for folder in build_folders:
        if folder != '/': #'/' means root, compile all
            build_cmd += " %s" %folder
        else:
            break

    cov_scan.covbuild(cov_tmp_dir, build_cmd)
    cov_scan.covanalyze(cov_tmp_dir)

    cov_scan.covdefectreport(cov_stream, cov_tmp_dir, cov_report)
    #filter the error located in the revised files
    fd = open(cov_report,'r')
    cov_report_json = fd.read()
    cov_report_dict = json.loads(cov_report_json)

    issue_info = []
    defect = 0
    for issue in cov_report_dict["issueInfo"]:
        find_issue = {}
        for s_file in scan_files:
            if issue["occurrences"][0]["file"][1:]== s_file:
                defect += 1
                find_issue["cid"] = issue["cid"]
                find_issue["occurrences"] = issue["occurrences"]
                issue_info.append(find_issue)

    new_defect = 0
    newissue_info =[]
    for issue in cov_report_dict["issueInfo"]:
        if issue["presentInComparisonSnapshot"] == "true":
            new_issue = {}
            for s_file in scan_files:
                if issue["occurrences"][0]["file"][1:]== s_file:
                    new_defect += 1
                    new_issue["cid"] = issue["cid"]
                    new_issue["occurrences"] = issue["occurrences"]
                    newissue_info.append(new_issue)

    result_log = OrderedDict()
    result_log["analysisInfo"] = cov_report_dict["analysisInfo"]
    result_log["newissueInfo"] = newissue_info
    result_log["issueInfo"] = issue_info

    if new_defect == 0:
        report["result"] = "pass"
    else:
        report["result"] = "fail"
    report["summary"]= "there are %d new defect of all the %d defect issue about your revised files\n" %(new_defect, defect)
    report["log"]= result_log

    logger.info("defect is %d" %defect)
    logger.info("new_defect is %d" %new_defect)

    os.chdir( pwd )
    return report

def cov_patchdir(patch_dir, root_path, cov_config):
    #get the latest stream in the preoject
    report_final = OrderedDict()
    report_final["name"] = "coverity scan"
    report_final["result"] = "pass"
    report_final["url"] = ""
    report_final["log"] = "coverity scan has start"

    report = OrderedDict()
    log = ''
    cov_streams = cov_config["cov_streams"]
    logger.info(cov_config)
    try:
        cov_scan = CovAnalyze( cov_config )
        stream = cov_scan.covgetneweststream(cov_streams)
        patchfiles = os.listdir(patch_dir)
        for pfile in patchfiles:
            logger.info(pfile)
            tmp_report = cov_patch(patch_dir+'/'+pfile, root_path, stream, cov_config)
            # the patch shoule by "git format-patch -1 --suffix -gerridid"
            report[pfile[-5:]]=tmp_report
            log +=pfile[-5:]+ ":"+tmp_report["summary"]
            if tmp_report["result"] != "pass":
                report_final["result"] = "fail"
                break
        report_final["log"] = log
    except Exception as e:
        report_final["result"] = "block"
        report_final["log"] = "coverity scan error, please info admin"

    fd = open("./coverity_result.json",'w')
    fd.write(json.dumps(report, indent=4))
    fd.close()
    return report_final

def cov_topic(test_repo, test_branch, topic,root_path, cov_config):
    #get the latest stream in the preoject
    report_final = OrderedDict()
    report_final["name"] = "coverity scan"
    report_final["result"] = "pass"
    report_final["url"] = ""
    report_final["log"] = "coverity scan has start"
    scan_files = []
    build_folders =[]

    report = OrderedDict()
    log = ''
    cov_streams = cov_config["cov_streams"]
    logger.info(cov_streams)
    logger.info(cov_config)
    try:
        cov_scan = CovAnalyze( cov_config )
        stream = cov_scan.covgetneweststream(cov_streams)

        tmp_report = cov_patchlist(test_repo, test_branch, topic, root_path, stream, cov_config)
        # the patch shoule by "git format-patch -1 --suffix -gerridid"
        report[ topic ]=tmp_report
        log += topic + ":"+tmp_report["summary"]
        if tmp_report["result"] != "pass":
            report_final["result"] = "fail"
        report_final["log"] = log
        logger.info(scan_files)
    except Exception as e:
        report_final["result"] = "block"
        report_final["log"] = "coverity scan error, please info admin"

    fd = open("./coverity_result.json",'w')
    fd.write(json.dumps(report, indent=4))
    fd.close()
    return report_final


def test():
    #patchfile = "./patches/0007-drm-i915-gvt-add-plane-rotation-support-for-90-180-a.patch"
    #patchfile = "./patches/0009-ipu-Fix-double-free-and-firmware-loading-issues.patch"
    #patch_root = "./patches"
    kernel_root = "/home/hongli/MyWork/metronome/dev_branch/test/kernel-lts2018"
    #cov_stream = "kernel-lts2018-v4.19.1"
    #cov_patchdir(patch_root, kernel_root, cov_stream)
    #cov_patch(patchfile, kernel_root, cov_stream)
    #hfile = "include/linux/zutil.h"
    #find_hfile_include(hfile, kernel_root)
    stream = "12345"
    print(stream)
    cov_scan = CovAnalyze()
    stream = cov_scan.covgetneweststream("kernel-lts2018*")
    print(stream)

def main(argv):

    kernel_test_branch = ''
    kernel_code_dir = ''
    kernel_base_scan = ''
    try:
        opts, args = getopt.getopt(argv,"hb:d:c:")
    except getopt.GetoptError:
        logger.info("get the input parameter error ")
        sys.exit(2)

    if len(opts) == 0:
        logger.info("please input para")
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            logger.info("\n\
                    Please input the paramter, ep: \n\
                    python3 cov.py -b 4.14/dnt -d drivers/usb/ -c true \n\
                    -b : the branch name to be scan \n\
                    -d : the scan folder, if scan all the kernel, ignore it \n\
                    -c : compare the result with the base tag \n\
                    -h : help")
            sys.exit()
        elif opt == "-b":
            kernel_test_branch = arg
        elif opt == "-d":
            kernel_code_dir=arg
        elif opt == "-c":
            kernel_base_scan=arg
        else:
            logger.info("unknow the input parameter")

    logger.info(kernel_test_branch)
    logger.info(kernel_code_dir)
    logger.info(kernel_base_scan)

    cov_scan = CovAnalyze()
    if kernel_code_dir != '':
        if kernel_code_dir[-1] != '/':
            kernel_code_dir = kernel_code_dir + '/'
        build_cmd = "make O=./build ARCH=x86_64 "+kernel_code_dir
    else:
        build_cmd = "make O=./build ARCH=x86_64"

    cov_scan.cov_scan(build_cmd,kernel_test_branch,kernel_code_dir,kernel_base_scan)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
