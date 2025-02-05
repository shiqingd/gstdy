#!/usr/bin/env python3

import os
import sys
import sh
import re
import json
import logging
import argparse
from datetime import datetime, timedelta
from django.utils import timezone
import time
from glob import glob
import shutil
from django.db.models import F, Q
from django.db import transaction

if not "DJANGO_SETTINGS_MODULE" in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
    import django
    django.setup()

from framework.models import *
from framework import const
from lib.pushd import pushd
from lib.gitutils import get_patchid, find_dup_commits, compute_domains


logger = logging.getLogger(__name__)
bash = sh.Command("/bin/bash")


def gen_quilt(gitcmd, reltag):
    m = re.search(r'(v[3-9]\.[\d\.\-rc]+)-', reltag)
    if not m:
        logger.error("Invalid release tag %s, kernel version not found" % reltag)
        sys.exit(1)
    basever = m.group(1)
    quiltdir = 'quilt-tmp'
    shutil.rmtree(quiltdir, ignore_errors=True)
    # generate quilt <base version>..<reltag>
    gitcmd("format-patch", "-o", quiltdir, "%s..%s" % (basever, reltag))
    cmt_re = re.compile(r'^From ([\da-f]{8,})\s')
    quilt = []
    shout = bash('-c',
                 """
                    cd {quiltdir}
                    for f in *.patch; do
                        out="$(git patch-id < $f 2>/dev/null)"
                        echo "$out $f"
                    done
                 """.format(quiltdir=quiltdir),
                 _tty_out=False).stdout.decode().strip().splitlines()

    for l in shout:
        item = l.split()
        if len(item) != 3:
            logger.warning("%s: NO PATCH-ID found" % item[0])
            m = cmt_re.search(pfl.read(1024))
            if not m:
                logger.error("Cannot get the commit id, skip it")
                continue
            item = [None, m.group(1), item[0]]
        quilt.append(item)

    shutil.rmtree(quiltdir, ignore_errors=True)
    # [[(<patch id>, <commit id>, <patch file>), ...], ...]
    return quilt


