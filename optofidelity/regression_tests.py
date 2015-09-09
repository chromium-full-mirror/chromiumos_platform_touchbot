#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for debugging command line interface"""
from collections import namedtuple
from fnmatch import fnmatch
import sys
import traceback

import numpy as np

from debugger_main import LoadBenchmarkFromURL
from optofidelity.detection import MultithreadedVideoProcessor
from optofidelity.reporting import BenchmarkReport

Test = namedtuple("test", ("uid", "expectations"))

TEST_DEFINITIONS = {
  "finger.small.s6edge":
      Test("20150825_1410_000", {}),
  "finger.small.s6":
      Test("20150825_1630_000", {}),

  "led.false_suppression.nexus4":
      Test("20150825_1953_000", {}),
  "led.false_suppression.s6edge":
      Test("20150825_1855_001", {}),
  "led.screen_on_edge.s6edge":
      Test("20150903_1018_000", {}),
  "led.false_distance_suppression.m9":
      Test("20150826_2244_000", {}),
  "led.false_distance_suppression.nexus4":
      Test("20150826_2139_000", {}),

  "line.brightness_changed.nexus6":
    Test("20150908_1624_000", Exception),

  "baseline.tap.nexus4":
      Test("20150825_1908_000", {"DownLatency": 98, "UpLatency": 81}),
  "baseline.tap.nexus6":
      Test("20150825_1827_000", {"DownLatency": 63, "UpLatency": 90}),
  "baseline.tap.m9":
      Test("20150825_1730_000", {"DownLatency": 116, "UpLatency": 108})
}

FAILURE_THRESHOLD = 5


def RunBenchmark(benchmark, expectations):
  try:
    video_processor = MultithreadedVideoProcessor()
    benchmark.results.error = ""
    benchmark.ProcessVideo(video_processor, [])
    benchmark.ProcessTrace()
    print "Results:"
    print benchmark.results
    if len(benchmark.results.error):
      return False
    if isinstance(expectations, dict):
      measurements = benchmark.results.measurements
      for value_name, expected in expectations.iteritems():
        actual = np.mean(measurements.SummarizeValues(value_name))
        if abs(actual - expected) > FAILURE_THRESHOLD:
          print "Assertion failed: %s != %d" % (value_name, expected)
          return False
    elif isinstance(expectations, type) and issubclass(expectations, Exception):
      print "Expected exception of type", expectations
      return False
    print "Test successful."
    return True
  except KeyboardInterrupt:
    raise
  except:
    traceback.print_exc()
    if isinstance(expectations, type) and issubclass(expectations, Exception):
      print "Exception expected"
      return True
    return False


def RunTest(name, uid, expectations):
  success = False
  try:
    print "-" * 80
    print "-  %s (%s)" % (name, uid)
    print "-" * 80
    benchmark, url = LoadBenchmarkFromURL(uid)
    success = RunBenchmark(benchmark, expectations)
    benchmark.Save(url)
    if not success:
      report = BenchmarkReport(url)
      report.GenerateReport(benchmark.results, benchmark.trace,
                            benchmark.screen_calibration, benchmark.video)
      print "Test Failed: file://%s/report.html" % url
  except KeyboardInterrupt:
    raise
  except:
    traceback.print_exc()
  return success


def Main():
  pattern = "*"
  if len(sys.argv) > 1:
    pattern = sys.argv[1]

  failed = []
  success = []
  for name, definition in TEST_DEFINITIONS.iteritems():
    if fnmatch(name, pattern):
      if RunTest(name, definition.uid, definition.expectations):
        success.append(name)
      else:
        failed.append(name)

  print
  if len(failed):
    print "%d tests failed:" % len(failed)
    for name in failed:
      print "  %s (%s)" % (name, TEST_DEFINITIONS[name].uid)
  else:
    print "All tests were successful."
if __name__ == "__main__":
  Main()
