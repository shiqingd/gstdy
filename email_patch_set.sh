#!/usr/bin/env bash

set -e

TEMP_DIR=/tmp/patch-email
MAIL_TO=sys_oak@intel.com
KERNEL=mainlinetracking

get_domains()
{
	DOMAINS=`curl --no-progress-meter https://oak-pkpt.ostc.intel.com/domains/${KERNEL}`
}

get_domains

usage()
{
	echo ""
	echo "Usage: $0 -b BRANCH -r REF0..REF1 -d DOMAIN [ -t TITLE ]"
	echo
	echo "WHERE:"
	echo "	BRANCH      -	domain branch from which to pull patches"
	echo "	REF0..REF1	-	range of commits to include in set of patches"
	echo "	TITLE	    -   One-Line Title for the Patch set (255 characters max)"
	echo "                  (you will be prompted if not provided on command line"
	echo "	DOMAIN      -   valid domain for ${KERNEL} kernel.  Valid values are:"
	echo
	echo "		[" $DOMAINS "]"
	echo
}

while getopts 'b:r:d:t:k:h?' arg
do
	case $arg in
		b) branch=$OPTARG ;;
		r) range=$OPTARG ;;
		d) domain_label=$OPTARG ;;
		k) KERNEL=$OPTARG	# Undocumented option - allowd specifying alternate kernel
			get_domains		# Get new set of domains for new kernel
			;;
		t) series_title=$OPTARG ;;
		h|?) usage
			exit 0;;
		*) echo "ERROR : bad command arguments"
			usage
			exit 1
			;;
	  esac
done

if [ -z "${branch}" -o -z "${range}" -o -z "${domain_label}" ]
then
    echo 
    echo "ERROR: Insufficient required arguments"
    usage
    exit 1
fi

# Validate domain label
domain_array=($(echo $DOMAINS | tr ' ' '\n'))
for label in "${domain_array[@]}"; do
    [[ $domain_label == "$label" ]] && valid_domain=1
done

if [ -z "${valid_domain}" ]
then
	echo
	echo "ERROR : Invalid domain label"
	echo "Valid domains are":
	echo "[" $DOMAINS "]"
	echo
	exit 1
fi

series_title=''
while [ -z "${series_title}" ]
do
	echo -n 'Please Provide a 1-line tile line for this patch set (255 characters max): '
	read series_title
done

echo
echo "==========Patches==Harvesting=========="
if grep linux/kernel-integration .git/config
then
	echo "Please run this script from am up-to-date view of the linux-kernel-integration/kernel-staging repository"
	exit 1
fi

git checkout $branch
rm -rf ${TEMP_DIR}
git format-patch ${range} --output-directory=${TEMP_DIR} --to=${MAIL_TO} --cover-letter
echo "==========adding=domain=info=========="
echo
mkdir -p ${TEMP_DIR}
cd ${TEMP_DIR}
sed -i 's/\(\[PATCH .\+\]\) \*\*\* SUBJECT HERE \*\*\*/\['$domain_label'\] \1 '"$series_title"'/' *cover-letter*
sed -i 's/\*\*\* BLURB HERE \*\*\*/'"${series_title}"'/' *cover-letter*
for patchfile in ${TEMP_DIR}/*.patch
do	
	sed -i 's/\(Subject:\) \+\(\[PATCH .\+\]\)/\1 \['$domain_label'\] \2/' ${patchfile}
done
echo "==========patches are ready=========="
echo
echo "=============send-patches============="
echo git send-email --smtp-debug=1 --suppress-cc=all --to=${MAIL_TO} ${TEMP_DIR}
