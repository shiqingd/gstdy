#!/usr/bin/env  python3

import re


"""
tag schema:
{{ is staging/sandbox }}{{ is stable update }}\
{{ iotg-next or mainline-tracking or lts }}-{{ kernel.current_baseline }}-\
{{ is_project }}{{ is_milestone }}{{ release.name }}{{ is_cve or is_bullpen }}\
{{ is_overlay }}{{ staging_number }}

release.name: linux/yocto/ubuntu/centos/android/android_X/rt/preempt-rt/xenomai

Note: is_su has not been approved, so disable this option.
"""
def generate_tagstr(kernel, base, ts, relname, is_staging=True,
                    is_sandbox=False, is_su=False, prj=None, ms=None,
                    is_cve=False, is_overlay=False, is_bp=False):
    m = re.search(r'(mainline-tracking|iotg-next)', kernel)
    if m:
        k = m.group(1)
    else:
        k = 'lts'
    if is_sandbox:
        stg = "sandbox-"
    elif is_staging:
        stg = "staging-"
    else:
        stg = ""
    su = "su-" if is_su else ""
    # overlay string
    ol = "overlay-" if is_overlay else ""
    prj = "%s-" % prj if prj else ""
    ms = "%s-" % ms if ms else ""
    cve = "cve-" if is_cve else ""
    bp = "bp-" if is_bp else ""
    return "{stg}{su}{k}-{kv}-{p}{m}{r}-{cve}{ol}{bp}{ts}".format(stg=stg,
                                                                  su=su,
                                                                  k=k,
                                                                  ol=ol,
                                                                  kv=base,
                                                                  p=prj,
                                                                  m=ms,
                                                                  r=relname,
                                                                  cve=cve,
                                                                  bp=bp,
                                                                  ts=ts)