def import_quilt(gitcmd, td, reltag_idx):
    tag = td.release_tags[reltag_idx]
    quilt = gen_quilt(gitcmd, tag)
    patch_dict = { p[1]: p[0] for p in quilt }

    # identify the new patches
    #   1. filter out old commit
    #   2. filter out old payload hash
    query = Q()
    for c in patch_dict.keys():
        query = query | Q(commit=c)
    # query crossing kernels
    tdp_list = TechDebtPatch.objects.filter(
                 query).values_list('commit', flat=True).distinct()
    tdp_set = set(tdp_list)
    # new commits
    c_unmatched = patch_dict.keys() - tdp_set
    unmatched_plhs = set([ patch_dict[c] \
                             for c in c_unmatched if patch_dict[c] ])
    query = Q()
    for h in unmatched_plhs:
        query = query | Q(payload_hash=h)
    pinfo_list = PatchInfo.objects.filter(
                   query).values_list('payload_hash', flat=True)

    # new payload hash
    h_unmatched = unmatched_plhs - set(pinfo_list)
    query = Q()
    for h in h_unmatched:
        query = query | Q(payload_hash=h)
    upstreameds = UpstreamedPatch.objects.filter(query)
    upstreamed_dict = { p.payload_hash: p.id for p in upstreameds }

    # insert new patches into patchinfo
    rcmt_re = re.compile(r'this\sreverts\scommit\s([\da-f]{4,})\b',
                         flags=re.M|re.I)
    rcmt_re2 = re.compile(r'^\s*Fixes:\s*([\da-f]{4,})\b')
    now = datetime.now()
    # new patchinfo object list
    new_pi_objs = []
    new_pi_dict = {}
    # new revert commit object list
    new_rc_objs = []
    logger.debug("c_unmatched: %i" % len(c_unmatched))
    for c in c_unmatched:
        # payload_hash
        plh = patch_dict[c]
        new_pinfo = PatchInfo(
            payload_hash=plh
        )

        subject = gitcmd(
                    "show", '-s', r'--format=%s', c, _tty_out=None).rstrip()
        # handle revert commit first
        m = re.search(r'\brevert\b', subject, flags=re.I)
        if m:
            # new revert commit
            new_rc = RevertPatch(
                commit=c,
                reltag=tag
            )
            new_pinfo.state = const.PATCHINFO_STAT_REVERT_COMMIT
            msg = gitcmd("show", '-s', r'--format=%b',
                           c, _tty_out=None).rstrip()
            m2 = rcmt_re.search(msg)
            if not m2:
                m2 = rcmt_re2.search(msg)
            if m2:
                # get the full version of the commit hash
                try:
                    new_rc.reverted_commit = gitcmd(
                        "show", '-s', r'--format=%H',
                          m2.group(1), _tty_out=None).rstrip()
                except:
                    new_rc.reverted_commit = m2.group(1)
                if new_rc.reverted_commit in patch_dict:
                    new_rc.state = const.REVERTPATCH_STAT_BOTH_QUILT
                else:
                    # check if it's duplicated
                    dup_commits = find_dup_commits(new_rc.reverted_commit, tag)
                    if dup_commits:
                        new_rc.state = const.REVERTPATCH_STAT_DUPLICATED

            new_rc_objs.append(new_rc)

        # skip to insert into patchinfo
        if not plh or plh in pinfo_list or plh in new_pi_dict:
            continue

        new_pi_dict[plh] = new_pinfo
        new_pinfo.subject = subject
        new_pinfo.created_date = now
        new_pinfo.files = gitcmd("show", r'--pretty=', "--name-only",
                                   c, _tty_out=None).rstrip().splitlines()
        new_pinfo.author = gitcmd("show", '-s', r'--format=%ae',
                                    c, _tty_out=None).rstrip() 

        # set upstreamed_info
        if plh in upstreamed_dict:
            new_pinfo.upstreamed_info_id = upstreamed_dict[plh]
        else:
            upstreamed_info = new_pinfo.link_upstreamed_by_sub(save=False)
            if upstreamed_info:
                logger.info("upstreamed_info linked: %s" % \
                              upstreamed_info.commit_id)

        # set domain
        # FIXME: get DOMAINSHIP from label in gitlab database
        if new_pinfo.files:
            domains = compute_domains(new_pinfo.files)
            if domains:
                new_pinfo.domain = domains[0]
                logger.debug("%s: %s" % (new_pinfo.payload_hash, domains[0].name))
        # FIXME: platformids - get from label in gitlab database
        # FIXME: featureids - get from lable in gitlab database 

        # add new object in the list first, will be updated later
        new_pi_objs.append(new_pinfo)

    # insert new patchinfos into database
    logger.debug("patchinfo objs: %i" % len(new_pi_objs))
    with transaction.atomic():
        PatchInfo.objects.bulk_create(new_pi_objs)

    # insert each quilt patch in techdebtpatch table
    # new techdebtpatch object list
    new_tdp_objs = []
    for p in quilt:
        new_tdp = TechDebtPatch(
            techdebt_id=td.id,
            patch_id=p[0],
            commit=p[1],
            patchfile=p[2],
            reltagid=reltag_idx
        )
        new_tdp_objs.append(new_tdp)

    # insert into techdebtpatch and revertpatch
    logger.debug("tdp objs: %i" % len(new_tdp_objs))
    logger.debug("revertpatch objs: %i" % len(new_rc_objs))
    with transaction.atomic():
        TechDebtPatch.objects.bulk_create(new_tdp_objs)
        RevertPatch.objects.bulk_create(new_rc_objs)


def import_techdebt(td):
    kernel_repo = KernelRepoSet.objects.get(
                    kernel=td.kernel, repo__repotype__repotype='src').repo
    scmdir = os.path.join(os.environ["WORKSPACE"], kernel_repo.project)
    __git = kernel_repo.initialize(scmdir=scmdir)

    # cleanup the rows of this techdebtpatch, revertpatch
    query = Q()
    for t in td.release_tags:
        query = query | Q(reltag=t)
    with transaction.atomic():
        TechDebtPatch.objects.filter(techdebt=td).delete()
        #RevertPatch.objects.filter(query).delete()

    with pushd (kernel_repo.scmdir):
        for i, tag in enumerate(td.release_tags):
            import_quilt(__git, td, i)


if __name__ == '__main__':
    LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO')
    logging.basicConfig(level=LOGLEVEL, format='%(levelname)-5s: %(message)s')

    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument('--kernel', '-k', type=Kernel.validate, required=True,
                        action='store', help="Valid values: %s" % Kernel.list())
    parser.add_argument('--release-tags', '-t', action='store', required=True,
                        help="release tag(s), separated by comma")
    args = parser.parse_args()
    
    assert(os.path.exists(os.environ["WORKSPACE"]))

    kernel = Kernel.objects.get(name=args.kernel)
    reltags = re.sub(r'\s', '', args.release_tags).split(',')
    tds = TechDebt.objects.filter(kernel=kernel, release_tags__contains=reltags)
    if len(tds):
        td = tds[0]
    else:
        #created_date = time.strftime(
        #    "%Y-%m-%d %H:%M:%S+0000",
        #    time.strptime(reltags[0].split('-')[-1], '%y%m%dT%H%M%SZ'))
        created_date = timezone.utc.localize(
                         datetime.strptime(reltags[0].split('-')[-1],
                                           '%y%m%dT%H%M%SZ'))

        td = TechDebt(
            kernel=kernel,
            release_tags = reltags,
            created_date = created_date
        )
        td.save()

    import_techdebt(td)
