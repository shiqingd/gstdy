#!/usr/bin/env python3

import re
import sys
import yaml

# the simplest, lambda-based implementation
def multiple_replace(adict, text):
    # Create a regular expression from all of the dictionary keys
    regex = re.compile("|".join(map(re.escape, adict.keys())))

    # For each match, look up the corresponding value in the dictionary
    return regex.sub(lambda match: adict[match.group(0)], text)


def make(yml_fl):
    # Read YAML file
    with open(yml_fl, 'r') as yf:
        ciyml = yaml.safe_load(yf)
        yf.seek(0)
        text = yf.read()

    #envs = { (r'${{\s*env\.%s\s*}}' % k): v for k,v in ciyml['env'].items() }
    # doesn't work
    #text = multiple_replace(envs, text)
    for k,v in ciyml['env'].items():
        text = re.sub(r'\${{\s*env\.%s\s*}}' % k, str(v), text)

    newfl = re.sub(r'-template', '', yml_fl)
    if newfl == yml_fl:
        newfl = "%s.new" % yml_fl
    with open(newfl, 'w') as new_yf:
        new_yf.write(text)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        make(sys.argv[1])
