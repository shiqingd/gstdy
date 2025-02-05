#!/usr/bin/env python3
import subprocess
import sys
import re
import smtplib
import os
import argparse
import logging
import yaml
from pyshell import PyShell   # FIXME: This is from https://github.com/knsathya/pyshell.git , NOT from PyPI (not compatible)
from jinja2 import Environment, FileSystemLoader
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ci.github.testcases import banned_word_scan as bw
import upload_dashboard

if not "DJANGO_SETTINGS_MODULE" in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
    import django

    django.setup()

try:
    assert('DATABASE_HOST' in os.environ)
except:
    print("Environment Variable DATABASE_HOST not set", file=sys.stderr)
    sys.exit(1)

from framework.models import Kernel, Repository, KernelRepoSet

'''
it should clone audit from clr
if should clone kernel-bkc

if already clone 
git fetch --all
git pull

checkout branch 
run audit from baseline version to staging_ref
save results in a file
email results

'''


class audit_pkt():
    def __init__(self, home='', kernel= None, repo=None, staging_ref='', baseline_tag=None):
        self.repository = repo.url()
        if baseline_tag is not None:
            self.kernel_version = baseline_tag
        else:
            self.kernel_version = kernel.current_baseline
        self.kernel_location = os.path.join(home, repo.project)
        self.dir_home = home
        self.staging_ref = staging_ref
        self.audit_remote = 'http://kojiclear.jf.intel.com/cgit/projects/clr-github-publish-packages/'
        self.audit_loc = home + '/clr_audit'
        self.dashell = PyShell()
        self.output_file = ''
        self.results_file = ''
        self.data_out = ''
        self.output_code = ''
        self.output_commit_msg = ''
        self.output_commit_msg_html = ''
        self.flag_code = False
        self.flag_commit_msg = False

    def print_vars(self):
        print("Repo:", self.repository)
        print("kernel version: ", self.kernel_version)
        print("kernel location: ", self.kernel_location)
        print("staging Git reg: ", self.staging_ref)
        print("audit remote: ", self.audit_remote)
        print("audit location: ", self.audit_loc)
        if not os.path.exists(self.audit_loc):
            os.makedirs(self.audit_loc)

    def decode_print(self, dashell_out):
        if dashell_out[0] == 0 or dashell_out[0] == 1:
            return (dashell_out[1] + dashell_out[2]).decode("utf-8", errors="replace")
        elif dashell_out[0] == 128:
            return dashell_out[2].decode("utf-8", errors="replace")

    def sync_audit(self):
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'clone', self.audit_remote, self.audit_loc, wd=self.dir_home))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'reset', '--hard', wd=self.audit_loc))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all', wd=self.audit_loc))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'pull', wd=self.audit_loc))

    def sync_kernel(self):
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'clone', self.repository, self.kernel_location, wd=self.dir_home))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all','--tags', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'checkout', 'master', wd=self.kernel_location))
        self.data_out += self.decode_print( self.dashell.cmd('git', 'pull', wd=self.kernel_location))
        ret = self.dashell.cmd('git', 'cat-file', '-t',  self.staging_ref, wd=self.kernel_location)
        if ret[0] != 0:
            ret = self.dashell.cmd('git', 'cat-file', '-t',  'origin/'+self.staging_ref, wd=self.kernel_location)
            if ret[0] != 0:
                print('Cannot determine ref type of ', self.staging_ref , str(ret))
                sys.exit(ret[0])
        self.isbranch = ( str(ret[1]) == 'commit')

    def audit_kernel(self):
        if self.isbranch:
            self.data_out += self.decode_print(self.dashell.cmd('git', 'checkout', 'origin/' + self.staging_ref, wd=self.kernel_location))
        else:
            self.data_out += self.decode_print(self.dashell.cmd('git', 'checkout', self.staging_ref, wd=self.kernel_location))
        self.output = self.decode_print(self.dashell.cmd(self.audit_loc + '/audit', '-r', self.kernel_version + '..HEAD', '.', wd=self.kernel_location))
        if self.output is None:
            self.output = ''
        print('<' + str(self.output) + '>')
        if self.output == '':
            self.output = 'Audit from ' + self.audit_remote + \
                ' did not find any banned words IN Code between: ' + \
                self.kernel_version + '..' + self.staging_ref + '\n\n'
        else:
            self.flag_code = True
        return self.data_out, self.output

    def audit_kernel_commits(self,repo_name):
        """
        Determine whether to include banned words
        """
        bw_re, wl_re = self.get_banned_words()
        text_output = ''
        output_commit_msg = ""
        msg_bug = None
        r = re.compile(
            '^(.+)-(v[0-9]\.[0-9]+(?:\.[0-9]+|)(?:-r[ct][0-9]+|\.[0-9]{1,3}){0,1})-([^0-9]+)-([0-9]{6})[-T]([0-9]{6})Z$')
        match = r.match(self.staging_ref)

        branch_outs = ['kmb-mr','thb','adls']
        try:
            if match:
                previous_tag = self.decode_print(self.dashell.cmd('git', 'describe', '{}^'.format(self.staging_ref), '--abbrev=0')).split('\n')[0]
                if not previous_tag:
                    previous_tag = self.kernel_version
            else:
                for branch_out in branch_outs:
                    if branch_out in self.staging_ref:
                        previous_tag = self.decode_print(self.dashell.cmd('git', 'describe', '{}^'.format(self.staging_ref), '--abbrev=0',
                            '--match=*{}* --tags'.format(branch_out))).split('\n')[0]
                        break
                    else:
                        previous_tag = self.kernel_version
        except Exception:
            previous_tag = self.kernel_version

        git_log_results = self.decode_print(
                self.dashell.cmd('git', 'log', '-p', previous_tag + '..'+ self.staging_ref, '--raw', '-U0', wd=self.kernel_location))
        commits = self.parse_git_log(git_log_results)

        commit_error = list()
        for commit in commits:
            msg_bug = bw.find_banned_words(commit['message'], bw_re, wl_re)
            if msg_bug:
                commit_str = "{" + "\n".join("{!r}: {!r},".format(k, v) for k, v in commit.items()) + "}"
                text_output = 'commit_sha: {}'.format(commit['hash']) + '\n' \
                                'author: {}'.format(commit['author']) + '\n' \
                                "Banned words: {}".format(msg_bug) + "\n" \
                                "Subject: {}".format(commit['subject']) + "\n" \
                                "have banned_words Patch:\n\n{}".format(commit_str) + '\n' + \
                                "{}".format('-' * 80)
                output_commit_msg += text_output + '\n'
                commit_error.append((commit["subject"], commit["email"], msg_bug))

        if commit_error:
            self.status_msg = 'Failed'
        else:
            self.status_msg = 'Pass'
            output_commit_msg = 'Not found banned_words'
        if re.search(r'rt',self.staging_ref) or re.search(r'cve',self.staging_ref) or re.search(r'iotg-next',self.staging_ref):
            self.output_commit_msg = 'Result: Skip\nThis {} does not require scanning, do not scan contain cve,rt,iotg-next'.format(self.staging_ref)
        else:
            self.output_commit_msg = 'Result: {}\nThis scan banned words is between:{}..{},repo is {}\n{}'\
                                    .format(self.status_msg, previous_tag, self.staging_ref, repo_name, output_commit_msg)
        self.output_commit_msg_html = self.output_commit_msg + '<br>'
        return self.output_commit_msg

    def parse_git_log(self, git_log_results):
        """
        parse commit, separate the logs, get commit list
        :return: list
        """
        commits = list()
        commit = dict()
        for line in git_log_results.splitlines():
            if line == '' or line == '\n':
                # ignore empty lines
                pass
            elif bool(re.match('commit', line, re.IGNORECASE)):
                # commit xxxx
                commit = {'hash': re.match('commit (.*)', line, re.IGNORECASE).group(1)}
            elif bool(re.match('merge:', line, re.IGNORECASE)):
                # Merge: xxxx xxxx
                pass
            elif bool(re.match('author:', line, re.IGNORECASE)):
                # Author: xxxx <xxxx@xxxx.com>
                m = re.compile('Author: (.*) <(.*)>').match(line)
                commit['author'] = m.group(1)
                commit['email'] = m.group(2)
            elif bool(re.match('date:', line, re.IGNORECASE)):
                pass
            elif bool(re.match('    ', line, re.IGNORECASE)):
                # (4 empty spaces)
                if commit.get('subject') is None:
                    commit['subject'] = line.strip()
                    commit['message'] = ""
                commit['message'] += "%s\n" % (line.strip())
        commits.append(commit)
        return commits

    def get_banned_words(self):
        """
        get banned_words data
        :return: list
        """
        # banned_words_data = open("banned-words", 'r', encoding='utf-8')
        # return banned_words_data.read().splitlines()
        # load banned words from yaml
        mydir = os.path.dirname(os.path.abspath(__file__))
        yaml_fl = os.path.join(mydir, 'ci/github/testcases/bannedwords.yml')
        with open(yaml_fl, 'r') as y:
            bw_yaml = yaml.safe_load(y)
        # bw: banned word
        bw_dict = bw_yaml['bannedword']
        whitelist = bw_yaml['whitelist']
        bw_list = [ w for k in sorted(bw_dict.keys()) for w in bw_dict[k] ]
        bw_re = re.compile(r"\b(%s)\b" % '|'.join(bw_list), re.IGNORECASE)
        wl_re = re.compile(r"\b(%s)\b" % '|'.join(whitelist), re.IGNORECASE)
        return bw_re, wl_re

    def audit_kernel_commit_msg(self):
        banned_words = self.open_banned_words()
        text_output=''
        text_output_html=''
        for word_count in range(len(banned_words)):
            banned_word = banned_words[word_count].split('\n')[0]
            reg_ex_banned_word = "'" + banned_word.replace('.','\.') + "'"
            git_log_results = self.decode_print(self.dashell.cmd('git','log', self.kernel_version + '..HEAD','--grep='+reg_ex_banned_word, wd=self.kernel_location))
            base_text=self.kernel_location + "/:"
            if (git_log_results != None and banned_word != ''):
                self.flag_commit_msg = True
                m = re.findall(r'^commit \b[0-9a-f]{5,40}\b', git_log_results, re.MULTILINE | re.IGNORECASE)
                for h in range(len(m)):
                    sha_num=re.sub('commit', '', m[h])
                    text_output=base_text + "    commit:" + sha_num + "\n" \
                              + base_text + "    file:" "\n" \
                              + base_text + "    banned word:" + banned_word + "\n" \
                              + base_text + "    match:+" "\n" \
                              + base_text
                    text_output_html=base_text + "    commit:" + sha_num + "<br>" \
                              + base_text + "    file:" "<br>" \
                              + base_text + "    banned word:" + banned_word + "<br>" \
                              + base_text + "    match:+" "<br>" \
                              + base_text
                    print(text_output)
                    self.output_commit_msg+=text_output + '\n'
                    self.output_commit_msg_html+=text_output_html + '<br>'
        if(text_output == ''):
            self.output_commit_msg = 'Banned words Audit did not find any banned words IN Commit Messages between: ' + \
            self.kernel_version + '..' + self.staging_ref + '\n'
            self.output_commit_msg_html = self.output_commit_msg + '<br>'
        return self.output_commit_msg

    def open_banned_words(self):
        banned_words_data = open(self.audit_loc + "/banned-words", 'r')
        return banned_words_data.readlines()

    def send_email(self, sender, subject, receivers, template, _results, _staging):
        '''
        Uses Jinja2 to send email to receivers.
        '''
        print('send email')
        # Initialize Jinja2 environment and template
        template_loader = FileSystemLoader(searchpath=os.path.dirname(template))
        template_env = Environment(loader=template_loader)
        templ = template_env.get_template(os.path.basename(template))
        msg = MIMEMultipart('alternative')
        msg['From'] = sender
        msg['Subject'] = subject + _staging
        msg['To'] = ','.join(receivers)
        msg.attach(MIMEText(templ.render(results=_results), 'html'))
        try:
            smtp_obj = smtplib.SMTP('smtp.intel.com')
            smtp_obj.sendmail(sender, receivers, msg.as_string())
            #file_obj = open('results{}.html'.format(build_num), 'w')
            #file_obj.write(templ.render(suites=test_results))
            #file_obj.close()
            print("Successfully sent email")
        except Exception as e:
            logging.error("Unable to send email")
            logging.exception(str(e))

    def check_audit_results(self, email_to):
        #if(self.flag_commit_msg):
        print("commit message scan results send to email(s)", email_to)
        self.send_email('sys_oak@intel.com', '[commit message scan] Audit Banned Words for ', email_to, 'audit_email.j2',self.output_commit_msg_html, self.staging_ref)
        #if(self.flag_code):
        print("CODE scan results send to email(s)", email_to)
        instance_.send_email('sys_oak@intel.com', '[CODE scan] Audit Banned Words: ', email_to, 'audit_email.j2', self.output, self.staging_ref)

    def write_tofile(self, file_name, data):
        self.p_file = open(file_name, 'w+')
        self.p_file.writelines(data)

    def close_file(self):
        self.p_file.close()

    def upload_file(self,file_list,tag,result,category):
        import upload_dashboard
        reporturl = upload_dashboard.save(file_list,tag,result=result,category=category)
        return reporturl

    def sync_base_repo(self,base_repo):
        try:
            self.data_out += self.decode_print(self.dashell.cmd('cd %s;'%self.kernel_location, 'git', 'remote', 'add', 'base-kernel', '%s'%base_repo.url(), wd=self.dir_home))
        except:
            pass
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all', '--tags', wd=self.kernel_location))

    def get_pre_release_tag(self,kernel_version,kernel_category):
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'clone', self.repository, self.kernel_location, wd=self.dir_home))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'fetch', '--all','--tags', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd( 'git', 'checkout', 'master', wd=self.kernel_location))
        self.data_out += self.decode_print( self.dashell.cmd('git', 'pull', wd=self.kernel_location))
        if 'v' not in kernel_version:
            kernel_version = 'v' + kernel_version
        tag_list = self.decode_print(self.dashell.cmd( 'git', 'tag', '--list', '*%s*%s*'% (kernel_version,kernel_category), wd=self.kernel_location))
        pre_tag = None
        for tag in tag_list.split('\n'):
            if 'preempt-rt' not in tag and tag.endswith('Z'):
                if not pre_tag:
                    pre_tag = tag
                elif tag.split('-')[-1] > pre_tag.split('-')[-1] :
                    pre_tag = tag
        return pre_tag

    def range_diff_commit(self,pre_tag,repo_name):
        pre_base = pre_tag.replace('bullpen-', '')
        staging_base = self.staging_ref.replace('bullpen-', '')
        out = self.decode_print(self.dashell.cmd( 'git', 'range-diff', '%s..%s %s..%s'%(staging_base,self.staging_ref,pre_base,pre_tag), wd=self.kernel_location))
        scan_commit_list = re.findall(':  ([a-z0-9]{12,12}) [<!]',out)

        """
        Determine whether to include banned words
        """
        banned_words = self.get_banned_words()
        text_output = ''
        output_commit_msg = ""
        commit_bug = []
        for banned_word in banned_words:
            if banned_word:
                reg_ex_banned_word = "'" + banned_word.replace('.', '\.') + "'"
                for commit_sha in scan_commit_list:
                    git_log_results = self.decode_print(
                        self.dashell.cmd('git', 'show', '-p', commit_sha, '--raw', '-U0',
                                        '--grep=' + reg_ex_banned_word, wd=self.kernel_location))
                    if git_log_results != "":
                        commits = self.parse_git_log(git_log_results)
                        # if this link in git log result,pass
                        if re.findall(r'https://.*.kernel.org/.*.intel\.com', git_log_results, re.MULTILINE | re.IGNORECASE):
                            pass
                        else:
                            for commit in commits:
                                commit_bug.append({'banned_words':reg_ex_banned_word,'commit_sha':commit_sha})
                                commit_str = "{" + "\n".join("{!r}: {!r},".format(k, v) for k, v in commit.items()) + "}"
                                text_output = 'commit_sha: {}'.format(commit['hash']) + '\n' \
                                            'author: {}'.format(commit['author']) + '\n' \
                                            "Banned word: {}".format(banned_word) + "\n" \
                                            "Subject: {}".format(commit['subject']) + "\n" \
                                            "have banned_words Patch:\n\n{}".format(commit_str) + '\n' + \
                                            "{}".format('-' * 80)
                                output_commit_msg += text_output + '\n'
                    else:
                        pass
        if commit_bug:
            self.status_msg = 'Fail'
        else:
            self.status_msg = 'Pass'
            output_commit_msg = 'Not found banned_words'
        self.output_commit_msg = 'Result: {}\nThis scan banned words is between:{}..{},repo is {}\n{}'\
                                    .format(self.status_msg, pre_tag, self.staging_ref, repo_name, output_commit_msg)
        self.output_commit_msg_html = self.output_commit_msg + '<br>'
        return self.output_commit_msg

    def clamscan_code(self,):
        clamscan_result = ''
        clamscan_report = 'Kernel Version:%s\n'%self.staging_ref
        self.decode_print(self.dashell.cmd('sudo freshclam',wd=self.dir_home))
        out = self.decode_print(self.dashell.cmd('clamscan -vr %s | tee clamscan_output.log'%self.kernel_location,wd=self.dir_home))
        flag = 0
        for line_out in out.split('\n'):
            if '----------- SCAN SUMMARY -----------' in line_out:
                flag = 1
            if 'Infected fil' in line_out:
                if int(line_out.split(':')[-1].strip()) != 0:
                    clamscan_result = 'ClamAV scan Fail!'
                else:
                    clamscan_result = 'ClamAV scan Pass!'
            if flag == 1 and line_out:
               clamscan_report += line_out+'\n'
        clamscan_report += 'ClamAV scan result:'+ clamscan_result
        return clamscan_result,clamscan_report

