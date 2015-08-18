# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests of all delegates implementations.

Most importantly this includes tests of trace processing, which processes
recorded traces into measurements.
"""
import cPickle as pickle
import os
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

  def runTraceProcessingTest(self, delegate, trace_file, expected_latencies):
    trace_path = test_data.Path(trace_file)
    trace = pickle.load(open(trace_path, "r"))

    measurements = BenchmarkMeasurements()
    delegate.ProcessTrace(trace, measurements)
    print "Trace file:", trace_file

    for series_name in measurements.series_infos:
      if series_name not in expected_latencies:
        continue
      latencies = measurements.SummarizeValues(series_name)
      print "Measurement", series_name
      print "Calculated Latencies:", latencies
      print "Expected Latencies:", expected_latencies[series_name]
      self.assertTrue(np.allclose(latencies, expected_latencies[series_name]))


class LineDrawDelegateTests(AbstractDelegateTests):
  TRACE_EXPECTED_LATENCIES = {
    "line_draw_basic.trace": {
      "LineDrawLatency": np.asarray([37, 37, 45, 44, 42, 46, 48, 48, 50, 48, 42,
                                     48, 46, 43, 44, 43, 43, 39, 44, 46]) * 3.33,
      "DroppedFrameFrequency": np.asarray([40.0])
    },
    "line_draw_incomplete.trace": {
      "LineDrawLatency": np.asarray([28, 28, 29, 29, 30, 31, 35, 35,
                                     35, 40, 40, 45, 44, 46, 47]) * 3.33,
      "DroppedFrameFrequency": np.asarray([26.666666666666668])
    },
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
      "DownLatency": np.asarray([31, 28, 31, 28]) * 3.33,
      "UpLatency": np.asarray([31, 29, 26]) * 3.33
    },
    "tap_basic.trace": {
      "DownLatency": np.asarray([31, 28, 31, 28]) * 3.33,
      "UpLatency": np.asarray([32, 30, 27, 25]) * 3.33
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
