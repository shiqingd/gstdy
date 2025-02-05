#!/usr/bin/env python3

import re
import sys

class KernelVersion(object):

	def __init__(self, version:str):
#		r = re.compile('^v([0-9])\.([0-9]+)(?:-r[ct][0-9]+|\.[0-9]{1,3}(?:-rt[0-9]+){0,1}){0,1}$')
		r = re.compile('^v([0-9])\.([0-9]+)(?:[\.\-]){0,1}((?:rc){0,1}[0-9]+){0,1}$')
		match = r.match(version)
		if not match:
			raise ValueError("Invalid Version number " + version)
		self.numeric_version = int(match.group(1))
		self.numeric_version = (self.numeric_version << 8 ) + int(match.group(2))
		if not match.group(3):
			self.numeric_version = (self.numeric_version << 8 )
		elif match.group(3).isnumeric():
			self.numeric_version = (self.numeric_version << 8 ) + int(match.group(3))
		else:
			# -rcX versions treated as vX.Y.0
			# raise ValueError("Release Candidate versions not allowed: " + version)
			self.numeric_version = (self.numeric_version << 8 )

	def major(self):  # Actually, kernel version + major version
		return self.numeric_version >> 8

	def minor(self):
		return (self.numeric_version & 0xFF)

	def __gt__(self, o2:object):
		return self.numeric_version > o2.numeric_version

	def __ge__(self, o2:object):
		return self.numeric_version >= o2.numeric_version

	def __lt__(self, o2:object):
		return self.numeric_version < o2.numeric_version

	def __le__(self, o2:object):
		return self.numeric_version <= o2.numeric_version

	def __eq__(self, o2:object):
		return self.numeric_version == o2.numeric_version

	def __ne__(self, o2:object):
		return self.numeric_version != o2.numeric_version


if __name__ == '__main__':
	kv = KernelVersion(sys.argv[1])
	kv2 = KernelVersion(sys.argv[2])
	print(hex(kv.numeric_version), kv.major(), kv.minor())
	print(hex(kv2.numeric_version), kv2.major(), kv2.minor())
	print(kv == kv2)
	print(kv != kv2)
	print(kv >= kv2)
	print(kv > kv2)
	print(kv <= kv2)
	print(kv < kv2)
	print("Major", kv.major() == kv2.major())
