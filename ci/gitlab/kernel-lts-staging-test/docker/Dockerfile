FROM ubuntu:xenial AS env
USER root

#add user
ENV http_proxy "http://child-prc.intel.com:913"
ENV https_proxy "http://child-prc.intel.com:913"
RUN apt-get update && apt-get install -y bash \
                                         python3 \
                                         python3-dev \
                                         openssh-server \
                                         sudo \
                                         vim \
                                         ca-certificates \
                                         wget \
                                         python3-pip \
                                         busybox \
                                         git
ENV APP_DIR=/build/ \
    SHELL=/bin/bash \
    NEW_USER=sys_oak \
    NEW_PASSWD=intel#123 \
    NEW_UID=1000 \
    NEW_GID=100 \
    GERRIT_USER=sys_oak \
    GERRIT_PASSWD=xxx \ 

#note this is a dummy password, use your own user and passwd instead
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8
ENV PATH=$APP_DIR/bin:$PATH \
    HOME=/home/$NEW_USER
ADD bin/fix-permissions /usr/local/bin/fix-permissions
RUN useradd --uid $NEW_UID --system --gid $NEW_GID --create-home --shell $SHELL $NEW_USER && \
    echo "$NEW_PASSWD\n$NEW_PASSWD" | passwd $NEW_USER && \
    usermod -aG sudo $NEW_USER && \
    mkdir -p $APP_DIR && chown $NEW_USER:$NEW_GID $APP_DIR && chmod g+w /etc/passwd /etc/group && \
    fix-permissions $HOME && fix-permissions $APP_DIR

#chuser and setup code base
RUN whoami
#add ssh key(only needed for production environment)
#clone code
RUN git clone https://$GERRIT_USER:$GERRIT_PASSWD@gitlab.devtools.intel.com/linux-kernel-integration/gitlab-ci /build/tools
CMD [ "bash" ]

