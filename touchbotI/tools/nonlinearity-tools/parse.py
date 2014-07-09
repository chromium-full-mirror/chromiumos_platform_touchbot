# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Parse activity logs into individual pickled strokes

Given a series of activity logs from the touchpad, this parses and dedupes the
events, then separates them into individual strokes across the pad.  Each of
these strokes is then saved to disk in it's own stroke##.p file for further
processing.

Usage: python parse.py linearity_logs/*.txt
"""

import json
import sys

from lib.progress import ProgressBar
from lib.stroke import Stroke


logs = sys.argv[1:]

# First get all of the hardwareState events and store them all in one big list
print "Parsing the logs..."
bar = ProgressBar(len(logs))
data = []
for log in logs:
    # Open up each log and parse the json
    log_data = json.load(open(log, 'r'))

    # We are only interested in the hardwareState entries
    hwstates = [e for e in log_data.get('entries')
                if e.get('type') == 'hardwareState']

    if hwstates:
        bar.subtask(len(hwstates))
        for e in hwstates:
            fingers = e.get('fingers')
            if len(fingers) == 0:
                # Add dummy events to indicate the end of a stroke
                data.append((e.get('timestamp'), None, None, None))
            elif len(fingers) == 1:
                # Otherwise, add a new event onto the stroke
                t = e.get('timestamp')
                x = fingers[0].get('positionX')
                y = fingers[0].get('positionY')
                p = fingers[0].get('pressure')
                data.append((t, x, y, p))
            bar.progress()
    bar.progress()

# Sort and dedupe the list of events
data = sorted(data, key=lambda tup: tup[0])
events = []
for i, e in enumerate(data[0:-2]):
    timestamp, next_timestamp = e[0], data[i + 1][0]
    consecutive_empty_values = e[1] is None and data[i + 1][1] is None
    if timestamp != next_timestamp and not consecutive_empty_values:
        events.append(e)

# Split the list of events into individual Strokes wherever the finger lifted
strokes = []
current_stroke = []
for e in events:
    if e[1] == None:
        strokes.append(Stroke(current_stroke))
        current_stroke = []
    else:
        current_stroke.append(e)
if current_stroke:
    strokes.append(Stroke(current_stroke))

# Write the "good" (straight and long) strokes to disk
print "Writing the strokes to disk..."
bar = ProgressBar(len(strokes))
for i, stroke in enumerate(strokes):
    stroke.clip()
    if stroke.is_useful():
        stroke.save_to_file('stroke%d.p' % i)
    bar.progress()

print "Done.  The results are stored in stroke###.p"
