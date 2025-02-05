#!/bin/bash -ex


mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions

#########################
# main

echo "Creating/updating working projects"
rm -fr kernel-staging
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-staging kernel-staging

declare kernel_version=${BASELINE}

if [[ $KERNEL == *rt* ]];then
    tag=iotg-next-${kernel_version}-preempt-rt-${STAGING_NUMBER}
    quilt_tag=iotg-next-${kernel_version}-preempt-rt-${STAGING_NUMBER}
    kernel_branch="iotg-next-rt/${kernel_version}"
    overlay_branch="iotg-next-rt/${kernel_version}-ubuntu"
    overlay_tag=iotg-next-overlay-${kernel_version}-preempt-rt-ubuntu-${STAGING_NUMBER}
else
    tag=iotg-next-${kernel_version}-linux-${STAGING_NUMBER}
    quilt_tag=iotg-next-${kernel_version}-linux-${STAGING_NUMBER}
    kernel_branch="iotg-next/${kernel_version}"
    overlay_branch="iotg-next/${kernel_version}-ubuntu"
    overlay_tag=iotg-next-overlay-${kernel_version}-ubuntu-${STAGING_NUMBER}
fi

pushd kernel-staging
    git remote add IOT_NEXT https://github.com/intel-innersource/os.linux.kernel.iot-next.git
    git reset --hard $tag
    git push origin HEAD:${kernel_branch}
    push_remote IOT_NEXT HEAD $kernel_branch
    git tag -d $tag || :
    tag $tag "IKT iotg-next kernel yocto $kernel_version $STAGING_NUMBER"
    push_tag IOT_NEXT $tag
    test $? -eq 0 && echo "EXTRA_DATA_TAG=${tag}:1:2"
    git tag -d $tag
popd

#gerenate similar prop file as release.py, used form overlay_tag_release job
echo "KERNEL_TAG=${tag}" > ds_release.prop
echo "KERNEL=${KERNEL}" >> ds_release.prop
echo "STAGING_NUMBER=${STAGING_NUMBER}" >> ds_release.prop

quilt_branch=master

echo "Creating/Update quilt"
rm -fr kernel-dev-quilt
git clone https://github.com/intel-innersource/os.linux.kernel.kernel-dev-quilt kernel-dev-quilt

pushd kernel-dev-quilt
    git checkout $quilt_tag
    quilt_branch="${KERNEL}/${kernel_version}"
    push_remote origin HEAD $quilt_branch
popd


EMAIL_TO="nex.linux.kernel.integration@intel.com"
echo " " | mail -s "please check https://cje-fm-owrp-prod05.devtools.intel.com/nex-cisv-devops00/job/NEX-Kernel/view/TechDebt/job/create-rangediff, if not ok, fill-in previous_release/target_release tags and trigger it manually" $EMAIL_TO

# release notes
release_header="[Release][${KERNEL}][$kernel_version] $STAGING_NUMBER"
echo "$release_header" > subject.txt
cat << EO_HTML > $WORKSPACE/message.html
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">

<html>
<head>
  <style type="text/css">
