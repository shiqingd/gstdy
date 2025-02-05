FROM ubuntu:focal AS env
USER root

#skip tzdata congifuration
ENV TZ=Asia/Beijing
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
ENV http_proxy "http://child-prc.intel.com:913"
ENV https_proxy "http://child-prc.intel.com:913"
RUN apt-get update && apt-get install -y tzdata
#to skip tzdata configuration
RUN apt-get install -y bash python3 python3-dev \
                       openssh-server sudo vim \
                       ca-certificates wget python3-pip \
                       busybox git
ENV APP_DIR=/build/ \
    SHELL=/bin/bash \
    CI_REPO_USERNAME=gitlab+deploy-token-630 \
    CI_REPO_CRED=xxx
#note this is a dummy password, use your own user and passwd instead
#    LC_ALL=en_US.UTF-8 \
#    LANG=en_US.UTF-8 \
#    LANGUAGE=en_US.UTF-8

#chuser and setup code base
RUN whoami
#add ssh key(only needed for production environment)
#clone code
RUN git clone https://$CI_REPO_USERNAME:$CI_REPO_CRED@gitlab.devtools.intel.com/linux-kernel-integration/gitlab-ci.git /build/tools


CMD [ "bash" ]

