# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Parse a raw log captured from mtplot into a format compatible with replay.py

This script loads an mtplot log and parses it generating a pickled file called
path.p that contains a list of events.  Each event is a list of 0 or more tuples
representing coordinates with x and y ranges from 0.0 to 1.0.

For example the generated path for a very simple log may look like:
    [
       [(0.1, 0.1)],
       [(0.15, 0.2)],
       [(0.2, 0.27), (0.8, 0.9)]
    ]

This is achieved by scaling all the x and y reading by their maximum range
and eliminated most of the unneeded information in the mtplot log.

To use this script, first capture a log by running the following command
and performing your gesture on the pad.
    DISPLAY=:0 mtplot > my_mtplot_log.txt
Then parse it with this script
    python parse_log my_mtplot_log.txt
It will generate a path.p for you that can then be replayed on the touchbot
with the replay.py script.
"""

import pickle
import re
import sys

from collections import defaultdict


CODE_X = 'ABS_MT_POSITION_X'
CODE_Y = 'ABS_MT_POSITION_Y'
CODE_SLOT = 'ABS_MT_SLOT'
CODE_TRACKING_ID = 'ABS_MT_TRACKING_ID'

MAX_FINGERS = 10

min_vals = {}
max_vals = {}
range_vals = {}
curr_header_slot = None

events = []
slot = 0
curr_state = defaultdict(lambda: {})

with open(sys.argv[1], 'r') as fo:
    for line in fo:
        header_matches = re.search('\W*Event code \d* \(([A-Z_]*)\)\W*', line)
        if header_matches:
            curr_header_slot = header_matches.groups()[0]

        min_matches = re.search('\W*Min\W*(\d*)\W*', line)
        if min_matches:
            min_vals[curr_header_slot] = int(min_matches.groups()[0])

        max_matches = re.search('\W*Max\W*(\d*)\W*', line)
        if max_matches:
            max_vals[curr_header_slot] = int(max_matches.groups()[0])

        if min_matches or max_matches:
            range_vals[curr_header_slot] = float(
                                            max_vals.get(curr_header_slot, 0) -
                                            min_vals.get(curr_header_slot, 0)
                                           )

        # Handle the actual events
        event_matches = re.search('Event: time[^(]*\([^(]*\)[^(]*\(([A-Z_]*)\)'
                                  ', value ([0-9\-]*).*', line)
        if event_matches:
            value_name = event_matches.groups()[0]
            value = int(event_matches.groups()[1])
            if value_name == CODE_TRACKING_ID:
                if value == -1:
                    curr_state[slot] = {}
            elif value_name == CODE_SLOT:
                slot = value
            elif slot >= 0:
                curr_state[slot][value_name] = value

        # Copy over the X and Y values when you get a SYN_REPORT
        # and scale them to between 0.0 and 1.0
        if re.search('SYN_REPORT', line):
            positions = []
            for s in curr_state:
                if not curr_state[s].get(CODE_X, None):
                    continue
                if not curr_state[s].get(CODE_Y, None):
                    continue

                scaled_x = ((curr_state[s][CODE_X] - min_vals[CODE_X]) /
                            range_vals[CODE_X])
                scaled_y = ((curr_state[s][CODE_Y] - min_vals[CODE_Y]) /
                            range_vals[CODE_Y])
                positions.append((scaled_x, scaled_y))
            events.append(positions)

pickle.dump(events, open('path.p', 'w'))
print 'Your parsed log has been saved to disk as "path.p"'
