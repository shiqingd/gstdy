"""Run checkpatch and static test for kernel config patch"""
#!/usr/bin/env python3

#core modules
import argparse
from collections import OrderedDict
import json
import logging
import os
#import re
import shutil
import sys
#import traceback


#3rd party

#local import
from Git import Git
import prepare_code
import banned_words_check as bwords_test
from checkpatch import CheckPatch
from kcc import cli as kcc_cli
import compile_test as kcompile_test
import metronome_client

#constants
CWD = os.getcwd()
LOG_FMT = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def log_init(log_fmt=LOG_FMT, debug=False):
    sh = logging.StreamHandler()
    #sh.setLevel(logging.DEBUG)
    sh.setFormatter(log_fmt)
    logger = logging.getLogger("ConfigTestLogger")
    logger.addHandler(sh)
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger

def generate_parser():
    """Parse input arguments"""
    parser = argparse.ArgumentParser(description="config test entry")
    parser.add_argument("-u", "--url", dest="build_url", action="store",
                        required=True, help="Jenkins build url")
    parser.add_argument("-c", "--config", dest="config", action="store",
                        required=True, help="Start with config file")
    parser.add_argument("-i", "--id", dest="job_id", action="store",
                        required=True, help="Job id")
    parser.add_argument("-s", "--server", dest="server", action="store",
                        help="Metronome server to report result")
    parser.add_argument("-d", "--debug", dest="debug", action="store",
                        help="Debug mode")
    parser.add_argument("-p", "--patches", dest="patches", action="store",
                        help="Patches to apply on given branch.")
    return parser

def prepare_test(args, logger):
    """Read config files and prepare code repo orchestrate test steps, return a list of test objects"""
    logger.info("Read config first")
    with open(args.config, 'r') as fd:
        config = json.loads(fd.read())
        logger.debug("###Config: %s", config)
    result = {"name": "getcode", "result": "pass", "logs": list()}
    namespace = {"kernel":None, "config":None}
    try:
        logger.info("Prepare code.")
        patches = eval(args.patches)
        kp, cp = setup_code(config, patches, logger)
        namespace["kernel"] = kp
        namespace["config"] = cp
    except Exception as e:
        logger.error("Get code failed due to exception: %s", e)
        result["result"] = "fail"
        result["logs"].append("Fetch code failed due to Exception: %s" %str(e))
    return result, config, namespace

def setup_code(config, patches, logger):
    """Prepare both kernel config and source code"""
    if config["target"] == "config":
        logger.info("Clone config %s origin/%s and apply patches %s.",
                    config["config_repo"], config["config_branch"], str(patches))
        config_path = prepare_code.getcode(config["config_repo"], config["config_branch"], patches)
        if config_path == -1:
            raise Exception("Fetch config repo failed, please check logs.")
        config_path = os.path.abspath(config_path)
        logger.info("Fetch config: %s", config_path)
        logger.info("Clone kernel source code: %s origin/base.", config["kernel_repo"])
        kernel_path = prepare_code.getcode(config["kernel_repo"], "base")
        if kernel_path == -1:
            raise Exception("Fetch kernel repo failed, please check logs.")
    elif config["target"] == "source":
        logger.info("Clone %s origin/%s.",
                    config["config_repo"], config["config_branch"])
        config_path = prepare_code.getcode(config["config_repo"], config["config_branch"])
        if config_path == -1:
            raise Exception("Fetch config repo failed, please check logs.")
        config_path = os.path.abspath(config_path)
        logger.info("Fetch config: %s", config_path)
        logger.info("Clone kernel source code: %s origin/%s and apply patches %s.", config["kernel_repo"], config["kernel_branch"][0], str(patches))
        kernel_path = prepare_code.getcode(config["kernel_repo"], config["kernel_branch"][0], patches)
        if kernel_path == -1:
            raise Exception("Fetch kernel repo failed, please check logs.")
    else:
        logger.warning("Target not defined!")
        kernel_path, config_path = -1, -1
    return kernel_path, config_path


def start_test(config, config_dir, kernel_dir, build_url, logger):
    """Start config test"""
    test_results = list()
    logger.info("Plan to execute %s test objects.", str(len(config["objects"])))
    count = 1
    for obj in config["objects"]:
        logger.debug("Current working directory: %s", os.getcwd())
        logger.debug("Reset back to root working directory: %s", CWD)
        os.chdir(CWD)
        logger.info("No.%s test to run: %s", str(count), obj["name"])
        if obj["name"] == "banned_words":
            if config["target"] == "config":
                r = banned_words_scan(Git(config["config_repo"]), config["config_branch"], logger)
                r["url"] = build_url + 'artifact/bannedword_result.json '
            else:
                r = banned_words_scan(Git(config["kernel_repo"]), config["kernel_branch"][0], logger)
                r["url"] = build_url + 'artifact/bannedword_result.json '
        elif obj["name"] == "checkpatch":
            r = checkpatch_test(config_dir, kernel_dir, config["checkpatch_config"], config["target"], logger)
            r["url"] = build_url + 'artifact/checkpatch_result.json '
        elif obj["name"] == "compile_test":
            r = compile_test(config_dir, kernel_dir, config["compile_config"], logger)
            r["url"] = build_url + 'artifact/compile_test.json'
        elif obj["name"] == "kcc_test":
            r = kcc_test(config_dir, config["kernel_repo"], config["kcc_config"], logger)
            r["url"] = build_url + 'artifact/kcc_test.json'
        else:
            logger.error("Unsupport test item: %s", obj)
            r = dict()
        test_results.append(r)
        logger.debug("Test result: %s", r)
        count += 1
    logger.info("All test objects has been executed.")
    return test_results

