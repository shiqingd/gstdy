#!/bin/bash

#
# Common code used by the dev kernel scripts.
#

# Set to tag you wish to start with.  Otherwise leave "" for latest.
linus_tag_release=""
linus_tag_staging=""
embargoed_tag=""
embargoed_base="v4.14"

release_branches="\
	tracker/dev/release/drm \
	tracker/dev/release/camera \
	tracker/dev/release/audio \
	tracker/dev/release/usb \
	tracker/dev/release/comms \
	tracker/dev/release/sensors \
	tracker/dev/release/em \
	tracker/dev/release/tm \
	tracker/dev/release/pmic \
	tracker/dev/release/touchscreen \
	tracker/dev/release/video \
	tracker/dev/release/security \
	tracker/dev/release/lpss \
	tracker/dev/release/storage \
	tracker/dev/release/core \
	tracker/dev/release/pm \
	tracker/dev/release/network" 
#	tracker/dev/release/hypervisor temporarily removed

release_android_branches="\
	tracker/dev/release/drm-android \
	tracker/dev/release/trusty \
	tracker/dev/release/google \
	tracker/dev/release/google-fixes \
	tracker/dev/release/dnt \
	tracker/dev/release/camera-android \
	tracker/dev/release/presi"

release_yocto_branches="\
	tracker/dev/release/yocto"


#staging_branches="\
#	tracker/dev/staging/drm \
#	tracker/dev/staging/camera \
#	tracker/dev/staging/audio \
#	tracker/dev/staging/usb \
#	tracker/dev/staging/comms \
#	tracker/dev/staging/sensors \
#	tracker/dev/staging/em \
#	tracker/dev/staging/tm \
#	tracker/dev/staging/pmic \
#	tracker/dev/staging/touchscreen \
#	tracker/dev/staging/video \
#	tracker/dev/staging/security \
#	tracker/dev/staging/lpss \
#	tracker/dev/staging/storage \
#	tracker/dev/staging/core \
#	tracker/dev/staging/pm \
#	tracker/dev/staging/network"
#	tracker/dev/staging/hypervisor temporarily removed.


#staging_branches="\
#  tracker/sandbox/mgross/core \
#  tracker/sandbox/mgross/security \
#  tracker/sandbox/mgross/comms \
#  tracker/sandbox/mgross/pm \
#  tracker/sandbox/mgross/hypervisor \
#  tracker/sandbox/mgross/usb \
#  tracker/sandbox/mgross/lpss \
#  tracker/sandbox/mgross/sensors \
#  tracker/sandbox/mgross/storage \
#  tracker/sandbox/mgross/dii"

staging_branches="tracker/sandbox/mgross/4.19/dev-bkc-rc2"
#staging_branches="tracker/sandbox/mgross/dev-bkc-rc8"

#staging_android_branches="\
#	tracker/dev/staging/drm-android \
#	tracker/dev/staging/trusty \
#	tracker/dev/staging/google \
#	tracker/dev/staging/google-fixes \
#	tracker/dev/staging/dnt \
#	tracker/dev/staging/camera-android \
#	tracker/dev/staging/presi"

#staging_android_branches="\
#  tracker/sandbox/mgross/trusty \
#  tracker/sandbox/mgross/google-fixes \
#  tracker/sandbox/mgross/google \
#  tracker/sandbox/mgross/dnt"
 
staging_android_branches="tracker/sandbox/mgross/4.19/dev-bkc-rc2-android"
#staging_android_branches="tracker/sandbox/mgross/dev-bkc-rc8-android"

#staging_yocto_branches="\
#	tracker/dev/staging/yocto"

staging_yocto_branches="tracker/sandbox/mgross/4.19/dev-bkc-rc2"
#staging_yocto_branches="tracker/sandbox/mgross/dev-bkc-rc8"

embargoed_branches="\
	tracker/${embargoed_base}_embargoed/drm \
	tracker/${embargoed_base}_embargoed/camera \
	tracker/${embargoed_base}_embargoed/audio \
	tracker/${embargoed_base}_embargoed/usb \
	tracker/${embargoed_base}_embargoed/comms \
	tracker/${embargoed_base}_embargoed/sensors \
	tracker/${embargoed_base}_embargoed/em \
	tracker/${embargoed_base}_embargoed/tm \
	tracker/${embargoed_base}_embargoed/pmic \
	tracker/${embargoed_base}_embargoed/touchscreen \
	tracker/${embargoed_base}_embargoed/video \
	tracker/${embargoed_base}_embargoed/security \
	tracker/${embargoed_base}_embargoed/lpss \
	tracker/${embargoed_base}_embargoed/storage \
	tracker/${embargoed_base}_embargoed/core \
	tracker/${embargoed_base}_embargoed/pm \
	tracker/${embargoed_base}_embargoed/network \
	tracker/${embargoed_base}_embargoed/hypervisor"

embargoed_android_branches="\
	tracker/${embargoed_base}_embargoed/drm-android \
	tracker/${embargoed_base}_embargoed/trusty \
	tracker/${embargoed_base}_embargoed/google \
	tracker/${embargoed_base}_embargoed/google-fixes \
	tracker/${embargoed_base}_embargoed/dnt \
	tracker/${embargoed_base}_embargoed/camera-android \
	tracker/${embargoed_base}_embargoed/presi"

embargoed_yocto_branches="\
	tracker/${embargoed_base}_embargoed/yocto"
