# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Style dictionaries used in _hist_figure and _trace_figures.

These dictionaries describe the styling of various figure elements. The
dictionaries are passed to matplotlib plotting methods as keyword arguments.

A description of these can be found in the matplotlib documentation:
http://matplotlib.org/api/lines_api.html#matplotlib.lines.Line2D
"""

# General plot styles

MESSAGE_STYLE = {
  "fontsize": 16,
  "color": "#444444"
}

PASS_MARKER_STYLE = {
  "linewidth": 2,
  "linestyle" : "dashed",
  "color": "#ff9800"
}

# List of colors used for automatic color assignments.
COLOR_ROTATION = [
  "#d32f2f",
  "#512da8",
  "#fbc02d",
  "#388e3c",
  "#0288d1",
  "#795548",
  "#f50057",
  "#536dfe",
  "#00e5ff",
  "#b2ff59",
  "#ffe57f",
]


# Location plot styles

FINGER_STYLE = {
  "color": "#4CAF50",
  "linewidth": 1,
  "linestyle" : "dotted",
  "label": "Finger"
}
CALIB_FINGER_STYLE = {
  "color": "#4CAF50",
  "linewidth": 2,
  "linestyle" : "solid",
  "label": "Finger (calibrated)"
}
LINE_DRAW_START_STYLE = {
  "color": "#2196F3",
  "linewidth": 1,
  "linestyle" : "dotted",
  "label": "Line Draw Start"
}
LINE_DRAW_END_STYLE = {
  "color": "#2196F3",
  "linewidth": 2,
  "linestyle" : "solid",
  "label": "Line Draw End"
}

# Events plot styles

LED_STYLE = {
  "color": "#4CAF50",
  "linewidth": 1,
  "linestyle" : "dotted",
  "label": "LEDs"
}
CALIB_LED_STYLE = {
  "color": "#4CAF50",
  "linewidth": 2,
  "linestyle" : "solid",
  "label": "LEDs (calibrated)"
}
SCREEN_DRAW_START_STYLE = {
  "color": "#2196F3",
  "linewidth": 1,
  "linestyle" : "dotted",
  "label": "Screen Draw Start"
}
SCREEN_DRAW_END_STYLE = {
  "color": "#2196F3",
  "linewidth": 2,
  "linestyle" : "solid",
  "label": "Screen Draw End"
}

# Measurements marker styles

MEASUREMENT_STYLE = {
  "linewidth": 2,
  "linestyle" : "solid",
  "marker": "o",
}
MEASUREMENT_HELPER_STYLE = {
  "linewidth": 1,
  "linestyle" : "solid",
}
DISCRETE_LATENCY_STYLE = {
  "linewidth": 2,
  "linestyle" : "dotted",
  "marker": "o",
}
LATENCY_STYLE = {
  "linewidth": 2,
  "linestyle" : "solid",
}

# Histogram styles

# Here we also define the dimensions of the histogram plots. We want histogram
# plots to be comparable, which is why we cannot automatically scale them.
MIN_LATENCY = 0
"""Minimum latency in ms."""

MAX_LATENCY = 200
"""Maximum latency in ms."""

MAX_REL_FREQ = 0.3
"""Maximum relative frequency expected in histograms."""

HISTOGRAM_STYLE = {
  "color": "#CFD8DC",
  "edgecolor": "#90A4AE",
  "label": "Latency Histogram"
}

SUMMARY_PDF_COLOR = "#546E7A"

MAIN_PDF_STYLE = {
  "linewidth": 3,
  "zorder": 10
}
DRAW_START_PDF_STYLE = {
  "linewidth": 2,
  "linestyle": ":",
}

SECONDARY_PDF_STYLE = {
  "linewidth": 2,
  "linestyle": "-"
}
