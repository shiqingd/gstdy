#!/bin/bash -ex

mydir="$(cd $(dirname $0); pwd)"
source $mydir/bkc_common.sh # Include library of common build functions
kernel_source_folder=$mydir/kernel-lts-staging
kernel_config_folder=$mydir/kernel-config
kernel_cve_folder=$mydir/kernel-lts-cve
kernel_quilt_folder=$mydir/kernel-dev-quilt
exit_usage() {
        cat << EOF >&2

USAGE:
	$0 -t <staging tag> -d <dry run> -p <push internal release> [ -n ]
	staging tag = only the non sandbox/cve staging tag is accepted
    dry run = true/false
    push internal release = true/false
	h|? = help (this screen)

EOF
exit 1
}

# Given the staging branch, we check to see if the tags associated with
# the branch have "sandbox" in them. If so, we abort.
# This is intended as a failsafe to prevent absentminded engineers from
# thinking "Oh, looks like another staging branch for release, let's
# release it."
check_for_sandbox_tags() {
	arg_datetime=$1
    if git tag | grep $arg_datetime | grep "sandbox"
	then
	    die "Error! Sandbox tag found! Aborting!"
	else
	    echo "No sandbox tags found. Continuing..."
	fi
}

#########################
# main


android_push=false
android_dry_run=false
OPT_exit_only=false
while getopts "t:d:p:h?" OPTION; do
	case $OPTION in
		t)
			android_tag=${OPTARG}
			if [ $android_tag == '' ]; then
				OPT_exit_only=true
			fi
			;;
		d)
			android_dry_run=${OPTARG}
			;;
		p)
			android_push=${OPTARG}
			;;
		h|?)
			OPT_exit_only=true
			;;
	esac
done
$OPT_exit_only && exit_usage

echo "Creating/updating working projects"
init_kernel_lts_staging

declare cve_true=`echo "${android_tag}" | grep -c "cve"`
declare sandbox_true=`echo ${android_tag} | grep -c "sandbox"`
declare android_s_true=`echo ${android_tag} | grep -c "android_s"`
echo 'cve Tag: ' $cve_true
echo 'sandbox Tag : ' $sandbox_true 
if [ ${cve_true} == '1' ] || [ ${sandbox_true} == '1' ] || [ ${android_s_true} != '1' ]; then
	exit_usage
fi

tag_timestamp=`echo ${android_tag} | grep -o -P '[0-9]{6}T[0-9]{6}Z'`
tag_kernel_version=`echo ${android_tag} | grep -o -P 'v[0-9].[0-9]*.[0-9]*'`
get_ww_string $tag_timestamp date_string release_string
rc_android_tag=lts-$tag_kernel_version-android_s-$tag_timestamp
rc_android_cve_tag=lts-$tag_kernel_version-android_s-cve-$tag_timestamp
cve_staging_tag=lts-$tag_kernel_version-android_s-cve-$tag_timestamp
ANDROID_TAG="lts-$tag_kernel_version-android_s-$tag_timestamp"

echo 'tag timestamp: ' $tag_timestamp
echo 'tag kernel version: ' $tag_kernel_version
echo 'Date string: ' $date_string
echo 'release string: ' $release_string

if [ "${android_dry_run}" == false  ] || [ "${android_push}" == true  ]; then
	pushd $kernel_source_folder
		add_scm z_android https://github.com/intel-innersource/os.android.bsp-gordon-peak.kernel-lts2018 || \
			die "Unable to git-remote-add android kernel lts2018"
		add_scm z_github_lts https://github.com/intel/linux-intel-lts.git || \
			die "Unable to git-remote-add github linux-intel-lts"
		add_scm z_rel_int https://github.com/intel-innersource/os.linux.kernel.kernel-lts || \
			die "Unable to git-remote-add github/innersource kernel-lts"
	popd
	pushd $kernel_cve_folder
		add_scm z_github_lts https://github.com/intel/linux-intel-lts.git || \
			die "Unable to git-remote-add github linux-intel-lts"
	popd

	pushd $kernel_config_folder
		add_scm z_android_config https://github.com/intel-innersource/os.android.bsp-gordon-peak.kernel-config-lts-2018 || \
			die "Unable to git-remote-add android config-lts"
	popd
