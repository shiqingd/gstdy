IFS="
"
env_opt=""
for e in $(env | grep -iE '(proxy|path)' | sed -r 's|\s||g'); do
    env_opt="$env_opt -e $e"
done
tmp_envfl=/tmp/cbe-env.$$
cat <<EO_ENV>$tmp_envfl
$(env | grep -iE '(proxy|path)' | sed -r 's|\s||g')
EO_ENV
docker run -itd --name android-cbe \
       -v /home/jenkins:/home/jenkins \
       -p 20022:22 \
       --env-file $tmp_envfl \
       cbe/android/jf:v0.1
#       otcpkt.bj.intel.com/cbe/yocto.jf:v1.0

