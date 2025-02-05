build:
	cp ~/.ssh/sys_oak id_rsa
	cp ~/.ssh/sys_oak.pub id_rsa.pub
	cp gitconfig.txt .gitconfig
	cp ~/.git-credentials .git-credentials
	echo "BRANCH=${BRANCH}\nBUILD_NUMBER=${BUILD_NUMBER}\nSCRIPT_BRANCH=${SCRIPT_BRANCH}\nPRODUCT=${PRODUCT}\nBUILD_URL=${BUILD_URL}" > env_vars.txt
	docker build --tag=clear .

run:
	mkdir -p artifacts
	docker run --rm --env-file ./env_vars.txt \
	-v ${PWD}/artifacts:/artifacts clear
