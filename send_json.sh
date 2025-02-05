#!/bin/bash

while getopts "v:u:j:r:k:m:" OPTION; do
	case $OPTION in
		v)
			version=${OPTARG}
			;;
		u)
			build_url=${OPTARG}
			;;
		j)
			jobname=${OPTARG}
			;;
		r)	
			result=${OPTARG}
			;;
		k)
			kernel=${OPTARG}
			;;
		m)
			minimal=${OPTARG}
			;;
	esac
done


url1='http://ikt.bj.intel.com:10086/send_json/'
url2='https://ikt.bj.intel.com/job_dashboard_api/api/send_json/send_json/'

data='{"version":"'${version}'","build_url":"'${build_url}'","jobname":"'${jobname}'","result":"'${result}'","kernel":"'${kernel}'","minimal":"'${minimal}'"}'

echo $data

curl -H "Expect:" -d $data -X POST $url1
curl -H "Expect:" -d $data -X POST $url2
