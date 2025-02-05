# The code in this file is snipped from download.py in LAVA Dispatcher.
#
# You can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software 
# Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import os
import shutil
import time
import hashlib
import requests
import math
import logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


HTTP_DOWNLOAD_CHUNK_SIZE = 32768


class HttpDownloadError(Exception):
    pass


class HttpDownloader():
    """
    Download a resource over http or https using requests module
    """

    def __init__(self, auth=None):
        self.auth = auth

    def validate(self, url):
        res = None
        try:
            logger.debug("Validating that %s exists", url)
            res = requests.head(url,
                                auth=self.auth,
                                allow_redirects=True,
                                verify=False)
            if res.status_code != requests.codes.OK:
                # try using (the slower) get for services with broken redirect support
                logger.debug("Using GET because HEAD is not supported properly")
                res.close()
                res = requests.get(url,
                                   auth=self.auth,
                                   allow_redirects=True,
                                   stream=True,
                                   verify=False)
                if res.status_code != requests.codes.OK:
                    logger.error("Resource unavailable at '%s' (%d)" % \
                                   (url, res.status_code))

            self.size = int(res.headers.get('content-length', -1))
        except requests.Timeout:
            logger.error("Request timed out")
        except requests.RequestException as exc:
            logger.error("Unable to get '%s': %s" % (url, str(exc)))
        finally:
            if res is not None:
                res.close()

    def reader(self, url):
        res = None
        try:
            # FIXME: When requests 3.0 is released, use the enforce_content_length
            # parameter to raise an exception the file is not fully downloaded
            res = requests.get(url,
                               auth=self.auth,
                               allow_redirects=True,
                               stream=True,
                               verify=False)
            if res.status_code != requests.codes.OK:  # pylint: disable=no-member
                raise HttpDownloadError("Unable to download '%s'" % url)
            for buff in res.iter_content(HTTP_DOWNLOAD_CHUNK_SIZE):
                yield buff
        except requests.RequestException as exc:
            raise HttpDownloadError("Unable to download '%s': %s" % (url, str(exc)))
        finally:
            if res is not None:
                res.close()

    def download(self, url, out, md5sum=None):
        def progress_unknown_total(downloaded_sz, last_val):
            """ Compute progress when the size is unknown """
            condition = downloaded_sz >= last_val + 25 * 1024 * 1024
            return (condition, downloaded_sz,
                    "progress %dMB" % (int(downloaded_sz / (1024 * 1024))) \
                      if condition else "")

        def progress_known_total(downloaded_sz, last_val):
            """ Compute progress when the size is known """
            percent = math.floor(downloaded_sz / float(self.size) * 100)
            condition = percent >= last_val + 5
            return (condition, percent,
                    "progress %3d%% (%dMB)" % \
                      (percent, int(downloaded_sz / (1024 * 1024))) \
                        if condition else "")

        self.validate(url)

        md5 = hashlib.md5()  # nosec - not being used for cryptography.

        logger.info("downloading %s", url)
        logger.debug("saving as %s", out)

        downloaded_size = 0
        beginning = time.time()
        # Choose the progress bar (is the size known?)
        if self.size == -1:
            logger.debug("total size: unknown")
            last_value = -25 * 1024 * 1024
            progress = progress_unknown_total
        else:
            logger.debug("total size: %d (%dMB)" % \
                           (self.size, int(self.size / (1024 * 1024))))
            last_value = -5
            progress = progress_known_total

        def update_progress():
            nonlocal downloaded_size, last_value, md5
            downloaded_size += len(buff)
            (printing, new_value, msg) = progress(downloaded_size,
                                                  last_value)
            if printing:
                last_value = new_value
                logger.debug(msg)
            md5.update(buff)

        with open(out, 'wb') as dwnld_file:
            for buff in self.reader(url):
                update_progress()
                dwnld_file.write(buff)

        # Log the download speed
        ending = time.time()
        logger.info("%dMB downloaded in %0.2fs (%0.2fMB/s)" %
                      (downloaded_size / (1024 * 1024), round(ending - beginning, 2),
                        round(downloaded_size / (1024 * 1024 * (ending - beginning)), 2)))

        chk_md5sum = md5.hexdigest()
        if md5sum and md5sum != chk_md5sum:
            raise HttpDownloadError(
                "MD5 checksum does not match (expected: %s, actual: %s)" % \
                  (md5sum, chk_md5sum))
