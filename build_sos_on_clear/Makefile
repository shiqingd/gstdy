ENV_VARS = ${WORKSPACE}/env_vars.txt
ARTIFACTS_DIR = ${WORKSPACE}/artifacts


build:
	cp ~/.ssh/sys_oak id_rsa
	cp ~/.ssh/sys_oak sys_oak
	cp ~/.gitconfig .gitconfig
	cp ~/.git-credentials .git-credentials
	rm -f ${ENV_VARS}
	touch ${ENV_VARS}
	rm -rf ${ARTIFACTS_DIR}
	echo "BRANCH=${BRANCH}" >> ${ENV_VARS}
	echo "PRODUCT=${PRODUCT}" >> ${ENV_VARS}
	# Docker can't reuse, unfortunately.
	echo "opt_reuse=no" >> ${ENV_VARS}
	echo "BASE_URL=${BASE_URL}" >> ${ENV_VARS}
	echo "HYPERVISOR_TAG=${HYPERVISOR_TAG}" >> ${ENV_VARS}
	echo "EBTOOL_TAG=${EBTOOL_TAG}" >> ${ENV_VARS}
	echo "SYS_OAK_CRED_AD=${SYS_OAK_CRED_AD}" >> ${ENV_VARS}
	docker build --tag=sos .

run:
	mkdir -p ${ARTIFACTS_DIR}
	docker run --privileged --rm --env-file ${WORKSPACE}/env_vars.txt \
	-v ${ARTIFACTS_DIR}:/artifacts sos 
