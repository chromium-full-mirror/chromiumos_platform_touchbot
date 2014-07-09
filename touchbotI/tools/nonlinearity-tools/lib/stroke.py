# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from itertools import izip
import pickle

import numpy as np


class Stroke:
    """ A class to hold all the position data for a single continuous motion

    A 'Stroke' is essentially a list of (t, x, y, p) tuples storing:
        * Time-stamp
        * X & Y positions
        * Pressure value
    but with some helper functions allowing you to easily do file i/o, line
    fitting, and stroke validation for non-linearity analysis.
    """
    MIN_STROKE_LENGTH = 10
    MIN_STROKE_TIME = 0.5
    MAX_FIT_DEVIATION = 85
    MAX_AVG_FIT_DEVIATION = 78
    MAX_SLOPE_DEVIATION = 0.15

    def __init__(self, events=[]):
        self.events = events

    def __iter__(self):
        for event in self.events:
            yield event

    @classmethod
    def load_from_file(cls, filename):
        """ Load events from a file and create a new Stroke """
        return cls(pickle.load(open(filename, 'rb')))

    def save_to_file(self, filename):
        """ Store the stroke to disk as a pickled list to be read later """
        pickle.dump(self.events, open(filename, "wb"))

    def compute_error(self):
        """ Compute the error at each point for a stroke """
        ideal = self.find_ideal()
        error = [ ((sx, sy, sp), (sx - ix, sy - iy))
                  for (it, ix, iy, ip), (st, sx, sy, sp)
                  in izip(ideal, self.events) ]
        return dict(error)

    def find_ideal(self, degree=1):
        """ Fit a nice smooth polynomial to the events in this stroke"""
        poly_x = np.polyfit([t for t, x, y, p in self.events],
                            [x for t, x, y, p in self.events], degree)
        poly_y = np.polyfit([t for t, x, y, p in self.events],
                            [y for t, x, y, p in self.events], degree)
        return [(t, np.polyval(poly_x, t), np.polyval(poly_y, t), p)
                for t, x, y, p in self.events]

    def clip(self, clip_amount=30):
        """ Clip both ends and returns the number of remaining events """
        if len(self.events) > 2 * clip_amount:
            self.events = self.events[clip_amount:-clip_amount]
        else:
            self.events = []
        return len(self.events)

    def is_useful(self):
        """ Checks several things about the stroke to confirm that is is
        suitable for use in non-linearity filter computation.
        """
        if not self.events:
            return False
        if len(self.events) < self.MIN_STROKE_LENGTH:
            return False
        if self.events[-1][0] - self.events[0][0] < self.MIN_STROKE_TIME:
            return False

        ideal = self.find_ideal()
        deviations = [self._distance(s, i) for s, i in izip(self.events, ideal)]
        if max(deviations) > self.MAX_FIT_DEVIATION:
            return False
        avg_deviation = sum(deviations) / len(deviations)
        if avg_deviation > self.MAX_AVG_FIT_DEVIATION:
            return False

        if ideal[-1][1] == ideal[0][1]:
            return False
        slope = (ideal[-1][2] - ideal[0][2]) / (ideal[-1][1] - ideal[0][1])
        if abs(abs(slope) - 1.0) > self.MAX_SLOPE_DEVIATION:
            return False

        return True

    def _distance(self, e1, e2):
        t1, x1, y1, p1 = e1
        t2, x2, y2, p2 = e2
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
