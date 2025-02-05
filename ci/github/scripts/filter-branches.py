#!/usr/bin/env python3

import re
import sys
import yaml

excluded_steps = ['re-head_ref-stable']

def get_branches(yml_fl, branch_fl):
    with open(yml_fl, 'r') as yf:
        yml = yaml.safe_load(yf)
    rules = yml['jobs']['prechk']['steps']

    with open(branch_fl, 'r') as bf:
        text = bf.read()
    text = re.sub(r'^\s*origin\/', '', text, flags=re.M)

    regexs = []
    for r in rules:
        if 'with' in r and \
           'regex' in r['with'] and \
           r['id'] not in excluded_steps:

            regexs.append(r['with']['regex'])

    for p in regexs:
        #rep = re.compile(r'%s$' % p)
        rep = re.compile(p)
        for b in text.splitlines():
            m = rep.search(b)
            if m:
                print(b)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        get_branches(sys.argv[1], sys.argv[2])
