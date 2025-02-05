#!/bin/bash

echo $1 | grep "\.intel\.com$" > /dev/null 2>&1
if [ $? -eq 0 ]; then
        /usr/bin/connect $@
else
        /usr/bin/connect -S proxy-im.intel.com:1080 -a none $@
fi