def merge_test_result(test_results, config, build_url, logger):
    """Merge all test results together"""
    if config is None:
        logger.error("No config defined, will simply return fail as result!")
        return {"result": "fail", "details": test_results}
    logger.debug("TR: %s", test_results)
    logger.info("Parse rule first.")
    rules = dict() #"name" : "critical|warning" kv pairs
    rules["getcode"] = "critical"
    for obj in config["objects"]:
        rules[obj["name"]] = obj["lvl"]
    r = {"job_name": config["name"], "details": test_results, "result": "pass", "msg": ""}
    for tr in test_results:
        r["msg"] += "Test object %s finished, result is %s.\n" %(tr["name"], tr["result"])
        if tr["result"] == "fail":
            if rules[tr["name"]] == "critical":
                logger.info("Set result as fail due to critical test object %s failed", tr["name"])
                r["result"] = "fail"
                break
            else:
                logger.info("Remain result as pass due to %s test object %s failed.",
                            rules[tr["name"]], tr["name"])
        else:
            logger.debug("Test object %s passed", tr["name"])
    r["msg"] += "Summarized result is %s, please visit %s to get more details" %(r["result"], build_url)
    return r

def report_to_metronome(server, msg, result, job_id, job_name):
    """Report test result to metronome"""
    data = dict()
    data["job_name"] = job_name
    if result["result"] == "pass":
        data["vendor_stop_next"] = False
    else:
        data["vendor_stop_next"] = True
    if "msg" not in result.keys():
        data["msg"] = msg
    else:
        data["msg"] = str(result)
    metronome_client.send(server, "pass", job_id, msg, "Jenkins", data)
    return

def compile_test(config_dir, kernel_dir, config, logger):
    """Wrap compile test for config"""
    logger.info("Run compile test.")
    logger.debug("Config directory: %s", config_dir)
    logger.debug("Kernel directory: %s", kernel_dir)
    logger.info("%d target to compile", len(config["compile_matrix"]))
    count = 0
    msg = ""
    result = "pass"
    for t in config["compile_matrix"]:
        logger.info("Target arch %s branch %s config %s", t["arch"], t["kernel_branch"], t["config"])
        temp = t["kernel_branch"].replace('/', '_')
        build_dir="%s/%s_%s_%s" %(CWD, t["arch"], temp, str(count))
        if t["arch"] == "arm64":
            cross_compile='CROSS_COMPILE=aarch64-linux-gnu-'
        else:
            cross_compile='CROSS_COMPILE=x86_64-poky-linux-'
        kcompile_test.run_cmd("rm -rf %s" %build_dir)
        kcompile_test.run_cmd("cp -rf %s %s" %(kernel_dir,build_dir))
        logger.info("Directory prepare finished, fetching given branch.")
        os.chdir(build_dir)
        kcompile_test.run_cmd("whoami && git fetch origin %s && git checkout origin/%s" \
                              %(t["kernel_branch"], t["kernel_branch"]))
        logger.info("Directory update finished, ready to compile.")
        r = kcompile_test.compile("ARCH="+t["arch"], cross_compile, t["config"],
                                  "-j"+config["jnum"], config_dir)
        logger.debug("Reset to default CWD.")
        os.chdir(CWD)
        if r != 0:
            msg = "Compile test failed on: arch %s branch %s config %s" \
                  %(t["arch"], t["kernel_branch"], t["config"])
            result = "fail"
            logger.error(msg)
            break
        else:
            msg += "Compile test passed on: arch %s branch %s config %s.\n" \
                  %(t["arch"], t["kernel_branch"], t["config"])
        count += 1
    return {"name" : "compile_test", "result": result, "log": msg}

def checkpatch_test(config_dir, kernel_dir, config, target, logger):
    """Wrap check patch test for config"""
    #copy patches to kernel source directory for running checkpatch
    if target == "config":
        logger.info("Run checkpatch test.")
        patch_path = os.path.join(config_dir, "patches")
        kernel_scan_path = os.path.join(kernel_dir, "patches")
        logger.info("Copy patches from config dir to kernel dir for checkpatch scan.")
        logger.debug("Config patch path: %s", patch_path)
        logger.debug("Kernel scan patch: %s", kernel_scan_path)
        c = shutil.copytree(patch_path, kernel_scan_path)
        logger.debug("Copy finished: %s", str(c))
    else:
        logger.info("Running checkpatch for kernel patches, no need to copy.")
    kernel_scan_path = os.path.join(kernel_dir, "patches")
    tools = os.path.join(kernel_dir, config["tool"])
    ckpatch = CheckPatch(tools, config["config"])
    ckpatch_result = ckpatch.checkindir(kernel_scan_path)
    return dict(ckpatch_result)

