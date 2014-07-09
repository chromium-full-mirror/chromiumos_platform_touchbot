# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Compute the touch latency by processing HS camera footage

The purpose of this script is to measure how much latency there is in the hw,
fw, and kernel relating to a touchpad or touchscreen.  First you need a very
carefully created video of the touchpad in use:

    1) First, find a free GPIO that the kernel can control.  Connect an LED and
    resistor to it so that the kernel can turn the LED on and off.
    2) Instrument your kernel so that every time an input event is reported by
    a driver, it checks to see if it is on the right or left side of the pad,
    simply by checking the X position reported.  If it is on one side, turn the
    LED on, otherwise turn the LED off.
    4) Set up a high speed camera arranged perpendicularly to the touch
    surface.  Ensure that the LED is in view as well as the touch surface.
    3) Get a probe and draw concentric circles on the back of it (to allow this
    script to track it easier in the video) and repeatedly slide the probe
    back and forth over the "line" so that the LED turns on and off.

Once you have this video you can analyze it my simply passing the file in as
the first argument to this script.

    python compute_latency.py path/to/my/high_speed_video.mkv

You will be prompted to click first the LED and then the probe before pressing
any key to start the processing.  When it is finished it will show you a
graphic depiction of what it thinks the probe/led did during the video before
computing the results as a sanity check to make sure the computer vision didn't
make any major mistakes.

The actual technique consists of a couple parts
    LED - As the LED is stationary, it simply samples the shade of grey around
    the position of the LED each frame and determines it to be on or off.
    PROBE - To track the probe each frame is blurred to reduce noise and edge
    detection is used in conjunction with a Hough filter to find circles.  The
    circles found are compared to the probes position in the previous frame and
    a likely candidate is chosen.

Once the positions and their corresponding led state are found all the places
where the led changed state are noted and used to estimate the "line" position.
This works because these positions should lie about equidistant on either side
of the "line" and it turns out that the average latency will compensate even if
the "line" isn't found perfectly.  Tilting it closer to one side will make it
equally far away from the other and the average will work out to be the same.

With our line found, it is simply a matter of counting how many frames it takes
after the probe crosses the line for the led to change state.
"""
import numpy as np
import sys

from cv2 import cv
from sklearn import svm, preprocessing

WINDOW_NAME = 'High Speed Analysis'
MAX_MOVEMENT = 20
WHITE = 255
RED = (0, 0, 255)
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
YELLOW = (0, 255, 255)

# Global variables for the MouseHandler to set and calibrate the test
led = (0, 0)
probe = (0, 0)
next_click = 0


def MouseHandler(evt, x, y, flags, param):
    """ This handler fires when the user clicks points on the display,
    allowing them to seed the initial values for the position of the
    probe and LED.
    """
    global led, next_click, probe
    if (evt == cv.CV_EVENT_LBUTTONDOWN):
        x, y = int(x), int(y)
        if next_click == 0:
            led = x, y
            print 'LED position: (%d, %d)' % (x, y)
        else:
            probe = x, y
            print 'Probe initial position: (%d, %d)' % (x, y)
        next_click = (next_click + 1) % 2


def CalibrateStartingPositions(frame):
    """ Display the frame of the video while the operator calibrates where
    the LED and probe are in it, then wait for a key press before continuing
    """
    global led, probe
    cv.ShowImage(WINDOW_NAME, frame)
    cv.SetMouseCallback(WINDOW_NAME, MouseHandler, 0)
    print 'Click the LED and then the probe before pressing any key to start'
    cv.WaitKey(0)
    return led, probe


def GetLedIntensity(img, led_pos, led_size=4):
    """ Average the intensity of the pixels in a box around the LED """
    intensity = count = 0
    for x in range(led_pos[0] - led_size/2, led_pos[0] + led_size/2):
        for y in range(led_pos[1] - led_size/2, led_pos[1] + led_size/2):
            if x < 0 or x >= img.width or y < 0 or y >= img.height:
                continue
            # Note: openCV images are stored row-wise so you index [y, x]
            intensity += img[y, x]
            count += 1

    return intensity / float(count) if count > 0 else 0.0


def Distance(pt1, pt2):
    """ Compute the distance squared between two points """
    x1, y1 = pt1
    x2, y2 = pt2
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def GetProbePosition(img, last_pos):
    """ Find the position of the probe in img given it's last position """
    # First, make a copy of the image to manipulate
    tmp = cv.CreateImage((img.width, img.height), img.depth, 1)
    cv.Copy(img, tmp)

    # Blur the image to reduce noise and detect edges using a Canny filter
    #cv.EqualizeHist(tmp, tmp)
    cv.Smooth(tmp, tmp, cv.CV_GAUSSIAN, 3, 3)
    cv.Canny(tmp, tmp, 5, 70, 3)

    # Next run HoughCircle detection to find probe-sized circles
    circles = cv.CreateMat(tmp.width, 1, cv.CV_32FC3)
    cv.HoughCircles(tmp, circles, cv.CV_HOUGH_GRADIENT,
                    2, 150.0, 30, 50, 10, 30)

    # If we found any circles, return the center of the one closest to where
    # we last saw the probe (assumes it didn't jump a huge amount)
    if circles.rows > 0:
        cs = [(int(x), int(y), int(r)) for ((x, y, r),) in np.asarray(circles)]
        probe = min(cs, key=lambda c: Distance((c[0], c[1]), last_pos))
        x, y, r = probe
        if Distance((x, y), last_pos) < MAX_MOVEMENT:
            return x, y

    # We didn't find the probe this time -- return the last known position
    return last_pos