ol{margin:0;padding:0}table td,table th{padding:0}.c2{color:#000000;font-weight:400;text-decoration:none;vertical-align:baseline;font-size:11pt;font-family:"Arial";font-style:normal}.c5{color:#000000;text-decoration:none;vertical-align:baseline;font-size:11pt;font-family:"Arial";font-style:italic}.c6{padding-top:0pt;padding-bottom:0pt;line-height:1.15;orphans:2;widows:2;text-align:center}.c0{padding-top:0pt;padding-bottom:0pt;line-height:1.15;orphans:2;widows:2;text-align:left}.c4{color:#000000;text-decoration:none;vertical-align:baseline;font-size:11pt;font-family:"Arial";font-style:normal}.c8{color:#000000;text-decoration:none;vertical-align:baseline;font-size:14pt;font-family:"Arial";font-style:normal}.c7{background-color:#ffffff;max-width:468pt;padding:72pt 72pt 72pt 72pt}.c3{height:11pt}.c1{font-weight:700}.title{padding-top:0pt;color:#000000;font-size:26pt;padding-bottom:3pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}.subtitle{padding-top:0pt;color:#666666;font-size:15pt;padding-bottom:16pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}li{color:#000000;font-size:11pt;font-family:"Arial"}p{margin:0;color:#000000;font-size:11pt;font-family:"Arial"}h1{padding-top:20pt;color:#000000;font-size:20pt;padding-bottom:6pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h2{padding-top:18pt;color:#000000;font-size:16pt;padding-bottom:6pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h3{padding-top:16pt;color:#434343;font-size:14pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h4{padding-top:14pt;color:#666666;font-size:12pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h5{padding-top:12pt;color:#666666;font-size:11pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h6{padding-top:12pt;color:#666666;font-size:11pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;font-style:italic;orphans:2;widows:2;text-align:left}
  </style>

  <title></title>
</head>

<body class="c7">
  <p class="c6"><span class="c2" style="color:red;"> INTEL CONFIDENTIAL </span></p>
  <p class="c6"><span class="c2"><b><big>NEX Linux Kernel Team</b></big></span></p>

  <p class="c6"><span class="c2"><b><big>$release_header</b></big></span></p>

  <p class="c0 c3"></p>

  <p class="c0"><span class="c1">Release Summary:</span></p>
  <br>
  <p class="c0"><span class="c2"><b>iotg-next<b></span><span class= "c2"> release for $kernel_version is published.</span></p>
  <br>
  <p class="c0"><span class="c2">Please visit <a href="https://wiki.ith.intel.com/display/ProductionKernel/IoTG+Linux+Kernel+Overlay">https://wiki.ith.intel.com/display/ProductionKernel/IoTG+Linux+Kernel+Overlay</a></span><span class="c2"> for more info on iotg kernel overlays.</span></p>
  <br>
  <p class="c0"><span class="c2"><b>List of patches integrated</b></span> (change log)</p>
  <p class="c0"><span class="c2"><a href="https://ikt.bj.intel.com/release/quiltdiff?tag=$tag">https://ikt.bj.intel.com/release/quiltdiff?tag=$tag</a></span></p>
<br>

  <p class="c2"><b>Known Issues:</b></p>
<br>
<br>
  <p class="c2"><b>kernel source: </b><a href=https://github.com/intel-innersource/os.linux.kernel.iot-next>https://github.com/intel-innersource/os.linux.kernel.iot-next</a></p>
  <p class="c2"><b>Branch: </b> $kernel_branch</p>
  <p class="c2"><b>Tags:</b> $tag</p>
<br>
  <p class="c2"><b>kernel overlay: </b><a href=https://github.com/intel-innersource/os.linux.kernel.iot-kernel-overlay>https://github.com/intel-innersource/os.linux.kernel.iot-kernel-overlay</a></p>
  <p class="c2"><b>Branch: </b>${overlay_branch}</p>
  <p class="c2"><b>Tag: </b> ${overlay_tag}</p>
<br>
<p class="c2"><b>Kernel Packages:</b></p>
<br>
<p class="c2"><b>Ubuntu: </b><a href=http://oak-07.jf.intel.com/ikt_kernel_deb_repo/pool/main/l/>http://oak-07.jf.intel.com/ikt_kernel_deb_repo/pool/main/l/</a></p>
<p class="c2">Please refer <a href=https://wiki.ith.intel.com/pages/viewpage.action?pageId=1891212420#HowtouseIKTkerneldebpackagerepository-Part2.HowtoinstallthekerneldebpackageintoUbuntuorDebianusingiktdebrepo.>https://wiki.ith.intel.com/pages/viewpage.action?pageId=1891212420#HowtouseIKTkerneldebpackagerepository-Part2.HowtoinstallthekerneldebpackageintoUbuntuorDebianusingiktdebrepo.</a></p>
<br>
<br>
  <p class="c2"><b>QA Reports: </b><a href=https://jira.devtools.intel.com/browse/$TRACKING_JIRA>https://jira.devtools.intel.com/browse/$TRACKING_JIRA</a></p>
<br>
  <p class="c2"><b>Release note mail list:</b><br>Please subscribe to this mail list: <a href=https://eclists.intel.com/sympa/info/iotg-next>https://eclists.intel.com/sympa/info/iotg-next</a></p>
<br>
  <p class="c2"><b>Patch submit process:</b></p>
  <p class="c0"><span class="c2"><a href="https://wiki.ith.intel.com/display/ProductionKernel/Pull+Request">https://wiki.ith.intel.com/display/ProductionKernel/Pull+Request</a></span></p>
<br>
<br>
  <p class="c2"><b>More details shared on this wiki:</b></p>
  <p class="c2"><span class="c2"><a href="https://wiki.ith.intel.com/display/ProductionKernel/IOTG+Kernel+Team+Power+On+support">https://wiki.ith.intel.com/display/ProductionKernel/IOTG+Kernel+Team+Power+On+support</a></span></p>
<br>
</body>
</html>
EO_HTML

uuencode message.html message.html | mail -s "$release_header" $EMAIL_TO

