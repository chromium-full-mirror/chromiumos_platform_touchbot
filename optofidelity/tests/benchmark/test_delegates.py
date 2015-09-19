# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests of all delegates implementations.

Most importantly this includes tests of trace processing, which processes
recorded traces into measurements.
"""
import cPickle as pickle
import unittest

import numpy as np

from optofidelity.benchmark._line_delegates import (LineDrawDelegate,
                                                    LineDrawStartDelegate)
from optofidelity.benchmark._tap_delegate import TapDelegate
from optofidelity.benchmark.results import (BenchmarkMeasurements,
                                            BenchmarkResults)
from optofidelity.system import BenchmarkSubject
from optofidelity.system.fake import FakeHighSpeedCamera
from tests.config import CONFIG, CreateTestDUTBackend
from . import test_data


class AbstractDelegateTests(unittest.TestCase):
  """Abstract base class for BenchmarkDelegate tests.

  Provides a methods for testing ExecuteOnSubject on a live robot as well as
  a method for testing the results of ProcessTrace.
  """

  def createTestSubject(self):
    backend = CreateTestDUTBackend()
    return BenchmarkSubject(CONFIG.get("dut_name", "fake"), backend,
                            FakeHighSpeedCamera())

  def runExecuteOnSubjectTest(self, delegate):
    subject = self.createTestSubject()
    delegate.ExecuteOnSubject(subject)

  def runTraceProcessingTest(self, delegate, trace_file, series_expectations):
    trace_path = test_data.Path(trace_file)
    trace = pickle.load(open(trace_path, "r"))

    measurements = BenchmarkMeasurements()
    delegate.ProcessTrace(trace, measurements)
    print "Trace file:", trace_file
    print measurements

    for series_name in measurements.series_infos:
      if series_name not in series_expectations:
        continue
      expectation = series_expectations[series_name]
      latencies = measurements.SummarizeValues(series_name)
      print "Validating %s of %s: %s" % (series_name, trace_file, latencies)
      if isinstance(expectation, float):
        msg = "mean(%s) != %.2f" % (series_name, expectation)
        mean = np.mean(latencies)
        self.assertAlmostEqual(mean, expectation, places=2, msg=msg)
      else:
        msg  = "len(%s) != %d" % (series_name, len(expectation))
        self.assertEqual(len(latencies), len(expectation), msg)
        for i, (expected, actual) in enumerate(zip(expectation, latencies)):
          msg  = "%s[%d] != %d" % (series_name, i, expected)
          self.assertAlmostEqual(expected, actual, places=2, msg=msg)


class LineDrawDelegateTests(AbstractDelegateTests):
  TRACE_EXPECTED_LATENCIES = {
    "line_draw_basic.trace": {
      "LineDrawLatency": [
          123.21, 123.21, 149.85, 146.52, 139.86, 153.18, 159.84, 159.84,
          166.5, 159.84, 139.86, 159.84, 153.18, 143.19, 146.52, 143.19,
          143.19, 129.87, 146.52
      ],
      "LineDrawLatencyStart": [
          113.22, 113.22, 139.86, 136.53, 129.87, 143.19, 146.52, 149.85,
          156.51, 149.85, 129.87, 149.85, 143.19, 136.53, 136.53, 133.2,
          133.2, 119.88, 136.53
      ],
      "DroppedFrameFrequency": 29.63
    },
    "line_draw_incomplete.trace": {
      "LineDrawLatency": 120.32,
      "LineDrawLatencyStart": 111.22,
      "DroppedFrameFrequency": 21.05
    },
    "line_draw_miscalibration.trace": {
      "DroppedFrameFrequency": 0.0
    }
  }

  def testExecuteOnSubject(self):
    self.runExecuteOnSubjectTest(LineDrawDelegate("fake", {}))

  def testTraceProcessing(self):
    for trace_file, expected_latencies in self.TRACE_EXPECTED_LATENCIES.items():
      delegate = LineDrawDelegate("fake", {})
      self.runTraceProcessingTest(delegate, trace_file, expected_latencies)


class LineDrawStartDelegateTests(AbstractDelegateTests):
  TRACE_EXPECTED_LATENCIES = {
  }

  def testExecuteOnSubject(self):
    self.runExecuteOnSubjectTest(LineDrawStartDelegate("fake", {}))

  def testTraceProcessing(self):
    for trace_file, expected_latencies in self.TRACE_EXPECTED_LATENCIES.items():
      delegate = LineDrawDelegate("fake", {})
      self.runTraceProcessingTest(delegate, trace_file, expected_latencies)


class TapDelegateTests(AbstractDelegateTests):
  TRACE_EXPECTED_LATENCIES = {
    "tap_unfinished.trace": {
      "DownLatency": [103.23, 93.24, 103.23, 93.24],
      "UpLatency": [103.23, 96.57, 86.58]
    },
    "tap_basic.trace": {
      "DownLatency": [103.23, 93.24, 103.23, 93.24],
      "DownLatencyStart": [79.92, 73.26, 79.92, 73.26],
      "UpLatency": [106.56, 99.9, 89.91, 83.25],
      "UpLatencyStart": [86.58, 79.92, 69.93, 63.27]
    }
  }

  def testExecuteOnSubject(self):
    self.runExecuteOnSubjectTest(TapDelegate("fake", {}))

  def testTraceProcessing(self):
    for trace_file, expected_latencies in self.TRACE_EXPECTED_LATENCIES.items():
      delegate = TapDelegate("fake", {})
      self.runTraceProcessingTest(delegate, trace_file, expected_latencies)


class TestResultsCompability(unittest.TestCase):
  def generateResults(self):
    trace_path = test_data.Path("line_draw_basic.trace")
    trace = pickle.load(open(trace_path, "r"))

    results = BenchmarkResults("", {})
    results.measurements = BenchmarkMeasurements(3.33)
    delegate = LineDrawDelegate("fake", {})
    delegate.ProcessTrace(trace, results.measurements)
    return results

  def testSaveAndLoad(self):
    results = self.generateResults()
    pickled = pickle.dumps(results)
    loaded_results = pickle.loads(pickled)

    loaded_msrmnts = loaded_results.measurements
    self.assertEqual(results.measurements.SummarizeValues("LineDrawLatency"),
                     loaded_msrmnts.SummarizeValues("LineDrawLatency"))
    self.assertEqual(loaded_msrmnts.series_infos,
                     results.measurements.series_infos)