def Smooth(x, beta=15, window=11):
    """ Smooth the values in the list x using Kaiser window smoothing """
    s = np.r_[x[window-1:0:-1], x, x[-1:-window:-1]]
    w = np.kaiser(window, beta)
    y = np.convolve(w / w.sum(), s, mode='valid')
    return y[5:len(y) - 5]

def TrackLedAndProbe(capture, led_inital_pos, probe_initial_pos, display=False):
    """ Given the starting positions and the video capture object, go through
    each frame and track the location of the probe and the intensity of the LED
    """
    led_intensities = []
    probe_positions = []
    frame_num = 0
    probe = probe_initial_pos
    led = led_initial_pos
    while True:
        frame_num += 1
        print 'Processing frame %d' % frame_num

        # Get the frame and convert it to 8-bit grayscale
        frame = cv.QueryFrame(capture)
        if not frame:
            break
        img = cv.CreateImage(cv.GetSize(frame), 8, 1)
        cv.CvtColor(frame, img, cv.CV_BGR2GRAY)

        # Note the led intensity
        led_intensities.append(GetLedIntensity(img, led))

        # Find the probe
        probe = GetProbePosition(img, probe)
        probe_positions.append(probe)

        if display:
            # Annotate the positions directly onto the image
            cv.Circle(img, led, 10, WHITE, thickness=2)
            cv.Circle(img, probe, 10, WHITE, thickness=3)

            # Display the annotated image live as it's computed
            cv.ShowImage(WINDOW_NAME, img)
            cv.WaitKey(1)

    return led_intensities, probe_positions


def FindEdgePoints(led_state, probe_positions):
    """ Find the probe's position when the LED changed states.
    This additionally returns a list of which state the LED changed to
    at those places.
    """
    edges = []
    classes = []
    for i, (pos, led_state) in enumerate(zip(probe_positions, led_states)):
        if i == 0:
            continue
        if led_states[i-1] != led_state:
            edges.append(pos)
            classes.append(led_state)
    return edges, classes


def EstimateLine(edge_points, classes):
    """ Estimate where the line is by looking at the points where the LED
    Changed. With these you can use an svm to estimate where the line is
    """
    scaler = preprocessing.Scaler().fit(edge_points)
    clf = svm.LinearSVC()
    clf.fit(scaler.transform(edge_points), classes)
    return scaler, clf


def Annotate(frame, scaler, line, edge_points, edge_classes, probe_positions):
    """ Add annotations to frame, displaying the probe path, discovered line,
    and the edge points color coded to indicate which way the LED was changing
    """
    for i, (x, y) in enumerate(probe_positions[:-1]):
        cv.Line(frame,
                (int(x), int(y)),
                (int(probe_positions[i+1][0]), int(probe_positions[i+1][1])),
                YELLOW, thickness=1)

    for i, (x, y)  in enumerate(edge_points):
        color = RED if edge_classes[i] else GREEN
        cv.Circle(frame, (int(x), int(y)), 1, color, thickness=2);

    class_top = [line.predict(scaler.transform([[float(x), 0.0]])[0])
                 for x in range(frame.width)]
    class_bot = [line.predict(
                    scaler.transform([[float(x), float(frame.height)]])[0]
                    )
                 for x in range(frame.width)]
    intercept_top = [i for i, c in enumerate(class_top[:-1])
                     if class_top[i+1] != c][0]
    intercept_bot = [i for i, c in enumerate(class_bot[:-1])
                     if class_bot[i+1] != c][0]
    cv.Line(frame, (intercept_top, 0), (intercept_bot, frame.height),
            BLUE, thickness=2)


def ComputeDelays(led_states, probe_on_left):
    # Count the number of frames of lag between the probe crossing the line
    # and the LED turning on
    delays = []
    waiting = 0
    for i, (l, p) in enumerate(zip(led_states, probe_on_left)):
        if i == 0:
            continue
        if waiting:
            if led_states[i - 1] != l:
                delays.append(waiting)
                waiting = 0
            else:
                waiting += 1
        elif probe_on_left[i - 1] != p:
                waiting = 1
    return delays


# Initialize OpenCV and load the video from disk
cv.NamedWindow(WINDOW_NAME, cv.CV_WINDOW_AUTOSIZE)
capture = cv.CaptureFromFile(sys.argv[1])
first_frame = cv.QueryFrame(capture)

led_initial_pos, probe_initial_pos = CalibrateStartingPositions(first_frame)
led_intensities, probe_positions = TrackLedAndProbe(capture,
                                                    led_initial_pos,
                                                    probe_initial_pos)

# Post-processing the data.  Determining if the LED is on/off
# and which side of the line the probe is on.
avg_light = sum(led_intensities) / len(led_intensities)
led_states = [l > avg_light for l in led_intensities]
probe_positions = zip(Smooth([x for x, y in probe_positions]),
                      Smooth([y for x, y in probe_positions]))

edge_points, edge_classes = FindEdgePoints(led_states, probe_positions)
scaler, line = EstimateLine(edge_points, edge_classes)
probe_on_left = [line.predict(scaler.transform([[x, y]])[0])
                 for x, y in probe_positions]

# Measure the delay and trim outliers
delays = ComputeDelays(led_states, probe_on_left)
min_delay = min(delays)
max_delay = max(delays)
delays = [d for d in delays if d != max_delay and d != min_delay]
print 'Delays (in frames):', delays
print 'avg: %f' % (sum(delays) / float(len(delays)))

# Give the user a chance to review the data on the screen before quitting
Annotate(first_frame, scaler, line, edge_points, edge_classes, probe_positions)
cv.ShowImage(WINDOW_NAME, first_frame)
print 'Press any key to quit.'
cv.WaitKey(0)

