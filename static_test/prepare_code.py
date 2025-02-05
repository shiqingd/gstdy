#!/usr/bin/python3

import sys
from Git import Git
import os
import sh
import re
import logging as log
import getopt
import json


def parse_git_range_diff(diff_text):
    sha1s = []
    for l in diff_text.splitlines():
        match = re.search(r'[-----------]\d*:', l)
        if match:
            fds = l.split()
            # the third field is: >, =, !, <
            #   >: new patch
            #   =: no change
            #   !: patch changed
            #   <: patch removed
            if fds[2] in ('>', '!', ):
                sha1s.append(fds[4])

    return sha1s


def getcode(test_repo,test_branch = None ,patch_list = None):
    #check if the repo had cloned;
    git = Git(test_repo)
    log.info(git.project)

    try:
        git.pushd()
        git.popd()
    except Exception as e:
        git.clone()

    git.checkout("-f","master")
    git.remote("prune","origin")
    git.pull("-r")
    git.clean("-xdf")


    if test_branch != None:
        out = git.ls_remote(test_repo ,test_branch)
        if out == '':
            log.info("there is not the branch in the repo, please check again")
            return -1
        git.branch("-D", test_branch)
        git.checkout("-f", test_branch)

    #git pull ssh://honglili@git-amr-4.devtools.intel.com:29418/pk_qa-coverity refs/changes/53/67053/1
    if (patch_list == None):
        return git.basedir
    if isinstance(patch_list, list):
        for patch in patch_list:
            try:
                match = re.search('([0-9:]+)/(.+)',str(patch))
            except Exception as e:
                log.info("get patch error " + patch)
                return -1
            if match :
                patchid = match.group(1)
                patchset = match.group(2)

                origin_rev = git.rev_parse( 'HEAD' ).stdout.decode()[:-1]
                baseline_rev = git.describe('--tags').stdout.decode()[:-1]
                log.info(baseline_rev)

                cmd_para1 = "refs/changes/%s/%s/%s" %(patchid[-2:],patchid,patchset)

                cmd1 = git.pull(test_repo, cmd_para1)
                out = cmd1.stderr.decode() + cmd1.stdout.decode()
                log.info(out)
                if re.search('fatal|conflict',out,re.IGNORECASE):
                    log.info("get patch error\n"+out)
                    return -1
                cur_rev = git.rev_parse( 'HEAD' ).stdout.decode()[:-1]
                diff_cmd1 = baseline_rev+'..'+origin_rev
                diff_cmd2 = baseline_rev+'..'+cur_rev

                diff_result = git.range_diff(diff_cmd1, diff_cmd2).stdout.decode()
                log.info(diff_result)

                shals = parse_git_range_diff(diff_result)
                for sha in shals:
                    file1 = git.format_patch("-1", "--suffix", "-"+patchid, sha, "-o", os.path.abspath(git.basedir)+"/patches").stdout.decode()
                    log.info(file1)
                log.info("list the shals")
                log.info(shals)


            else:
                log.info("get patch error, input %s not match 12345/6" %patch)
                return -1
        return git.basedir
    else:
        log.info("the input parameter should be list")
        return -1



#python3 prepare_code.py -r "ssh://git-amr-4.devtools.intel.com:29418/pk_qa-coverity" -p "[u'39135/2', u'39136/2']" -i 11 -b dev23
def test(argv):

    build_number = 0
    kernel_test_repo = ''
    kernel_patch_list = ''
    kernel_test_branch = ''
    kernel_code_location = ''
    download_auto = True
    result_report = {}
    logFilename = './testlog.log'

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

    try:
        opts, args = getopt.getopt(argv,"hp:i:b:r:d:")
    except getopt.GetoptError:
        log.info("get the input parameter error ")
        sys.exit(2)

    for opt, arg in opts:
      if opt == '-h':
         log.info("\n\
            Please input the paramter, ep: \n\
            python3 staic_check.py -r \"ssh://git-amr-4.devtools.intel.com/kernel-coe-tracker\" -p '\"36415/1\"' -i 12 -b 4.14/dnt  \n\
            -r : the kernel repo url\n\
            -b : the branch name to be compiled \n\
            -p : the patch in gerrit to be merge \n\
            -d : the kernel folder dir, if input the folder dir, not download the code, directly compile \n\
            -i : the jenkins build job number \n\
            -h : help")
         sys.exit()
      elif opt == "-r":
          kernel_test_repo = arg
      elif opt == "-b":
          kernel_test_branch = arg
      elif opt == "-p":
          kernel_patch_list = eval(arg)
      elif opt == "-d":
          kernel_code_location=arg
          download_auto = False
      elif opt == "-i":
          build_number = arg
      else:
          log.info("unknow the input parameter")

    log.info("kernel_test_repo="+kernel_test_repo)
    log.info("kernel_patch_list=")
    log.info(kernel_patch_list)
    log.info("kernel_test_branch="+kernel_test_branch)
    log.info("kernel_code_location="+kernel_code_location)
    log.info("build_number="+ str(build_number))


    getcode(kernel_test_repo, kernel_test_branch, kernel_patch_list)

if __name__ == '__main__':
      sys.exit(test(sys.argv[1:]))
