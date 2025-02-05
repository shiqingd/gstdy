#!/usr/bin/env python3

'''
Git revision parsing uilities for DevOps Framework

'''

import os
import sys, re
import sh
import time
from io import StringIO

from six.moves import map

_git = sh.Command("/usr/bin/git")

def __process_name_and_email(tag, match):
	return { "name" : match.group(1).strip().replace('"','') , "email" : match.group(2) }

def __process_bogus_email(tag, match):
	return { "name" : match.group(1).strip().replace('"','') , "email" : match.group(2)+"@"+match.group(3) }

def __process_bogus_email_domain(tag, match):
    return { "name" : match.group(1).strip().replace('"','') , "email" : match.group(2)+".bad" }

def __process_bogus_email_only(tag, match):
	return { "name" : match.group(1).strip().replace('"','') , "email" : match.group(1)+"@"+match.group(2) }

def __process_email_only(tag, match):
	if tag == 'Message-ID':
		return match.group(1)
	else:
		name = match.group(1)[:match.group(1).index('@')]
		return { "name" : name.replace('"','') , "email" : match.group(1) }

def __process_commit_hash(tag, match):
	return match.group(1)

__tag_value_parse_table = [
	( re.compile('((?:\S+\s+)+?)<{0,1}([a-zA-Z0-9_.+-]+@[_a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>{0,1}'), __process_name_and_email ),
	( re.compile('((?:\S+\s+)+?)<{0,1}([a-zA-Z0-9_.+-]+) at ([_a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,})>{0,1}'), __process_bogus_email ),
    ( re.compile('((?:\S+\s+)+?)<{0,1}([a-zA-Z0-9_.+-]+@.+)>{0,1}'), __process_bogus_email_domain ),
	( re.compile('<{0,1}([a-zA-Z0-9_.+-]+) at ([a-zA-Z0-9-]+\.[_a-zA-Z0-9-.]{2,})>{0,1}'), __process_bogus_email_only ),
	( re.compile('<{0,1}([a-zA-Z0-9_.+-]+@[_a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>{0,1}'), __process_email_only ),
	( re.compile(' ([0-9a-f]{8,40})$'), __process_commit_hash )
]

gitlog_format = 'Commit: %H\n\
Parents: %P\n\
Author: %an <%ae>\n\
Author-Date: %at\n\
Committer: %cn <%ce>\n\
Commit-Date: %ct\n\
Subject: %s\n\
\n\
%b\n\
---\n\
\n\
'

def parse_tags(text):
	committed_by  = None
	# Find all the 'Xxxxx-By: name <email>' lines in the commit message
	text = re.sub('\r', '', text)
	tag_dict = {}
	match = re.search("^From ([0-9a-f]{8,40})", text)
	if match:
		tag_dict["commit_id"] = match.group(1)
	tag_tuples = re.findall('\n*([A-Z][A-Za-z\-]+): (.+)\n', text)
#	credits = re.findall('^\s*([A-Za-z\-]+):\(.+)\n'(?:\S+\s+)*?)[<|]([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)[>|]$', text, re.MULTILINE)
	for tupl in tag_tuples:
		tagname = tupl[0]
		obj = None
		for t in __tag_value_parse_table:
			match = t[0].search(tupl[1])
			if match and tagname != 'Subject' :
				obj = t[1](tagname, match)
				break
			else:
				obj = tupl[1]
		if not tagname in tag_dict:
			tag_dict[tagname] = []
		tag_dict[tagname].append(obj)
	return tag_dict



