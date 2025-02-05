#!/usr/bin/env python3
import sys
import os
import argparse
import re
import logging
import shutil
import json
import traceback

if not "DJANGO_SETTINGS_MODULE" in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
        import django
        django.setup()

from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import IntegrityError
from django.db.models import Q
from django.utils import timezone

from framework.models import *

from lib.pushd import pushd
import lib.dry_run

# These methods have been moved to the Django models.py module

def handle_args(args):
    parser = argparse.ArgumentParser(prog = sys.argv[0], epilog = """\
The yocto_staging script will build the kernel from the branch named on
the commandline with various version of Poky.  It will always use the
dev-bkc repo.""")
    parser.add_argument("--kernel", "-k", required=True, type=Kernel.validate,
                        help="Kernel product: "+Kernel.list())
    parser.add_argument("--platform", required=True, type=Platform.validate,
                        help="platform name:"+ Platform.list())
    parser.add_argument("--staging-number", "-b", required=True, dest = "staging_number", type=str,
                        help="Staging Number")
    parser.add_argument("--yocto-release", "-p", required=True, dest = "yocto_release", type=str,
                        help="Yocto project release name (rocko, sumo, master (default))")
    parser.add_argument("--repo-mirror", "-m", dest = "repo_mirror", type=str,
                        help="The mirror path to Yocto repository")
    parser.add_argument("--dl-dir", "-d", dest = "dl_dir", type=str,
                        help="Path to the downloads directory for Yocto build")
    parser.add_argument("--sstate-dir", "-s", dest = "sstate_dir", type=str,
                        help="Path to the sstate-cache directory for Yocto build")
    parser.add_argument("--dry_run", action="store_true",
                        help="Do not actually do anything; just print what would happen")
    parser.add_argument("--repo-cmd", "-c", dest = "repo_cmd", type=str,
                        help="The path to repo command")
    parser.add_argument("--log-verbose", "-v", action="store_true",
                        help="Log the output of bitbake in verbose mode")
    parser.add_argument("--conf", "-l", dest = "confs", type=json.loads,
                        help="Dict of variables set in conf file(s)")
    return parser.parse_args()


if __name__ == '__main__':
    assert("WORKSPACE" in os.environ)
    LOGLEVEL = os.environ.get('LOGLEVEL', 'DEBUG')
    logging.basicConfig(level=LOGLEVEL, format='%(levelname)-5s: %(message)s')

    args = handle_args(sys.argv[0])
    lib.dry_run.dry_run = args.dry_run

    # calculate the number of parallel jobs per available cpu and mem
    job_num = cal_cpu_num()

    try:
        kernel = Kernel.objects.get(name = args.kernel)
        platform = Platform.objects.get(name = args.platform)
        yb = YoctoBuild.objects.get(kernel = kernel, platform = platform)
        yb.add_cmdline_args(args)
        yb.logger = logging.getLogger(__name__)
        if args.log_verbose:
            print(yb.__dict__)
    except Exception as e:
        traceback.format_exc()
        print(e)
        sys.exit(1)
    yb.do_all()

    # save image url in the downstream.prop file
    image_url = os.path.join(
        os.environ['BUILD_URL'], 'artifact', yb.get_image_path())
    propfl = os.path.join(os.environ['WORKSPACE'], 'downstream.prop')
    with open(propfl, 'w') as pf:
        pf.write("IMAGE_URL=%s\n" % image_url)
        pf.write("STAGING_REVISION=%s\n" % yb.kernel.current_baseline)

