#!/bin/bash

export GIT_DISCOVERY_ACROSS_FILESYSTEM=1
export GIT_LFS_SKIP_SMUDGE=1
export GIT_SSL_NO_VERIFY=1

function get_domain() {
    # return value
    local rv=""
    local hostname=$(hostname)
    if [ -z "$hostname" ]; then
        echo "error: cannot get hostname"
        return
    fi
    case $hostname in
      *-bj-*|mhw*)
          rv="bj.intel.com"
          ;;
      *-sh-*)
          rv="sh.intel.com"
          ;;
      iotgikt*)
          rv="hf.intel.com"
          ;;
      nece-kernel*|oak*)
          rv="jf.intel.com"
          ;;
      *)
          net="$(ip a | grep '\s*inet 10\.' | awk '{print $2}')"
          case "$net" in
            10.238.*|10.240.*)
              rv="bj.intel.com"
              ;;
            10.67.*)
              rv="sh.intel.com"
              ;;
            10.23.*)
              rv="hf.intel.com"
              ;;
            10.72.*)
              rv="jf.intel.com"
              ;;
          esac
          ;;
    esac
    eval "$1=\"$rv\""
}

get_domain domain
case "$domain" in
  bj.intel.com|sh.intel.com)
    proxy_server="child-prc.intel.com"
    def_port=913
    https_port=912
    ;;
  *)
    proxy_server="proxy-chain.intel.com"
    def_port=911
    https_port=912
    ;;
esac

export http_proxy="http://${proxy_server}:${def_port}"
export https_proxy="http://${proxy_server}:${https_port}"
export ftp_proxy="ftp://${proxy_server}:${def_port}"
export all_proxy="http://${proxy_server}:${def_port}"
export socks_proxy="socks://${proxy_server}:1080"
export no_proxy="intel.com,.intel.com,10.0.0.0/8,192.168.0.0/16,localhost,127.0.0.0/8,134.134.0.0/16,172.16.0.0/20"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export FTP_PROXY="$ftp_proxy"
export ALL_PROXY="$all_proxy"
export SOCKS_PROXY="$socks_proxy"
export NO_PROXY="$no_proxy"
export DATABASE_HOST=oak-pkpt.ostc.intel.com

# run_docker <arg1> <arg2> <arg3> [<arg4>]
#   arg1: docker image
#   arg2: docker instance name
#   arg3: job script that is going to run in docker
#   arg4: docker options
function run_docker () {

    declare envfl=/tmp/docker-env.$$
    env | awk -F= '{print $1}' > $envfl
    newgrp docker
    docker run \
        -a stdin \
        -a stdout \
        -a stderr  \
        --rm \
        -u jenkins \
        --name $2 \
        --privileged=true \
        -v /dev:/dev \
        -v /home/jenkins:/home/jenkins \
        -v $3:$3 \
        --env-file $envfl \
        -w $WORKSPACE \
        $4 \
        $1 $3
        
    rm -f $envfl
}

# run_docker_cje <arg1> <arg2> <arg3> [<arg4>]
#   arg1: docker image
#   arg2: docker instance name
#   arg3: job script that is going to run in docker
#   arg4: docker options
function run_docker_cje () {

    declare envfl=/tmp/docker-env.$$
    env | awk -F= '{print $1}' > $envfl
    newgrp docker
    docker run \
        -a stdin \
        -a stdout \
        -a stderr  \
        --rm \
        --network host \
        -u jenkins \
        --name $2 \
        -v /home/jenkins:/home/jenkins \
        -v $3:$3 \
        --env-file $envfl \
        -w $WORKSPACE \
        $4 \
        $1 $3
    rm -f $envfl
}

# rm_docker <arg1>
#   arg1: docker instance name
function rm_docker() {
    docker rm $1
}

# dockerize <arg1> <arg2> [<arg3>]
#   arg1: docker image
#   arg2: temp job script
#   arg3: (optional) docker options
function dockerize() {
    declare docker_img=$1
    declare job_script=$2
    declare docker_name=${docker_img//[\/:]/-}.$$

    chmod +x $job_script
    trap "rm -f $job_script" EXIT
    run_docker $docker_img $docker_name $job_script "$3"
}

# dockerize_cje <arg1> <arg2> [<arg3>]
#   arg1: docker image
#   arg2: temp job script
#   arg3: (optional) docker options
function dockerize_cje() {
    declare docker_img=$1
    declare job_script=$2
    declare docker_name=${docker_img//[\/:]/-}.$$

    chmod +x $job_script
    trap "rm -f $job_script" EXIT
    run_docker_cje $docker_img $docker_name $job_script "$3"
}