def kcc_test(config_dir, kernel_repo, config, logger):
    """Wrap kernel config check test"""
    #TODO: implement this
    logger.info("Run kcc test.")
    logger.debug("Config directory: %s", config_dir)
    k = Git(kernel_repo)
    kernel_dir = k.basedir
    logger.debug("Kernel directory: %s", kernel_dir)
    logger.info("%d configs to check", len(config["kcc_matrix"]))
    os.chdir(CWD)
    logs = list()
    test_pass = True
    for c in config["kcc_matrix"]:
        logger.debug("Config: %s on kernel branch %s", c["config"], c["kernel_branch"])
        #os.chdir(kernel_dir)
        logger.debug(os.getcwd())
        k.checkout("origin/%s" %c["kernel_branch"])
        os.chdir(kernel_dir)
        logger.debug(os.popen("make distclean").readlines())
        logger.info(os.popen("git log --oneline -3").readlines())
        tools = './scripts/kconfig/merge_config.sh'
        config_file = os.path.join(config_dir, c["config"])
        out = os.popen(tools + ' ' + config_file ).readlines()
        for l in out:
            logger.debug(l)
        logger.info(".config file generated, use it for kcc")
        with open(os.path.join(os.getcwd(), ".config"), 'r') as fd:
            cfg = fd.readlines()
        logger.debug(".config readed for kcc_cli: %s lines", len(cfg))
        r, msg = kcc_cli.run(config_file=cfg)
        r_new = False if r == 1 else True
        logs.append("KCC for %s passed: %s, msg is: %s.\n" %(c["config"], r_new, msg))
        test_pass = (test_pass and r_new)
        os.chdir(CWD)
    result={"name": "kcc_test", "result": "pass" if r_new else "fail", "log": "".join(logs)}
    kcc_json=json.dumps(result,indent=4)
    with open(os.getcwd()+'/kcc_result.json', 'w') as fd:
        fd.write(kcc_json)
    return result

def banned_words_scan(git_repo, branch, logger):
    """Wrap banned words scan"""
    #prepare data for banned words scan first
    #git log --pretty=medium origin/<branch>..HEAD
    logger.info("Start banned words scan.")
    commit_data = git_repo.log("--pretty=medium","origin/"+branch+"..HEAD").stdout.decode()
    logger.debug(commit_data)
    result = dict()
    result["name"] = "banned_words"
    if commit_data !='':
        ban_result, msg, commit_error = bwords_test.main(commit_data.splitlines())
        result["result"] = ban_result
        result["log"] = msg
        if commit_error:
            for e in commit_error:
                result["log"] += "Subject: %s Author: %s Found banned words: %s\n" %(e[0], e[1], e[2])
    else:
        result["log"] = "there isn't any commit message to check, please info the admin"
        result["result"] = "fail"
    banned_json=json.dumps(result,indent=4)
    with open(os.getcwd()+'/bannedword_result.json', 'w') as fd:
        fd.write(banned_json)
    logger.info("Banned words scan finished.")
    logger.info("Result: %s", str(result))
    return result

def main(arg_list):
    """Main entry of config test"""
    parser = generate_parser()
    if len(arg_list) == 0:
        parser.print_help()
        return 1
    try:
        args = parser.parse_args(arg_list)
        logger = log_init(debug=args.debug)
        logger.debug("Parsed args are: %s", str(args))
        logger.info("Prepare test data.")
        ts = list()
        c = None
        r, c, ns = prepare_test(args, logger)
        if args.server:
            report_to_metronome(args.server, "%s has start on %s" %(c["name"], args.build_url), {"result":"pass"}, args.job_id, c["name"])
        #first report
        if r["result"] == "fail":
            ts.append(r)
            raise Exception("FetchCodeError")
        logger.info("Test objects detected, start testing.")
        ts.extend(start_test(c, ns["config"], ns["kernel"], args.build_url, logger))
    except Exception as e:
        logger.error("Caught Exception while running test: %s", str(e))
        exc_type, exc_val, exc_traceback = sys.exc_info()
        logger.error("Type: %s", str(exc_type))
        logger.error("Value: %s", str(exc_val))
        logger.error("Trace: %s", exc_traceback)
    finally:
        merged_result = merge_test_result(ts, c, args.build_url, logger)
        if args.server:
            logger.info("Report result to Metronome server: %s", args.server)
            report_to_metronome(args.server, merged_result["msg"], merged_result, args.job_id, c["name"])
        else:
            logger.info("------StartOfReport------")
            logger.info("Test finished, result as below.")
            logger.info("Test result: %s", merged_result["result"])
            for obj in merged_result["details"]:
                logger.info("------Separate Line------")
                logger.info("Test object %s result: %s", obj["name"], obj["result"])
                logger.info("Key log: %s", obj["log"])
            logger.info("------EndOfReport------")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
