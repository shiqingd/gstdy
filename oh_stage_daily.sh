#!/bin/bash -ex

datetime=$(TZ='Asia/Shanghai' date +%y%m%d)T$(TZ='Asia/Shanghai' date +%H%M%S)Z
OHOS_MANIFEST=ohos-4.1-${datetime}-manifest.xml
STAGING_REV=OpenHarmony-4.1-Daily-${datetime}

echo "MANIFEST_BRANCH=${MANIFEST_BRANCH}" > oh_daily_staging_build.prop
echo "OHOS_MANIFEST=${OHOS_MANIFEST}" >> oh_daily_staging_build.prop
echo "STAGING_REV=${STAGING_REV}" >> oh_daily_staging_build.prop


