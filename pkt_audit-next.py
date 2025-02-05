import pyshell
import sys
import re
import smtplib
import os
from jinja2 import Environment, FileSystemLoader
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

'''
it should clone audit from clr
if should clone kernel-bkc

if already clone 
git fetch --all
git pull

checkout kernel-bkc branch 
run audit from base(4.19-rc7) to branch (staging/mainline-tracking-android-181012T051938Z)
save results in a file
email results

'''


class audit_pkt():
    def __init__(self, home='', kernel_loc='', kernel_remote='', kernel_version='', staging_branch=''):
        self.repository = kernel_remote + kernel_loc
        self.kernel_version = kernel_version
        self.kernel_location = home + '/' + kernel_loc
        self.kernel_tf_name = kernel_loc
        self.dir_home = home
        self.staging_branch = staging_branch
        self.audit_remote = 'http://kojiclear.jf.intel.com/cgit/projects/clr-github-publish-packages'
        self.audit_loc = home + '/clr_audit'
        self.dashell = pyshell.PyShell()
        self.output_file = ''
        self.results_file = ''
        self.data_out = ''
        self.output_code = ''
        self.output_commit_msg = ''
        self.output_commit_msg_html = ''

    def print_vars(self):
        print("Repo:", self.repository)
        print("kernel version: ", self.kernel_version)
        print("kernel location: ", self.kernel_location)
        print("staging branch: ", self.staging_branch)
        print("audit remote: ", self.audit_remote)
        print("audit location: ", self.audit_loc)

    def decode_print(self, dashell_out):
        if dashell_out[0] == 0 or dashell_out[0] == 1:
            return dashell_out[1].decode("utf-8") + dashell_out[2].decode("utf-8")
        elif dashell_out[0] == 128:
            return dashell_out[2].decode("utf-8")

    def sync_audit(self):
        self.data_out += self.decode_print(self.dashell.cmd(
            'git', 'clone', self.audit_remote, self.audit_loc, wd=self.dir_home))
        self.data_out += self.decode_print(self.dashell.cmd(
            'git', 'reset', '--hard', wd=self.audit_loc))
        self.data_out += self.decode_print(self.dashell.cmd(
            'git', 'fetch', '--all', wd=self.audit_loc))
        self.data_out += self.decode_print(
            self.dashell.cmd('git', 'pull', wd=self.audit_loc))

    def sync_kernel(self):
        self.data_out += self.decode_print(self.dashell.cmd('git', 'clone', self.repository, self.kernel_location, wd=self.dir_home))
        self.data_out += self.decode_print(self.dashell.cmd('git', 'clean','-xdf', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd('git', 'reset','--hard', 'origin/master', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd('git', 'fetch', '--all', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd('git', 'fetch', '--tags', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd('git', 'checkout', 'master', wd=self.kernel_location))
        self.data_out += self.decode_print(self.dashell.cmd('git', 'pull', wd=self.kernel_location))

    def audit_kernel(self):
        self.data_out += self.decode_print(self.dashell.cmd(
            'git', 'checkout', self.staging_branch, wd=self.kernel_location))
        if self.kernel_tf_name == 'kernel-lts-quilt' or self.kernel_tf_name == 'kernel-dev-quilt':
            print('Running quilt audit.')
            self.output = self.decode_print(self.dashell.cmd(self.audit_loc + '/audit','patches', wd=self.kernel_location))
        else:
            self.output = self.decode_print(self.dashell.cmd(self.audit_loc + '/audit', '-r', self.kernel_version + '..HEAD', '.', wd=self.kernel_location))
        if self.output == '':
            self.output = 'Audit from ' + self.audit_remote + \
                ' did not find any banned words IN Code between: ' + \
                self.kernel_version + '..' + self.staging_branch + '\n\n'
        return self.data_out, self.output
    
    def audit_kernel_commit_msg(self):
        banned_words = self.open_banned_words()
        text_output=''
        text_output_html=''		
        for word_count in range(len(banned_words)):
            banned_word = banned_words[word_count].split('\n')[0]
            reg_ex_banned_word = banned_word.replace('.','\.')
            git_log_results = self.decode_print(self.dashell.cmd('git','log', self.kernel_version + '..HEAD','--grep='+reg_ex_banned_word, wd=self.kernel_location))
            base_text=self.kernel_location + "/:"
            if (git_log_results != '' and banned_word != ''):
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
                    self.output_commit_msg+=text_output + '\n'
                    self.output_commit_msg_html+=text_output_html + '<br>'
        if(text_output == ''):
            self.output_commit_msg = 'Banned words Audit did not find any banned words IN Commit Messages between: ' + \
            self.kernel_version + '..' + self.staging_branch + '\n'
        return self.output_commit_msg

    def open_banned_words(self):
        banned_words_data = open(self.audit_loc + "/banned-words", 'r')
        return banned_words_data.readlines()
        
    def send_email(self, sender, subject, receivers, template, quilt_results,code_total,quilt_total,msg_total, _staging):
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
        msg.attach(MIMEText(templ.render(code_results=self.output,msg_results=self.output_commit_msg_html, \
            quilt_results=quilt_results,code_total=code_total,quilt_total=quilt_total,msg_total=msg_total, staging=_staging), 'html'))
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
        
    def check_audit_results(self, email_to, code_total, msg_total, quilt_total = 'N/A', quilt_results = 'Quilt scan skipped.'):
        print("CODE scan results send to email(s)", email_to)
        instance_.send_email('sys_oak@intel.com', 'PKT Audit Banned Words: ', email_to, 'audit_email-next.j2', \
            quilt_results,code_total,quilt_total,msg_total, self.staging_branch)

    
    def write_tofile(self, file_name, data):
        self.p_file = open(file_name, 'w+')
        self.p_file.writelines(data)

    def close_file(self):
        self.p_file.close()


if __name__ == '__main__':
# Example '/home/randy/Desktop'
    home = sys.argv[1]

# example kernel-lts2018, kernel-bkc, kernel-coe-tracker
    kernel_repo = sys.argv[2]

    
# Tag for staging example: lts-v4.14.109-preempt-rt-190415T161515Z
    staging_tag = sys.argv[3]

# example v4.14.109
    kernel_version = sys.argv[4]

# repo project for quilt example : kernel_repo_quilt = 'kernel-lts-quilt' or kernel-dev-quilt
    kernel_repo_quilt = sys.argv[5]

#Email to notify. set to given param else use default
    if (sys.argv[6] != 'none'):
        email_to = str(sys.argv[6]).split(',')
    else:
        email_to=['ranjan.dutta@intel.com','cheon-woei.ng@intel.com','qingdong.shi@intel.com']

    kernel_remote = 'ssh://git@gitlab.devtools.intel.com:29418/linux-kernel-integration/'
    # set quilt variables to default
    total_banned_quilt=0
    results_out_quilt=''
    #if there are no quilts skip
    if  kernel_repo_quilt != 'none':
        instance_quilt = audit_pkt(home, kernel_repo_quilt, kernel_remote,kernel_version, staging_tag)
        instance_quilt.print_vars()
        instance_quilt.sync_kernel()
        data_out_quilt, results_out_quilt = instance_quilt.audit_kernel()
        instance_quilt.write_tofile("quilt_output.log", data_out_quilt)
        instance_quilt.close_file()
        #if any banned words subtract 1 for intro
        if results_out_quilt.count('banned word') >= 1:
            total_banned_quilt = results_out_quilt.count('banned word') - 1
            print("Quilt found banned words")
        else:
            print("Quilt did NOT found banned words")
            total_banned_quilt = results_out_quilt.count('banned word')
            results_out_quilt = 'Banned words Audit did not find any banned words in quilt.'
        instance_quilt.write_tofile("quilt_code_results.log", results_out_quilt)
        instance_quilt.close_file()

    instance_ = audit_pkt(home, kernel_repo, kernel_remote, kernel_version, staging_tag)
    instance_.print_vars()
    instance_.sync_audit()
    instance_.sync_kernel()
    data_out, results_out = instance_.audit_kernel()
    commit_msg_out = instance_.audit_kernel_commit_msg()
    
    #if any banned words subtract 1 for intro
    if results_out.count('banned word') >= 1:
        total_banned_source = results_out.count('banned word') - 1
    else:
        total_banned_source = results_out.count('banned word')

    total_banned_msg = commit_msg_out.count('banned word')
    instance_.write_tofile("code_output.log", data_out)
    instance_.close_file()
    instance_.write_tofile("code_results.log", results_out)
    instance_.close_file()
    instance_.write_tofile("commit_msg_results.log", commit_msg_out)
    instance_.close_file()
    if  kernel_repo_quilt != 'none':
        instance_.check_audit_results(email_to,total_banned_source,total_banned_msg,total_banned_quilt,results_out_quilt)
    else:
        instance_.check_audit_results(email_to,total_banned_source,total_banned_msg)