fi

tags=""
if [ "${android_dry_run}" == false  ]; then
	pushd $kernel_source_folder
		checkout_remote $android_tag
		if [ "${android_push}" == true  ]; then
			git tag -d $rc_android_tag || :
			tag $rc_android_tag "release Kernel 4.19 for android S Dessert" || :
			git push origin $rc_android_tag || :
			push_remote z_android HEAD abt/sandbox/sys_oak/integ/kernel_s true
			push_remote z_github_lts HEAD 4.19/android_s true
			
			# delete tag locally, re-create it with singingkey and push tag to github external release repo
			git tag -d $rc_android_tag || :
			git tag -s $rc_android_tag -m "release Kernel 4.19 for android S Dessert"
			push_tag z_github_lts $rc_android_tag
			tags="${rc_android_tag}:1:3"
			push_remote origin HEAD 4.19/release/android_s
			add_scm z_rel_int https://github.com/intel-innersource/os.linux.kernel.kernel-lts || \
				die "Unable to git-remote-add github/innersource kernel-lts"
			push_remote z_rel_int HEAD 4.19/android_s true
			push_tag z_rel_int $rc_android_tag
			tags="$tags ${rc_android_tag}:1:2"
		fi

	popd
	pushd $kernel_config_folder
		checkout_remote $android_tag
		if [ "${android_push}" == true  ]; then
			git tag -d $rc_android_tag || :
			tag $rc_android_tag "release Kernel Configuration for 4.19 for android S Dessert" || :
			git push origin $rc_android_tag || :
			push_remote z_android_config HEAD abt/sandbox/sys_oak/integ/kernel_s true
			push_remote origin HEAD 4.19/config_s
			push_remote origin HEAD 4.19/release/config_s
		fi

	popd
fi	

