#!/usr/bin/python

import sys
import os
import subprocess
import sh
import re
import json
import logging as log
import multiprocessing
import getopt
from collections import OrderedDict

CWD = os.getcwd()


findwarning = 0

def_arch_types= ['x86_64','arm64']
#make_configs={'allnoconfig'}
def_make_configs=['allyesconfig','allmodconfig','allnoconfig']
nproc = sh.Command('/usr/bin/nproc')().stdout.decode().strip()
#make_jnum='-j20'

PASS = 0
ERROR_GET_CODE = 1
ERROR_DOWNLOAD_PATCH = 2
ERROR_KERNEL_MAKE = 3
ERROR_OSIT_MAKE = 4
ERROR_WARNING = 5

JOB_RESULT = {
    PASS: True,
    ERROR_GET_CODE: False,
    ERROR_DOWNLOAD_PATCH: False,
    ERROR_KERNEL_MAKE: False,
    ERROR_OSIT_MAKE: False,
    ERROR_WARNING: False}

RESULT_REMARK = {
    PASS: 'good job',
    ERROR_GET_CODE: 'get the source code failed',
    ERROR_DOWNLOAD_PATCH: 'download patch failed',
    ERROR_KERNEL_MAKE: 'kernel build failed',
    ERROR_OSIT_MAKE: 'osit build failed',
    ERROR_WARNING: 'please check warning'}


git = sh.Command('/usr/bin/git')
make = sh.Command('/usr/bin/make')


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


def run_cmd(command, err_msg=None, err_ignore=True, exit_code=None, use_shell=True):
    log.info("  Run command: %s" %command)
    try:
        output = subprocess.check_output(command,
                                         stderr=subprocess.STDOUT,
                                         shell=use_shell
                                        )
    except subprocess.CalledProcessError as e:
        output = e.output
        ret_code = e.returncode
        log.error("  Output: %s" %output)
        log.error("Error with return code : %s" %ret_code)
        if err_msg:
            log.error(err_msg)
        if err_ignore:
            log.error("Ignored error")
            return ret_code
        else:
            log.error("Terminated")
            sys.exit(exit_code if exit_code else ret_code)
    log.info("  Output: %s" %output)
    return 0

def run_cmd_pipe(command):
    proc = subprocess.Popen(command, \
                            shell = True, \
                            stdout = subprocess.PIPE, \
                            stderr = subprocess.PIPE)

    output = proc.stdout.read()
    error = proc.stderr.read()
    returncode = proc.wait()
    return [returncode, output, error]

def cleanup(compile_location):
    run_cmd("rm -rf %s && echo $?" %compile_location)
    return


def test_patch_compile(compile_arch,cross_compile,compile_config):

    log.info(make_jnum)

    make('distclean')
    for line in make('clean', _err_to_out=True, _iter=True):
        log.info(line)
    log_file=CWD+'/log_'+compile_arch+compile_config
    fd = open(log_file,'w')

    try:
        if(cross_compile!=''):
            for line in make(compile_arch,cross_compile,compile_config, _err_to_out=True ):
                fd.write(line)
        else:
            for line in make(compile_arch,compile_config, _err_to_out=True ):
                fd.write(line)

    except Exception as e:
        log.error("make config error")
        log.error(unicode(e).encode('ascii', 'replace'))
        fd.close()
        return ERROR_KERNEL_MAKE

    try:
        if(cross_compile!=''):
            for line in make(compile_arch,cross_compile,make_jnum, _err_to_out=True, _iter=True):
                log.info(line)
                fd.write(line)
        else:
            for line in make(compile_arch,make_jnum, _err_to_out=True, _iter=True):
                log.info(line)
                fd.write(line)
    except Exception as e:
        log.error("make error")
        log.error(unicode(e).encode('ascii', 'replace'))
        fd.close()
        return ERROR_KERNEL_MAKE
    fd.close()
    warning_check(findwarning,'warning', log_file)

    return 0

