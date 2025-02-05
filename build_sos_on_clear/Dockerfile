FROM acrn/docker:latest

ENV HTTP_PROXY http://proxy-chain.intel.com:911
ENV HTTPS_PROXY http://proxy-chain.intel.com:912

#Install all needed packages
RUN swupd bundle-add --allow-insecure-http c-basic curl git openssh-server make network-basic devpkg-openssl
RUN swupd bundle-add --allow-insecure-http bc diffutils devpkg-elfutils python-basic cpio dev-utils file texinfo patch which
RUN swupd bundle-add --allow-insecure-http unzip

# Additional dependencies found by trial and error.

RUN swupd bundle-add --allow-insecure-http devpkg-systemd
RUN swupd bundle-add --allow-insecure-http devpkg-e2fsprogs
RUN swupd bundle-add --allow-insecure-http devpkg-libxml2
RUN swupd bundle-add --allow-insecure-http devpkg-util-linux
RUN swupd bundle-add --allow-insecure-http devpkg-libevent
RUN swupd bundle-add --allow-insecure-http devpkg-libusb
RUN swupd bundle-add --allow-insecure-http devpkg-libpciaccess
#RUN swupd bundle-add --allow-insecure-http lz4
RUN swupd bundle-add --allow-insecure-http sudo
RUN swupd bundle-add --allow-insecure-http devpkg-telemetrics-client
RUN swupd bundle-add --allow-insecure-http storage-utils
RUN swupd bundle-add --allow-insecure-http os-core-dev

# Python2 needs to be in python's position.
RUN cp /bin/python2 /bin/python

# Artifacts will be where we copy the finished images to.
RUN mkdir /artifacts

COPY gitconfig.txt /root/.gitconfig

# Create the ssh folder for git cloning
COPY id_rsa /root/.ssh/sys_oak
COPY id_rsa /root/.ssh/id_rsa
COPY .gitconfig /root/.gitconfig
COPY .gitconfig /.gitconfig
COPY .git-credentials /root/.git-credentials
COPY .git-credentials /.git-credentials
COPY config /etc/ssh/ssh_config
COPY build_sos.sh /build_sos.sh
COPY disable-stringop-truncation-warnings-in-tools.patch \
     /disable-stringop-truncation-warnings-in-tools.patch

# Envs have to be copied into the container.
COPY env_vars.txt /env_vars.txt

# Copy script for getting URL of flashfile.
COPY get_flashfiles.py /get_flashfiles.py


# Copy gitproxy

COPY gitproxy.sh /root/bin/gitproxy.sh

# Install the Python dependency kconfiglib
RUN pip3 --proxy http://proxy-chain.intel.com:911 install kconfiglib

# Packages for get_flashfiles.py
RUN pip3 --proxy http://proxy-chain.intel.com:911 install beautifulsoup4

CMD ["/bin/bash", "-ex", "build_sos.sh"]

