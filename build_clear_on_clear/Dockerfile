FROM clearlinux

ENV HTTP_PROXY http://proxy-chain.intel.com:911
ENV HTTPS_PROXY http://proxy-chain.intel.com:912

COPY id_rsa /root/.ssh/sys_oak
COPY id_rsa /root/.ssh/id_rsa
COPY id_rsa.pub /root/.ssh/sys_oak.pub
COPY id_rsa.pub /root/.ssh/id_rsa.pub
COPY .gitconfig /root/.gitconfig
COPY .gitconfig /.gitconfig
COPY .git-credentials /root/.git-credentials
COPY .git-credentials /.git-credentials
COPY config /etc/ssh/ssh_config
COPY build_clear.sh /build_clear.sh

RUN swupd update
RUN swupd bundle-add c-basic curl git openssh-server make network-basic devpkg-openssl bc diffutils devpkg-elfutils

CMD ["/bin/bash", "-ex", "build_clear.sh"]

