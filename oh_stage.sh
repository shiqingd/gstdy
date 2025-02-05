#!/bin/bash -ex

datetime=$(TZ='Asia/Shanghai' date +%y%m%d)T$(date +%H%M%S)Z
OHOS_MANIFEST=ohos-4.1-${datetime}-manifest.xml
STAGING_REV=OpenHarmony-4.1-Staging-${datetime}
tags=""
test $? -eq 0 && tags="${STAGING_REV}:1:1"

echo "MANIFEST_BRANCH=${MANIFEST_BRANCH}" > oh_staging_build.prop
echo "OHOS_MANIFEST=${OHOS_MANIFEST}" >> oh_staging_build.prop
echo "STAGING_REV=${STAGING_REV}" >> oh_staging_build.prop

for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done