def parse_patch(text):
	patchbuf = ''
	commentbuf = ''
	buf = ''
	__hunk_re = re.compile('^\@\@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? \@\@')

	# state specified the line we just saw, and what to expect next
	state = 0
	# 0: text
	# 1: suspected patch header (diff, ====, Index:)
	# 2: patch header line 1 (---)
	# 3: patch header line 2 (+++)
	# 4: patch hunk header line (@@ line)
	# 5: patch hunk content
	# 6: patch meta header (rename from/rename to)
	#
	# valid transitions:
	#  0 -> 1 (diff, ===, Index:)
	#  0 -> 2 (---)
	#  1 -> 2 (---)
	#  2 -> 3 (+++)
	#  3 -> 4 (@@ line)
	#  4 -> 5 (patch content)
	#  5 -> 1 (run out of lines from @@-specifed count)
	#  1 -> 6 (rename from / rename to)
	#  6 -> 2 (---)
	#  6 -> 1 (other text)
	#
	# Suspected patch header is stored into buf, and appended to
	# patchbuf if we find a following hunk. Otherwise, append to
	# comment after parsing.

	# line counts while parsing a patch hunk
	lc = (0, 0)
	hunk = 0

	for line in text.split('\n'):
		line += '\n'

		if state == 0:
			if line.startswith('diff ') or line.startswith('===') \
					or line.startswith('Index: '):
				state = 1
				buf += line

			elif line.startswith('--- '):
				state = 2
				buf += line

			else:
				commentbuf += line

		elif state == 1:
			buf += line
			if line.startswith('--- '):
				state = 2

			if line.startswith(('rename from ', 'rename to ')):
				state = 6

		elif state == 2:
			if line.startswith('+++ '):
				state = 3
				buf += line

			elif hunk:
				state = 1
				buf += line

			else:
				state = 0
				commentbuf += buf + line
				buf = ''

		elif state == 3:
			match = __hunk_re.match(line)
			if match:

				def fn(x):
					if not x:
						return 1
					return int(x)

				lc = list(map(fn, match.groups()))

				state = 4
				patchbuf += buf + line
				buf = ''

			elif line.startswith('--- '):
				patchbuf += buf + line
				buf = ''
				state = 2

			elif hunk and line.startswith('\ No newline at end of file'):
				# If we had a hunk and now we see this, it's part of the patch,
				# and we're still expecting another @@ line.
				patchbuf += line

			elif hunk:
				state = 1
				buf += line

			else:
				state = 0
				commentbuf += buf + line
				buf = ''

		elif state == 4 or state == 5:
			if line.startswith('-'):
				lc[0] -= 1
			elif line.startswith('+'):
				lc[1] -= 1
			elif line.startswith('\ No newline at end of file'):
				# Special case: Not included as part of the hunk's line count
				pass
			else:
				lc[0] -= 1
				lc[1] -= 1

			patchbuf += line

			if lc[0] <= 0 and lc[1] <= 0:
				state = 3
				hunk += 1
			else:
				state = 5

		elif state == 6:
			if line.startswith(('rename to ', 'rename from ')):
				patchbuf += buf + line
				buf = ''

			elif line.startswith('--- '):
				patchbuf += buf + line
				buf = ''
				state = 2

			else:
				buf += line
				state = 1

		else:
			raise Exception("Unknown state %d! (line '%s')" % (state, line))

	commentbuf += buf

	if patchbuf == '':
		patchbuf = None

	if commentbuf == '':
		commentbuf = None

	return (patchbuf, commentbuf)


def patch_get_filenames(str):
	# normalise spaces
	str = str.replace('\r', '')
	str = str.strip() + '\n'
	__filename_re = re.compile('^(---|\+\+\+) (\S+)')

	filenames = {}

	for line in str.split('\n'):

		if len(line) <= 0:
			continue

		filename_match = __filename_re.match(line)
		if not filename_match:
			continue

		filename = filename_match.group(2)
		if filename.startswith('/dev/null'):
			continue

		filename = '/'.join(filename.split('/')[1:])
		filenames[filename] = True

	filenames = sorted(filenames.keys())

	return filenames

"""
def parse_revision(cmt):
	full_patch = _git.log('-1', '-p', '--format='+gitlog_format , cmt, _tty_out=False)
	full_patch = full_patch.stdout.decode('utf-8', errors='ignore')
	payload_hash = _git("patch-id", _in=StringIO(full_patch), _tty_out=False).stdout.decode().split()
	if payload_hash:
		payload_hash = payload_hash[0]
	else:
		print('%s has no payload - skipping' % (cmt))
		return None
	payload, non_payload = parse_patch(full_patch)
#	payload = payload and payload or ''
	files = payload and patch_get_filenames(payload) or []
	tags_dict = parse_tags(non_payload)
	non_payload = re.sub('\s*[A-Za-z\-]+\: .+\r*\n', '', non_payload, re.DOTALL | re.MULTILINE)
	match = re.search("---\n", non_payload)
	if match:
		non_payload = non_payload[:match.span()[0]]
#	description = non_payload.strip()
#	commit_id = tags_dict["Commit"][0]
	subject = tags_dict["Subject"][0]
	unixtime = int(tags_dict["Commit-Date"][0])
	orig_date = time.strftime('%Y-%m-%d %H:%M:%S-0000', time.localtime(unixtime))
#	submitted_by = __email_tag_to_Person(tags_dict["Committer"][0])
#	submitted_by = tags_dict["Committer"][0]
#	author = tags_dict["Author"][0]
	patch, created = Patch.objects.get_or_create(
		payload_hash = payload_hash,
		defaults = { 'subject' : subject, 'files' : files , 'orig_date' : orig_date } )
#	if not created:
#		print("DUPLICATE: commit {} has hash {}".format(cmt, payload_hash))
	return patch
"""

