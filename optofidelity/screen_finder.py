# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This script attempts to detect the region of a camera's field of view that
# contains the screen of the device we are testing.  Without a script like this
# ever time the camera moves, everything needs to be recalibrated by hand.
#
# Essentially the way it works, is you pass in a video of the device that was
# filmed while its screen was flashing black & white rapidly.  The script
# uses this to build a polygon inclosing the flashing area.
#
# Usage: python screen_finder.py filename.mp4

import sys

import cv2
import numpy as np

VIDEO_FILENAME = sys.argv[1]
NEIGHBOR_BOX = 2
THRESHOLD = 20

# Load the video from disk and get it ready
capture = cv2.VideoCapture(VIDEO_FILENAME)
ret, frame = capture.read()
if not ret:
    print 'Error: no frames in video read!'
    sys.exit(1)
prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
diff = np.zeros(prev_frame.shape)

# Go through each frame and calculate the RMS of changes for each pixel between
# adjacent frames to figure out which pixels are flashing the most
frame_number = 0
while (capture.isOpened()):
    # Get the new frame
    ret, frame = capture.read()
    if not ret:
        break
    curr_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_number += 1
    print 'Processing frame %d' % frame_number

    # Diff the frame against the last one
    curr_diff = cv2.absdiff(prev_frame, curr_frame).astype(np.float64)
    curr_diff = cv2.multiply(curr_diff, curr_diff)
    last_frame = curr_frame

    # Acumulate the differences
    diff = np.add(diff, curr_diff)

averaged = np.divide(diff, frame_number)
scaled = np.divide(averaged, np.max(averaged) / 255.0).astype(np.uint8)
ret, thresh = cv2.threshold(scaled, THRESHOLD, 255, cv2.THRESH_BINARY)

# Remove any lit pixels that aren't surrounded by other lit pixels
thresh_cp = np.copy(thresh)
w, h = thresh.shape
for x in range(w):
    for y in range(h):
        should_be_lit = thresh.item(x, y)
        if should_be_lit:
            for x_off in range(-NEIGHBOR_BOX, NEIGHBOR_BOX + 1):
                for y_off in range(-NEIGHBOR_BOX, NEIGHBOR_BOX + 1):
                    xn = x + x_off
                    yn = y + y_off
                    if xn < 0 or xn >=w or yn < 0 or yn >= h:
                        continue
                    should_be_lit = should_be_lit and thresh.item(xn, yn)
        if should_be_lit:
            thresh_cp.itemset((x, y), True)
        else:
            thresh_cp.itemset((x, y), False)
thresh = thresh_cp

# Find the biggest connected component
contours, hierarchy = cv2.findContours(thresh,
                                       cv2.RETR_TREE,
                                       cv2.CHAIN_APPROX_SIMPLE)
max_area = 0
max_contour = None
for contour in contours:
    area = cv2.contourArea(contour)
    if area > max_area:
        max_area = area
        max_contour = contour

# Take its convex hull to simplify the shape a bit
hull = cv2.convexHull(max_contour)

#Display the shape on the screen
cv2.drawContours(scaled, [hull], 0, 255, 2)
cv2.imshow('Automatic Screen Location Detection', scaled)
cv2.waitKey(0)

cv2.destroyAllWindows()
