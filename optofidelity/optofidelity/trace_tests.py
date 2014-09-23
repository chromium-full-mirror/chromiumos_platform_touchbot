# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Test cases for testing detection features.

Per default all tests are skipped, it is up to the developer to pick which
test to run and manually validate the results.
"""
import matplotlib
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
import pickle
import unittest

from detection import Event, Screen
from trace_generator import TraceGenerator, MultithreadedTraceGenerator
from videoproc import FileVideoReader


def Plot(*args):
  plt.figure()
  plt.plot(*args)
  plt.show()


class TestTraceProcessing(unittest.TestCase):
  """Tests for processing traces.

  The trace files required for this test can be generated using the
  TestTraceGeneration test cases.
  """
  def setUp(self):
    self.trace = pickle.load(open("test.trace"))

  @unittest.skip("")
  def test_debug_print(self):
    print self.trace

  @unittest.skip("")
  def test_time_location(self):
    Plot(self.trace.Times(Event.FINGER_MOVED),
         self.trace.Locations(Event.FINGER_MOVED))

  @unittest.skip("")
  def test_time_location_interp(self):
    x = range(1, 299, 20)
    mapping = self.trace.TimeLocationMap(Event.FINGER_MOVED)
    Plot(x, mapping(x))

  @unittest.skip("")
  def test_linear_motion_trimming(self):
    (start, end) = self.trace.FindLinearMotionRange(Event.FINGER_MOVED)
    trimmed = self.trace.TrimByTime(start.time, end.time)

    times = trimmed.Times()
    print "(start, end) = (%d, %d)" % (start.time, end.time)
    print "(min(times), max(times)) = (%d, %d)" % (min(times), max(times))

    Plot(trimmed.Times(Event.FINGER_MOVED),
         trimmed.Locations(Event.FINGER_MOVED))


if __name__ == '__main__':
  unittest.main()
