#!/bin/bash
#set -x

CUR_DIR=$PWD
#WORK_DIR=$CUR_DIR/patches

if [ ! -d $CUR_DIR/patches ] && [ ! -f $CUR_DIR/patches/series ]
then
	echo "Please change to right directory."
	exit
fi

echo "#########################Checking_Patch################################"

ls $CUR_DIR/patches > file_list.txt

#To list patch name that removed from series file without deleting patch file.
grep -vwf $CUR_DIR/patches/series $CUR_DIR/file_list.txt > list1.txt
#cat list1.txt
list1=$(grep "patch" list1.txt)
#echo "$list1"
grep "\.patch" list1.txt
if [ $? ==  0 ]
then
	echo "======================ACTION REQUIRED=================================="
	echo "Please clean up. Following patch files are not included in series file."
	echo "patches need to cleaned up: "
	echo "$list1 "
	echo "======================================================================="
	exit 1
else
	echo "no patch files needed to be removed." 
fi

#To list patch name that removed from series file without deleting patch file.
grep -vwf $CUR_DIR/file_list.txt $CUR_DIR/patches/series > list2.txt
#cat list2.txt
list2=$(grep "\.patch" list2.txt)
if [  $? -eq 0 ]
then
	echo "======================ACTION REQUIRED================================================"
        echo "Please uploade patch files. Following patch files needed by series files are missing."
	echo "patches needed to be added: "
	echo "$list2" 
	echo "====================================================================================="
	exit 1
else
	echo "no missing patch files."
fi

