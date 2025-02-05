#!/usr/bin/env python
"""Author: Yifan Li
   Ssh Session module, include ShellSession
"""

import logging
import pexpect
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# from util.utils import format_asc_log

SSH_NEWKEY_RE = r'Are you sure you want to continue connecting \(yes/no\)\?'
SSH_WRONG_PWD = 'Permission denied, please try again.'
PING_STATUS_RE = re.compile(r'(?P<transmit>[1-9][0-9]*) packets transmitted, ' +
                            r'(?P<receive>[1-9][0-9]*) received')


def format_asc_log(new_line):
    """Change ascii format output to python str format line"""
    replacements = {
        '\n\n': '\n',  # double lines to single
        '\r': '',  # change \r\n to \n
        '"': '\\\"',  # escape double quotes for YAML syntax
        '\x1b': ''  # remove escape control characters
    }
    logger.debug("Format input: %s", new_line)
    for key, value in replacements.items():
        new_line = new_line.replace(key, value)
    return new_line


class SSHConnectionError(Exception):
    """ SSH connection failed error"""
    error_code = 1
    error_help = "SSH connection error"
    error_type = "Connection"


class SSHSession():
    """ SSH session class"""

    def __init__(self, user, host, password=None, shell_prompt=None, port=22):
        self.name = "SSHSession"
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        self.user = user
        self.host = host
        self.port = port
        self.logger.debug("Connecting to %s@%s on port %s", \
                          self.user, self.host, str(self.port))
        # for clear linux, expect r'~', 'Password:'
        self.login_prompt_str = r':?~'
        self.pwd_prompt_str = '(\'s )?[Pp]assword:'
        self.shell_prompt_str = shell_prompt if shell_prompt \
            else r"host_session\$"
        self.session_alive = False
        self.session = self.start_session(password)
        if not self.session:
            raise SSHConnectionError("Session not established!")
        if not self.set_shell_prompt():
            raise SSHConnectionError("Session promt setup failed!")

    def start_session(self, password=None):
        """ try connect to host with given param
            return session instance or None(connect failure)
        """
        start_cmd = "ssh -p %s %s@%s" % (str(self.port), self.user, self.host)
        session_process = pexpect.spawn(start_cmd)
        o = session_process.expect([pexpect.TIMEOUT, pexpect.EOF,
                                    self.login_prompt_str, self.pwd_prompt_str,
                                    SSH_NEWKEY_RE])
        if o <= 1:
            # Timeout
            self.logger.error('SSH login failed. Here is what SSH said:')
            self.logger.error(session_process.before)
            return None
        elif o == 2:
            # SSH login success, no password required
            self.logger.debug('Login success')
            return session_process
        elif o == 4:
            # SSH does not have the public key. Just accept it.
            session_process.sendline('yes')
            session_process.expect(self.pwd_prompt_str)
        # do password input
        if not password:
            self.logger.error('No password input!')
            return None
        self.logger.debug('Input password.')
        session_process.sendline(password)
        pwd_correct = session_process.expect([SSH_WRONG_PWD,
                                              self.login_prompt_str])

        if pwd_correct == 0:
            self.logger.error('Permission denied, password not correct.')
            return None
        else:
            self.logger.debug('Login success')
            self.session_alive = True
            return session_process

    def close_session(self):
        self.logger.debug("Session closed as required.")
        self.session.close()
        self.session_alive = False
        return

    def clean_session_buffer(self):
        """ Clean session output buffer in case of interrrupt other messages"""
        self.logger.debug("Clean session buffer.")
        index = 0
        while index == 0:
            index = self.session.expect(['.+',
                                         pexpect.EOF,
                                         pexpect.TIMEOUT],
                                        timeout=1)

    def set_shell_prompt(self):
        """ Set shell prompt to make pexpect.expect works more better
        """
        self.logger.debug("Set shell prompt.")
        self.clean_session_buffer()
        set_prompt_cmd = 'export PS1="%s"' % self.shell_prompt_str
        self.session.sendline(set_prompt_cmd)
        set_pass = self.session.expect([self.shell_prompt_str, pexpect.EOF],
                                       timeout=1)
        return True if set_pass == 0 else False

    def sendcommand(self, command, timeout=-1):
        """ Send command and get all output
            timeout = -1 means use pexpect timeout"""
        self.logger.debug("Send command: %s", command)
        self.session.sendline(command)
        self.session.expect([self.shell_prompt_str, pexpect.EOF], timeout=timeout)
        output = format_asc_log(self.session.before.decode('utf-8'))
        output_lines = output.split('\n')
        return output_lines[1:-1], output_lines[0]

    def __scp__(self, local, destination, password, recursive, timeout=-1):
        """internal function, wrapps of scp"""
        recursive_signal = "-r" if recursive else ""
        scp_command = "scp %s %s %s" % (recursive_signal, local, destination)
        # TODO: Change this to be a static method
        self.logger.debug("Scp command: %s", scp_command)
        process = pexpect.spawn(scp_command)
        o = process.expect([pexpect.TIMEOUT, pexpect.EOF,
                            self.pwd_prompt_str, SSH_NEWKEY_RE],
                           timeout=10)
        if o == 3:
            process.sendline('yes')
            process.expect(self.pwd_prompt_str)
            self.logger.debug("Hit SSH_NEWKEY regex in scp.")
        if not password:
            self.logger.error('No password input!')
            return ["Scp failed!"]
        self.logger.debug('Input password.')
        process.sendline(password)
        pwd_correct = process.expect([SSH_WRONG_PWD,
                                      pexpect.EOF], timeout=timeout)
        if pwd_correct == 0:
            raise SSHConnectionError("Scp could not connect.")
        logs = format_asc_log(process.before.decode('utf-8')).split('\n')[:-1]
        # remove empty item at list end
        return logs

    def scp_send(self, local, remote,
                 password=None, recursive=False, timeout=-1):
        """ This method wraps 'scp <ORIGIN> <USER>@<HOST>:<DESTINATION>'"""
        destination = "%s@%s:%s" % (self.user, self.host, remote)
        origin = local
        logs = self.__scp__(origin, destination, password,
                            recursive, timeout)
        self.logger.debug("Send file from local %s to remote %s.",
                          origin,
                          destination)
        for l in logs:
            self.logger.debug("Scp send: %s", l)
        return "100%" in logs[-1]

    def scp_get(self, local, remote,
                password=None, recursive=False, timeout=-1):
        """ This method wraps 'scp <USER>@<HOST>:<ORIGIN> <DESTINATION>'"""
        origin = "%s@%s:%s" % (self.user, self.host, remote)
        destination = local
        logs = self.__scp__(origin, destination, password,
                            recursive, timeout)
        self.logger.debug("Get file to local %s from remote %s",
                          destination,
                          origin)
        for l in logs:
            self.logger.debug("Scp get: %s", l)
        return "100%" in logs[-1]

    def __ping__(self, timeout=2, count=1):
        """ Ping remote host, return logs """
        ping_cmd = "ping %s -W %d -c %d" % (self.host, timeout, count)
        self.logger.debug("Ping: %s", ping_cmd)
        p = pexpect.spawn(ping_cmd)
        o = p.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=timeout + 1)
        # ensure expect could return
        if o == 1:
            logs = ["Ping command timeout!"]
        else:
            logs = format_asc_log(p.before.decode('utf-8')).split('\n')[:-1]
        return logs  # remove empty item at end of list

    def check_hang(self, timeout=2, count=1):
        """ Check remote host hang or not """
        host_alive = False
        self.logger.debug("Check host %s hang or not.", self.host)
        lines = self.__ping__(timeout=timeout, count=count)
        if len(lines) < 2:
            # In this case the single line mostly like below:
            #    ping: unknown host <HOSTNAME>
            #    ping: bad number of packets to transmit.
            # these are error msg when ping <HOST>, so return False
            self.logger.error("Ping host %s error, it says:", self.host)
            host_alive = False
        else:
            ping_result = PING_STATUS_RE.search(lines[-2])
            # ping normal lines like below:
            #   PING <HOST> (<IP>) 56(84) bytes of data.
            #   64 bytes from <HOST> (<IP>): icmp_seq=1 ttl=63 time=0.725 ms
            #   --- <HOST> ping statistics ---
            #   1 packets transmitted, 1 received, 0% packet loss, time 0ms
            #   rtt min/avg/max/mdev = 0.725/0.725/0.725/0.000 ms
            # so we see if line[-2] matches count then <HOST> works good
            if not ping_result:
                self.logger.error("Ping host %s unexpected output, it says:",
                                  self.host)
                host_alive = False
            else:
                t, r = ping_result.group("transmit"), \
                       ping_result.group("receive")
                self.logger.debug("Packet transmitted: %s, received: %s", t, r)
                if int(r) < count:
                    self.logger.error("Ping host %s packets lost, it says:",
                                      self.host)
                    host_alive = False
                elif int(r) > count:
                    self.logger.error("WTH this should not happen!")
                    self.logger.error("Ping host %s packets more than send!",
                                      self.host)
                    host_alive = False
                else:
                    self.logger.debug("Ping host %s received all packets.",
                                      self.host)
                    host_alive = True
        if host_alive:
            for l in lines:
                self.logger.debug("Check hang output: %s", l)
        else:
            for l in lines:
                self.logger.error("Check hang output: %s", l)
        return host_alive
