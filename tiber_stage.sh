#!/bin/bash -ex

#qingdong.shi@intel.com
#2024-Nov-05

#generate datestring and STAGING_REV(actually, STAGING_REV is tag)
if [[ $DATE_TIME == "none" ]]; then
    OPT_cve=false
    datetime=$(TZ='Asia/Shanghai' date +%y%m%d)T$(date +%H%M%S)Z
else
    OPT_cve=true
    datetime=${DATE_TIME}
fi

STAGING_REV=lts-v${BASELINE}-tiber-dev-${datetime}
STAGING_REV_CVE=lts-v${BASELINE}-tiber-dev-cve-${datetime}
KERNEL=6.6lts
if [[ $BASELINE == *rt* ]] ; then
    STAGING_REV=lts-v${BASELINE}-tiber-dev-preempt-rt-${datetime}
    STAGING_REV_CVE=lts-v${BASELINE}-tiber-dev-preempt-rt-cve-${datetime}
    KERNEL=6.6rt
fi
echo "STAGING_REV=$STAGING_REV"
echo "STAGING_REV_CVE=$STAGING_REV_CVE"
echo "KERNEL=$KERNEL"

rm -fr os.linux.kernel.kernel-lts-staging
rm -fr kernel-lts-cve
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-staging --branch "${TIBER_BRANCH}"
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve     kernel-lts-cve

if [[ $OPT_cve == true ]];then
  cd kernel-lts-cve
    git checkout 6.6

    #create tag for CVE content
    echo "tag_name is $STAGING_REV_CVE"
    git tag "${STAGING_REV_CVE}" -m ""
    git push --dry-run origin "${STAGING_REV_CVE}"
    git push origin "${STAGING_REV_CVE}"
  cd -
fi

if [[ $OPT_cve == "false" ]]; then
  pushd os.linux.kernel.kernel-lts-staging
    git tag "${STAGING_REV}" -m ""
    git push --dry-run origin "${STAGING_REV}"
    git push origin "${STAGING_REV}"
  popd

  rsync -a  --exclude '.*' os.linux.kernel.kernel-lts-staging/* ./${STAGING_REV}
  tar -cvzf ${STAGING_REV}.tar.gz ${STAGING_REV}
  ##curl -u username:passwd -X PUT -T xxx.tar.gz "https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES/xxx.tar.gz"
  curl --netrc-file /home/jenkins/.netrc -X PUT -T ${STAGING_REV}.tar.gz "https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES/${STAGING_REV}.tar.gz"

  tags=""
  test $? -eq 0 && tags="${STAGING_REV}:1:1"

else

  pushd os.linux.kernel.kernel-lts-staging
    #create cve-tag for compiling/build
    git quiltimport --series=../kernel-lts-cve/tiber/patches/series --patches=../kernel-lts-cve/tiber/patches/
    echo "cve tag_name is $STAGING_REV_CVE"
    git tag "${STAGING_REV_CVE}" -m ""
	git push --dry-run origin "${STAGING_REV_CVE}"
    git push origin "${STAGING_REV_CVE}"
    test $? -eq 0 && tags="$tags ${STAGING_REV_CVE}:3:1"
  popd

  rsync -a  --exclude '.*' os.linux.kernel.kernel-lts-staging/* ./${STAGING_REV_CVE}
  tar -cvzf ${STAGING_REV_CVE}.tar.gz ${STAGING_REV_CVE}
  #curl --netrc-file /home/jenkins/.netrc -X PUT -T ${STAGING_REV_CVE}.tar.gz "https://af01p-png-app03.devtools.intel.com/artifactory/tiberos-packages-png-local/CM2/SOURCES/${STAGING_REV_CVE}.tar.gz"
fi

rm -f *.prop
echo "datetime=${datetime}" > tiber_staging_build.prop
echo "BASELINE=${BASELINE}" >> tiber_staging_build.prop

if [[ $OPT_cve == "false" ]]; then
  echo "STAGING_REV=${STAGING_REV}" >> tiber_staging_build.prop
  echo "STAGING_REV=$STAGING_REV" > ClamAV_Scan.prop
else
  echo "STAGING_REV=${STAGING_REV_CVE}" >> tiber_staging_build.prop
  echo "STAGING_REV=${STAGING_REV_CVE}" > ClamAV_Scan.prop
fi

if [[ $BASELINE == *rt* ]] ; then
    mv tiber_staging_build.prop tiber_staging_build_RT.prop
fi


echo "KERNEL=$KERNEL" >> ClamAV_Scan.prop


for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

