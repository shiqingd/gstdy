echo "Docker image name:$1"
echo "Docker image version:$2"
echo "Start build with local"
docker build --no-cache --tag=$1:$2 .
echo "Build done!"
docker tag $1:$2 otcpkt.bj.intel.com/gitlab-ci/$1:$2

echo "Tag to docker habor done"
docker push otcpkt.bj.intel.com/gitlab-ci/$1:$2

echo "Push to habor done"