def get_patch_id(cmt):
	full_patch = _git.log('-1', '-p', '--format='+gitlog_format , cmt, _tty_out=False)
	full_patch = full_patch.stdout.decode('utf-8', errors='ignore')
	payload_hash = _git("patch-id", _in=StringIO(full_patch), _tty_out=False).stdout.decode().split()
	if payload_hash:
		payload_hash = payload_hash[0]
	else:
		print('%s has no payload - skipping' % (cmt))
		return None
	return payload_hash

def get_patch_dict(cmt):
	full_patch = _git.log('-1', '-p', '--format='+gitlog_format , cmt, _tty_out=False)
	full_patch = full_patch.stdout.decode('utf-8', errors='ignore')
	payload_hash = _git("patch-id", _in=StringIO(full_patch), _tty_out=False).stdout.decode().split()
	if payload_hash:
		payload_hash = payload_hash[0]
	else:
		print('%s has no payload - skipping' % (cmt))
		return None
	payload, non_payload = parse_patch(full_patch)
	tags_dict = parse_tags(non_payload)
	tags_dict["files"] = payload and patch_get_filenames(payload) or []
	non_payload = re.sub('\s*[A-Za-z\-]+\: .+\r*\n', '', non_payload, re.DOTALL | re.MULTILINE)
	match = re.search("---\n", non_payload)
	if match:
		non_payload = non_payload[:match.span()[0]]
	tags_dict["non_payload"] = re.sub('\s*[A-Za-z\-]+\: .+\r*\n', '', non_payload, re.DOTALL | re.MULTILINE)
	tags_dict["patch-id"] = payload_hash
	return tags_dict