#Push a release tag for the cve repo
if [ "${android_dry_run}" == false  ]; then
	pushd $kernel_cve_folder
		checkout_remote $cve_staging_tag
		rm -rf base 
		rm -rf clear
		rm -rf android
		rm -rf android_q

		#no matter android_s is symbol link of android_r, or android_s is itself, this line is ok
		mkdir android_s_tmp;cp -r android_s/* android_s_tmp;rm -fr android_s;mv android_s_tmp android_s

		rm -rf android_r;rm -rf android_t
		git rm -r base
		git rm -r clear
		git rm -r android
		git rm -r android_q
		git rm -r android_r
		git rm -r android_t || :
		pushd android_s
		cve_security_info_file='https://raw.githubusercontent.com/nluedtke/linux_kernel_cves/master/data/4.19/4.19_security.txt'
		version=$(echo "${tag_kernel_version:1}") #remove v from kernel version string ex. v4.19.62 become 4.19.62
		Prepare_cve_release_note patches/series $cve_security_info_file $version
		popd
		git add android_s
		git commit -m "CVE quilt release for $date_string"
		if [ "${android_push}" == true  ]; then
			git tag -d $rc_android_cve_tag || :
			tag $rc_android_cve_tag "release Kernel 4.19 for android S Dessert for '$rc_android_cve_tag'" || :
			git push origin $rc_android_cve_tag || :
			tags="$tags ${rc_android_cve_tag}:3:2"
			push_remote z_github_lts HEAD 4.19/android_s-cve true

			# delete tag locally, re-create it with singingkey and push tag to github external release repo
			git tag -d $rc_android_cve_tag || :
			git tag -s $rc_android_cve_tag -m "release Kernel 4.19 for android S Dessert for $rc_android_cve_tag"
			push_tag z_github_lts $rc_android_cve_tag
			tags="$tags ${rc_android_cve_tag}:3:3"
		fi
		rm android_s/CVE_Release_Notes.txt
	popd
fi

#Push a release tag for Internal lts-quilt
if [ "${android_dry_run}" == false  ]; then
	pushd $kernel_quilt_folder
		checkout_remote $android_tag
		if [ "${android_push}" == true  ]; then
			git tag -d $rc_android_tag || :
			tag $rc_android_tag "release Kernel 4.19 for android S Dessert" || :
			git push origin $rc_android_tag || :
			push_remote origin HEAD 4.19/android_s
			add_scm z_quilt_int https://github.com/intel-innersource/os.linux.kernel.kernel-lts-quilt || \
				die "Unable to git-remote-add github/innersource kernel-lts-quilt"
			push_tag z_quilt_int $rc_android_tag
			tags="$tags ${rc_android_tag}:2:2"
			push_remote z_quilt_int HEAD 4.19/android_s
		fi
	popd
fi

# get link as, https://ikt.bj.intel.com/release/quiltdiff?tag=...
android_chglst_rel_url="https://ikt.bj.intel.com/release/quiltdiff?tag=${rc_android_tag}"

rm -f android_tag.prop
declare pv=""
for pn in ANDROID_TAG ${CIB_JOB_PARAMS[4.19lts_s]}; do
    eval "pv=\$${pn}"
    echo "$pn=$pv" >> android_tag.prop
done
echo "KERNEL=4.19lts_s" >> android_tag.prop

# release notes
echo "[Release][$tag_kernel_version][lts-2018][S Dessert] $release_string" > subject.txt
h_release=$(echo "[Release][$tag_kernel_version][lts-2018][S Dessert] $release_string")
raw_html='<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">

<html>
<head>
  <style type="text/css">
ol{margin:0;padding:0}table td,table th{padding:0}.c2{color:#000000;font-weight:400;text-decoration:none;vertical-align:baseline;font-size:11pt;font-family:"Arial";font-style:normal}.c5{color:#000000;text-decoration:none;vertical-align:baseline;font-size:11pt;font-family:"Arial";font-style:italic}.c6{padding-top:0pt;padding-bottom:0pt;line-height:1.15;orphans:2;widows:2;text-align:center}.c0{padding-top:0pt;padding-bottom:0pt;line-height:1.15;orphans:2;widows:2;text-align:left}.c4{color:#000000;text-decoration:none;vertical-align:baseline;font-size:11pt;font-family:"Arial";font-style:normal}.c8{color:#000000;text-decoration:none;vertical-align:baseline;font-size:14pt;font-family:"Arial";font-style:normal}.c7{background-color:#ffffff;max-width:468pt;padding:72pt 72pt 72pt 72pt}.c3{height:11pt}.c1{font-weight:700}.title{padding-top:0pt;color:#000000;font-size:26pt;padding-bottom:3pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}.subtitle{padding-top:0pt;color:#666666;font-size:15pt;padding-bottom:16pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}li{color:#000000;font-size:11pt;font-family:"Arial"}p{margin:0;color:#000000;font-size:11pt;font-family:"Arial"}h1{padding-top:20pt;color:#000000;font-size:20pt;padding-bottom:6pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h2{padding-top:18pt;color:#000000;font-size:16pt;padding-bottom:6pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h3{padding-top:16pt;color:#434343;font-size:14pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h4{padding-top:14pt;color:#666666;font-size:12pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h5{padding-top:12pt;color:#666666;font-size:11pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;orphans:2;widows:2;text-align:left}h6{padding-top:12pt;color:#666666;font-size:11pt;padding-bottom:4pt;font-family:"Arial";line-height:1.15;page-break-after:avoid;font-style:italic;orphans:2;widows:2;text-align:left}
  </style>

  <title></title>
</head>

<body class="c7">
  <p class="c6"><span class="c2"><b><big>IoTg Linux Kernel Team</b></big></span></p>
  <p class="c6"><span class="c1 c5">'$h_release'</span></p>

  <p class="c0 c3"></p>

  <p class="c0"><span class="c1">Release Summary</span><span class=
  "c2">:</span></p>
  <br>
  <p>&emsp;&emsp;This is stable update for <b>'$tag_kernel_version'</b> </p> 
  <br>
  <br>

  <p class="c0"><span class="c2"><b>List of patches integrated</b> (change
  log)</span><br>
  &emsp;&emsp;Android: '$android_chglst_rel_url'</p>
  
  <p class="c0 c3"></p>
  <br>
  <p class="c4 c1"><font color="red"><b>Known Issues:</b></font></p>
<br>
<br>

  <p class="c4 c1"><b> Kernel Repository:</b></p>
	<p><a href=https://github.com/intel-innersource/os.linux.kernel.kernel-lts>https://github.com/intel-innersource/os.linux.kernel.kernel-lts</a></p>
	<p class="c4 c1"><b>Branch:</b></p>
	<p>4.19/android_s</p>
	<p class="c4 c1"><b>Tag:</b><br></p>
	<p>'$rc_android_tag'<br></p>
  <br>
  <br>
 <p class="c4 c1"><b>Kernel Configuration Repository:</b></p>
 	<p><a href=https://github.com/intel-innersource/os.linux.kernel.kernel-config>https://github.com/intel-innersource/os.linux.kernel.kernel-config</a></p>
  	<p class="c4 c1"><b>Branch:</b></p>
  	<p>4.19/release/config_s</p>
	<p class="c4 c1"><b>Tag:</b><br></p>
  	<p>lts-'$tag_kernel_version'-android_s-'$date_string'</span></p>
<br>
<br>
  <p class="c4 c1"><b>Kernel CVE Repository:</b></p>
	<p><a href=https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve>https://github.com/intel-innersource/os.linux.kernel.kernel-lts-cve</a></p>
  	<p class="c4 c1"><b>Tag:</b><br></p>
  	<p>'$rc_android_cve_tag'</span></p>

<br>
  <p class="c4 c1"><b>QA Reports</b></p>
  <p>
  	<a href=https://jira.devtools.intel.com/browse/'$TRACKING_JIRA'>https://jira.devtools.intel.com/browse/'$TRACKING_JIRA'</a> <br>
  </p>
<br>
<p class="c4 c1"><b>External Release Information</b></p>
<br>
  <p class="c4 c1"><b>GitHub Repository:</b></p>
<p><a href="https://github.com/intel/linux-intel-lts">https://github.com/intel/linux-intel-lts</a></p>
  <p>&ensp;<b>Branches:</b><br></p>
  <p>
                &emsp;&emsp;<a href="https://github.com/intel/linux-intel-lts/tree/4.19/android_s">4.19/android_s</a> <br>
                &emsp;&emsp;<a href="https://github.com/intel/linux-intel-lts/tree/4.19/android_s-cve">4.19/android_s-cve</a> <br>
  </p>
  <p>&ensp;<b>Tags:</b><br></p>
  <p>
  &emsp;&emsp;<a href="https://github.com/intel/linux-intel-lts/releases/tag/'$rc_android_tag'">'$rc_android_tag'</a> <br>
  &emsp;&emsp;<a href="https://github.com/intel/linux-intel-lts/releases/tag/'$rc_android_cve_tag'">'$rc_android_cve_tag'</a> <a href="https://github.com/intel/linux-intel-lts/blob/'$rc_android_cve_tag'/android_s/CVE_Release_Notes.txt">( --CVE Release Notes-- )</a> <br>
  </p>

<br>'


raw_html=$raw_html'

  <p class="c0 c3"></p>
  <hr style="page-break-before:always;display:none;">

</body>
</html>
'
msg="PRODUCTION KERNEL TEAM
*** lts 4.19 is Intel Public ***
[Release][$tag_kernel_version][lts2018][S Dessert] $release_string

https://github.com/intel-innersource/os.linux.kernel.kernel-lts

https://github.com/intel-innersource/os.linux.kernel.kernel-config

\ttags:
\t\tlts-$tag_kernel_version-android_s-$date_string

Known issues:

"

echo -e $raw_html > $WORKSPACE/message.html
echo "<pre>" >>$WORKSPACE/message.html
echo "</pre>" >>$WORKSPACE/message.html
echo -e "$msg" > $WORKSPACE/message.txt
for tag in ${tags}; do
    echo "EXTRA_DATA_TAG=$tag"
done

uuencode message.html message.html | mail -s "$h_release" nex.linux.kernel.integration@intel.com

