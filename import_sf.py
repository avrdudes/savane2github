#!/usr/bin/env python
#
# ----------------------------------------------------------------------------
# "THE BEER-WARE LICENSE" (Revision 42):
# Joerg Wunsch wrote this file.  As long as you retain this notice you
# can do whatever you want with this stuff. If we meet some day, and you think
# this stuff is worth it, you can buy me a beer in return.        Joerg Wunsch
# ----------------------------------------------------------------------------
#

"""
import_sf.py - Helper to import SourceForge.net issue trackers to GitHub

This operates on a SourceForge.net project export.

Unpack it into a temporary directory. All issue trackers can be found
there in separate JSON files named <issuetype>.json. This script
operates on such a JSON file, and generates a JSON file equivalent to
what savane2github.py produces after step #3.

./import_sf.py /some/temp/dir/project-backup-date/bugs.json \
  > project/trackers_bugs.json

Use savane2github.py then to import it to GitHub:

./savane2github.py --username user --project project \
  --access-token ghp_xxxxxxxxxxxxxxxxxx --repo-path where/project \
  --export-bugs

"""

import json
import sys
import re

def map_status(s):
    "map SF.net status to Savannah status and resolution"
    # closed_status_names:
    # closed wont-fix closed-invalid closed-fixed closed-works-for-me
    # open_status_names
    # open unread accepted pending
    if s == 'closed':
        return ('Closed', 'Fixed')
    if s == 'wont-fix' or s == 'closed-wont-fix':
        return ('Closed', 'Wont Fix')
    if s == 'closed-invalid':
        return ('Closed', 'Invalid')
    if s == 'closed-fixed':
        return ('Closed', 'Fixed')
    if s == 'closed-works-for-me':
        return ('Closed', 'Works For Me')
    if s == 'closed-duplicate':
        return ('Closed', 'Duplicate')
    if s == 'open' or s == 'unread' or s == 'accepted':
        return ('Open', 'None')
    if s == 'pending':
        return ('Open', 'In Progress')
    return ('Open', 'None') # not supposed to happen

def cleanup(s):
    "Remove unneeded backslashes from text"
    s = s.replace('&lt;', '<')
    s = s.replace('&gt;', '>')
    pat1 = re.compile(r'\\([-+*_{}()])')
    return pat1.sub('\g<1>', s)

if len(sys.argv) <= 1:
    sys.stderr.write("usage: import_sf.py <filename>\n")
    sys.exit(1)

f = open(sys.argv[1])
j = json.load(f)
f.close()

urlbase = 'https://sourceforge.net' + j['tracker_config']['options']['url']
issuetype = j['tracker_config']['options']['mount_point']

# 'mount_point' is 'bugs', 'patches' and so on -> turn into singular
if issuetype.endswith('es'):
    issuetype = issuetype[:-2]
elif issuetype.endswith('s'):
    issuetype = issuetype[:-1]

result = []
tickets = j['tickets']

for t in tickets:
    o = {} # o = "output"
    o['_json_type'] = 'Tracker'
    o['migration_id'] = None
    o['migration_status'] = 'pending'
    o['type'] = issuetype
    o['item_id'] = t['ticket_num']
    o['url'] = urlbase + str(t['ticket_num']) + '/'
    o['summary'] = t['summary']
    (s, r) = map_status(t['status'])
    o['status_id'] = s
    o['resolution_id'] = r
    o['originator_name'] = t['reported_by']
    o['originator_email'] = None
    o['summary'] = cleanup(t['summary'])
    o['description'] = {
        '_json_type': 'TrackerComment',
        'migration_status': 'pending',
        'author': None,
        'time': t['created_date'],
        'text': cleanup(t['description'])
    }
    comments = []
    attachments = []
    for p in t['discussion_thread']['posts']:
        if len(p['text']) > 0:
            c = {
                '_json_type': 'TrackerComment',
                'migration_status': 'pending',
                'author': p['author'],
                'time': p['timestamp'],
                'text': cleanup(p['text'])
            }
            comments.append(c)
        for a in p['attachments']:
            at = {
                '_json_type': 'TrackerAttachment',
                'text': a['path'].split('/')[-1],
                'url': a['url']
            }
            attachments.append(at)

    o['comments'] = comments
    o['attachments'] = attachments

    result.append(o)

print(json.dumps(result, indent=4))