# regular expression of change size line
__reptn_chgszln = r'^\s*\d+\s+files?\s+changed(?:,\s+(\d+)\s+insertions?\(\+\))?(?:,\s+(\d+)\s+deletions?\(\-\))?'
# regular expression of start line of patch
__reptn_first_ptchln = r'^diff '
# last comment message line
__last_cmln = r'---'
def parse_tags2(text):
    committed_by  = None
    textlines = re.sub('\r', '', text).splitlines()
    tag_dict = {}
    tag_list = []
    match = re.search(r'^(Commit:|From)\s+([0-9a-f]{8,40})\s+', textlines[0])
    if match:
        tag_dict["commit_id"] = match.group(2)

    subject_begin_flag = False
    desc_begin_flag = False
    last_cmln_flag = False
    tag = None
    reptn_blankln = r'^\s*$'
    reptn_tagname = r'^([A-Z][A-Za-z\-]+):\s*(.+)$'
    # sample: "4 files changed, 283 insertions(+), 5 deletions(-)"
    # Find all the 'Xxxxx-By: name <email>' lines in the commit message
    known_tags = (
       'Change-Id',
       'Signed-off-by',
       'Reviewed-on',
       'Reviewed-by',
       'Tested-by',
       'Tracked-On',
    )
    # patch header sample:
    #   Commit: 41715d2b5a9b5c652ca19c251a0c001cfb89c547
    #   Author: Dronamraju Santosh Pavan Kumar <santosh.pavan.kumarx.dronamraju@intel.com>
    #   Author-Date: 2017-08-16 17:04:49 +0530
    #   Committer: Pankaj Bharadiya <pankaj.laxminarayan.bharadiya@intel.com>
    #   Commit-Date: 2018-06-05 09:34:25 +0530
    #   Subject: ASoC: Intel: CNL: Remove larger frame size warnings from ...
    #
    #   Below warning message observed due to static allocation of struct
    #   skl_module_cfg and struct skl_module in above mentioned functions:
    #
    #   warning: the frame size of 85664 bytes is larger than 2048 bytes
    #
    #   To avoid this warning memory is allocated dynamically.
    #
    #   Change-Id: I62beb19219b70640a4e7391604b2f3884897e7d4
    #   Signed-off-by: Dronamraju Santosh Pavan Kumar <santosh.pavan.kumarx.dronamraju@intel.com>
    #   Reviewed-on: https://git-gar-1.devtools.intel.com/gerrit/17607
    #   Reviewed-by: Singh, Guneshwor O <guneshwor.o.singh@intel.com>
    #   Reviewed-by: Tewani, Pradeep D <pradeep.d.tewani@intel.com>
    #   Reviewed-by: Shaik, Kareem M <kareem.m.shaik@intel.com>
    #   Reviewed-by: Prusty, Subhransu S <subhransu.s.prusty@intel.com>
    #   Reviewed-by: Kp, Jeeja <jeeja.kp@intel.com>
    #   Reviewed-by: Koul, Vinod <vinod.koul@intel.com>
    #   Tested-by: Sm, Bhadur A <bhadur.a.sm@intel.com>
    #   ---
    for l in textlines[1:]:
        if subject_begin_flag:
            match = re.search(reptn_blankln, l)
            # check if subject section ends
            if match:
                subject_begin_flag = False
                desc_begin_flag = True
                tag_dict['desc'] = ''
            else:
                tag_dict['subject'] += l

            continue
        match = re.search(reptn_tagname, l)
        if desc_begin_flag:
            # check if descripton section ends
            if match and match.group(1) in known_tags:
                desc_begin_flag = False
                tag = [match.group(1), match.group(2)]
            elif l == __last_cmln:
                desc_begin_flag = False
                last_cmln_flag = True
            else:
                tag_dict['desc'] += l + '\n'

            continue

        if last_cmln_flag:
            match = re.search(__reptn_chgszln, l)
            if match:
                tag_dict['size'] = [
                    int(match.group(1)) if match.group(1) else 0,
                    int(match.group(2)) if match.group(2) else 0,
                ]
                break
            else:
                continue

        if match:
            # if a previous tag exist, it ends here
            if tag:
                tag_list.append(tag)
                tag = None

            if match.group(1) == 'Subject':
                subject_begin_flag = True
                tag_dict['subject'] = match.group(2)
            else:
                tag = [match.group(1), match.group(2)]
        elif l == __last_cmln:
            last_cmln_flag = True
            if tag:
                tag_list.append(tag)
                tag = None
        else:
            match = re.search(reptn_blankln, l)
            # ignore blank line
            if match:
                continue
            elif tag:
                tag[1] += l

    match = re.search(r'=?UTF-8?', tag_dict['subject'], re.IGNORECASE)
    if match:
        tag_dict['subject'] = str(decode_header(tag_dict['subject'])[0][0])
    match = re.search(r'=?UTF-8?', tag_dict['desc'], re.IGNORECASE)
    if match:
        tag_dict['desc'] = str(decode_header(tag_dict['desc'])[0][0])
    for tupl in tag_list:
        tagname = tupl[0]
        tagcont = tupl[1]
        match = re.search(r'=?UTF-8?', tagcont, re.IGNORECASE)
        if match:
            tagcont = str(decode_header(tagcont)[0][0])
        obj = None
        for t in __tag_value_parse_table:
            match = t[0].search(tagcont)
            if match and tagname != 'Subject' :
                obj = t[1](tagname, match)
                break
            else:
                obj = tagcont
        if not tagname in tag_dict:
            tag_dict[tagname] = []
        tag_dict[tagname].append(obj)
    return tag_dict


def parse_patch2(text):
    # strip tailing blank lines as well as the version footer
    # -- 
    # 2.x.x
    text_lst = text.rstrip().splitlines()[:-2]
    # patch text sample:
    #   Change-Id: Ieb8e83054bef9a15ee454f76f422b43b45faf93f
    #   Tracked-On: OAM-72691
    #   Signed-off-by: Romli, Khairul Anuar <khairul.anuar.romli@intel.com>
    #
    #   ---
    #    bxt/android/non-embargoed/acrn_guest_diffconfig | 1 +
    #    1 file changed, 1 insertion(+)                        <-- (mark line)
    #
    #   diff --git a/bxt/android/non-embargoed/acrn_guest_diffconfig b/bxt/...
    #   index fbf5477..9df1af9 100644
    payload = None
    non_payload = None
    last_cmln_flag = False
    chgszln_flag = False
    for i, l in enumerate(text_lst):
        if l == __last_cmln:
            last_cmln_flag = True
            continue

        match = re.search(__reptn_chgszln, l)
        if match:
            chgszln_flag = True
            continue

        match2 = re.search(__reptn_first_ptchln, l)
        if match2 and last_cmln_flag and chgszln_flag:
            # find the first line of payload
            non_payload = text_lst[:i]
            payload = text_lst[i:]
            break

    return (os.linesep.join(payload), os.linesep.join(non_payload))