if __name__ == '__main__':

    assert(os.path.exists(os.environ["WORKSPACE"]))
    home = os.environ["WORKSPACE"]

    subprocess.run('rm -f commit_msg_results.log output.log clamscan*.log',shell=True,cwd=home)
    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument('--kernel', '-k', required=True, type=Kernel.validate, help="Valid Values: "+Kernel.list())
    parser.add_argument('--staging-ref', '-s', required=True, type=str, help='Staging Branch or Tag to Scan')
    parser.add_argument('--baseline', '-b', required=False, type=str, help='Override current_baseline database value for this kernel')
    parser.add_argument('--email-to', '-E', type=str, help='Comma-separated list of email addresses')
    parser.add_argument('--verbose', '-v', action='store_true', default=False, help="generate verbose output")
    parser.add_argument('--testsuite', '-t', default=False, help="testsuite name.")
    args = parser.parse_args()
    if args.email_to:
        email_to = str(args.email_to).split(',')
    else:
        email_to=['patrick.j.noziska@intel.com','ranjan.dutta@intel.com','qingdong.shi@intel.com']
    print(args.__dict__)

    kernel = Kernel.objects.get(name = args.kernel)
    # FIXME : Sync up kernel category text with repotype text in DB
    # e.g. repo = KernelRepoSet.objects.get(kernel = kernel, repo__repotype__repotype = kernel.category )
    if kernel.category == 'bp':
        repo = KernelRepoSet.objects.get(kernel = kernel, repo__repotype__repotype = 'quilt').repo
        base_repo = Repository.objects.get(id=39)
        iot_repo = Repository.objects.get(id=58)

        #get pre release bullpen tag
        iot_instance_ = audit_pkt(home, kernel, iot_repo, args.staging_ref, args.baseline)
        iot_instance_.print_vars()
        pre_tag = iot_instance_.get_pre_release_tag(kernel.base_kernel,'bullpen')

        #get base repo
        instance_ = audit_pkt(home, kernel, repo, args.staging_ref, args.baseline)
        instance_.print_vars()
        instance_.sync_kernel()
        instance_.sync_base_repo(base_repo)
        data_out, results_out = instance_.audit_kernel()
        if re.search(r'rt',args.staging_ref) or re.search(r'cve',args.staging_ref):
            commit_msg_out = 'Result: Skip\nThis {} does not require scanning, do not scan contain cve,rt'.format(args.staging_ref)
            data_out = 'No further action is required'
        else:
            commit_msg_out = instance_.range_diff_commit(pre_tag,repo.project)
        
    else:
        repo = KernelRepoSet.objects.get(kernel = kernel, repo__repotype__repotype = 'src').repo
        instance_ = audit_pkt(home, kernel, repo, args.staging_ref, args.baseline)
        instance_.print_vars()
        instance_.sync_kernel()
        data_out, results_out = instance_.audit_kernel()
        commit_msg_out = instance_.audit_kernel_commits(repo.project)
    if args.testsuite.lower() == 'clamav':
        clamscan_result,clamscan_report = instance_.clamscan_code()
        instance_.write_tofile('clamscan_code_results.log',clamscan_report)
        instance_.close_file()
        if clamscan_result == 'ClamCV scan Fail!':
            result = 2
        else:
            result = 1
        instance_.upload_file(["clamscan_code_results.log","clamscan_output.log"],args.staging_ref,result,category='clamav')
    else:
        instance_.write_tofile("output.log", data_out)
        instance_.close_file()
        instance_.write_tofile("commit_msg_results.log", commit_msg_out)
        instance_.close_file()
        instance_.check_audit_results(email_to)

        result_maps = {
            'Result: Pass' : 1,
            'Result: Failed' : 2,
            'Result: Skip' : 3
        }
        for key,value in result_maps.items():
            if key in commit_msg_out:
                result = value
        instance_.upload_file(["output.log","commit_msg_results.log"],args.staging_ref,result,category='banned-words')