def compile(compile_para, compile_config,make_jnum=20,config_location=None):
    para_list=[]
    try:
        make('distclean')
    except Exception as e:
        log.error("make clean error")
        return ERROR_KERNEL_MAKE

    for  para in compile_para.keys():
        if compile_para[para]!='':
            para_list.append(para+'='+compile_para[para])


    if compile_config[0:3] == 'all':
        try:
            if compile_para["CC"]!='':
                log_file=CWD+'/log_'+compile_para["ARCH"]+'_'+compile_para["CC"]+'_'+compile_config
            else:
                log_file=CWD+'/log_'+compile_para["ARCH"]+'_gcc_'+compile_config

            fd = open(log_file,'w')
            #for line in make(compile_para, compile_config, _err_to_out=True ):
            for line in make(para_list, compile_config, _err_to_out=True ):
                fd.write(line)

        except Exception as e:
            log.error("make config error")
            log.error("make config error")
            fd.close()
            return ERROR_KERNEL_MAKE
    else:
        try:
            log_file=compile_config.replace('/','_')
            log_file=CWD+'/log_'+log_file
            fd = open(log_file,'w')
            config_file = os.path.join(str(config_location), compile_config)
            tools = os.getcwd()+'/scripts/kconfig/merge_config.sh'
            log.info(tools)
            log.info(config_file)
            out = os.popen(tools + ' ' + config_file ).readlines()
            for line in out:
                log.info(line)
                fd.write(line)
        except Exception as e:
            log.error("merge config error")
            fd.close()
            return ERROR_KERNEL_MAKE
    try:
        for line in make(para_list, make_jnum, _err_to_out=True, _iter=True):
            log.info(line)
            fd.write(line)
    except Exception as e:
        log.error("make error")
        fd.close()
        return ERROR_KERNEL_MAKE
    fd.close()
    warning_check(findwarning,'warning', log_file)

    return 0

def warning_check(findwarning,keyword, filename):
    '''
    search the keyword in a assign file
    '''
    warning_log=''
    #os.chdir(CWD)
    if(os.path.isfile(filename) == False):
        log.info('Input filepath is wrong,please check again!')
        sys.exit()
    linenum = 1
    warning_fd = open("%s/warning.xml"%CWD,'a')
    with open(filename, 'r') as fread:
        lines = fread.readlines()
        for line in lines:
            rs = re.search(keyword, line, re.IGNORECASE)
            if rs:
                warning_log +='line:%d %s<br/>\n'%(linenum,line)
                lsstr = line.split(keyword)
                strlength = len(lsstr)
                findwarning = findwarning + (strlength - 1)
            linenum = linenum + 1
    warning_fd.write('<hr/> there are %d warnings in %s <br/>\n'%(findwarning,filename))
    warning_fd.write(warning_log)
    warning_fd.close()


def kennel_compile_process(thread_name,compile_para,kernel_code_location, make_configs=def_make_configs,make_jnum=20, config_location=None):
    if compile_para != '':
        log.info('thread name is %s ' %thread_name)
        log.info("the current thread dir is %s" %os.getcwd())
        log.info("the current project dir is %s" %kernel_code_location)
        build_dir=CWD +'/'+ thread_name
        run_cmd("rm -rf %s" %build_dir)
        run_cmd("mkdir -p %s" %build_dir)
        run_cmd("cp -rf %s/* %s" %(kernel_code_location,build_dir))
        os.chdir(build_dir)
        for compile_config in make_configs:
            status=compile(compile_para,compile_config,make_jnum, config_location)
            if status!=0:
               return thread_name+'_'+compile_config+'_'+'fail'
        return thread_name + '_compile passed'

def compile_staging_test(kernel_code_location,config_location,make_info):
    #check if it we can build
    os.chdir(kernel_code_location)
    log.info(config_location)
    log.info(make_info)

    threads=[]

    result = []
    report = OrderedDict()
    report_log = []
    pool = multiprocessing.Pool(processes=6)
    run_cmd("rm -rf %s/log_* " %CWD)
    run_cmd("rm -rf %s/warning.xml" %CWD)
    os.chdir(CWD)
    make_jnum='-j'+make_info["jnum"]
    if make_info["compile_matrix"]!='':
        builds = make_info["compile_matrix"].keys()
    else:
       return

    log.info(builds)

    for build in builds:
        build_info = make_info["compile_matrix"][build]
        log.info(build_info)
        compile_para = build_info["make_para"]

        for configs in build_info["config"].keys():
            #make_configs = build_info[configs].split(',',)
            make_configs = build_info["config"][configs].split(',',)
            log.info(make_configs)
            if (configs =="basic_config") or \
                ((configs =="android_config") and (make_info["kernel_branch"]=="android")) or \
                ((configs =="base_config") and (make_info["kernel_branch"]=="base")):

                result.append(pool.apply_async(kennel_compile_process,(build+'_'+configs, compile_para ,kernel_code_location,make_configs, make_jnum, config_location)))
            else:
                log.info(configs + " nothing to do in branch "+ make_info["kernel_branch"])

    pool.close()
    pool.join()
    status=0
    for res in result:
      compile_result=res.get()
      log.info(compile_result)
      report_log.append(compile_result)
      if (re.search('fail', compile_result)):
        status=ERROR_KERNEL_MAKE
    os.chdir(CWD)


    #{"name": "xxx", "result": "fail|pass|block", "log": "", "url": ""}
    report["name"] = "compile_test"
    if status == 0:
        report["result"] = "pass"
    else:
        report["result"] = "fail"
    report["log"] = str(report_log)

    report["url"] = ''

    log.info('all_kernel_build_in_multiprocess end')
    #log.info(report)
    return  report

def compile_test(kernel_code_location, arch_types):
    #check if it we can build
    os.chdir(kernel_code_location)
    log.info(arch_types)
    log.info(def_arch_types)
    log.info(arch_types)
    threads=[]
    result = []
    report = OrderedDict()
    report_log = []
    pool = multiprocessing.Pool(processes=4)
    run_cmd("rm -rf %s/log_* " %CWD)
    run_cmd("rm -rf %s/warning.xml" %CWD)
    os.chdir(CWD)

    for arch in arch_types:
        if (arch =="arm64"):
            cross_compile='CROSS_COMPILE=aarch64-linux-gnu-'
        else:
            cross_compile='CROSS_COMPILE=x86_64-poky-linux-'
        result.append(pool.apply_async(kennel_compile_process,(arch,arch,cross_compile,kernel_code_location)))

    pool.close()
    pool.join()
    status=0
    for res in result:
      compile_result=res.get()
      log.info(compile_result)
      report_log.append(compile_result)
      if (re.search('fail', compile_result)):
        status=ERROR_KERNEL_MAKE
    os.chdir(CWD)


    #{"name": "xxx", "result": "fail|pass|block", "log": "", "url": ""}
    report["name"] = "compile_test"
    if status == 0:
        report["result"] = "pass"
    else:
        report["result"] = "fail"
    report["log"] = str(report_log)

    report["url"] = ''

    log.info('all_kernel_build_in_multiprocess end')
    #log.info(report)
    return  report

def main(argv):
    console_out('logging.log')
    code_location= ''
    config_location= ''
    make_info = ''

    try:
        opts, args = getopt.getopt(argv,"hd:c:k:")
    except getopt.GetoptError:
        log.info("get the input parameter error ")
        sys.exit(2)

    for opt, arg in opts:
      if opt == '-h':
         log.info("\n\
            Please input the paramter, ep: \n\
            python compile_test.py -p '\"36415/1\"' -i 12 -b 4.14/dnt -a x86_64,arm64 -j 48 \n\
            -d : the kernel folder dir \n\
            -c : the config folder dir \n\
            -k : the make_info, json file \n\
            -h : help")
         sys.exit()
      elif opt == "-d":
          code_location=arg
      elif opt == "-c":
          config_location=arg
      elif opt == "-k":
          files = open(arg,'r')
          make_info = json.loads(files.read())
          files.close()
      else:
          log.info("unknow the input parameter")

    log.info(make_info)
    if(os.path.isfile('warning.xml') == True):
        os.remove('warning.xml')


    run_cmd("rm -rf log_* ")
    #prepare code in the prepare_code.py, return the kernel_code_location

    result = compile_staging_test(code_location, config_location, make_info)

    return result
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
