# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Benchmark class."""

from unittest import TestCase
import logging
import os
import shutil
import tempfile

from optofidelity.benchmark import Benchmark
from optofidelity.benchmark.fake import FakeBenchmarkRunner

from . import test_data


class BenchmarkRunnerTests(TestCase):
  def setUp(self):
    self.tempdir = tempfile.mkdtemp()

  def CreateBenchmark(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    return FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testRun(self):
    self.assertBenchmarkComplete(self.CreateBenchmark())

  def testSaveDebugInfo(self):
    benchmark = self.CreateBenchmark()
    benchmark.Save(self.tempdir, debug_info=True)
    after = Benchmark.Load(self.tempdir)
    self.assertBenchmarkComplete(after)

    def assertFileExists(filename):
      self.assertTrue(os.path.exists(os.path.join(self.tempdir, filename)))
    assertFileExists("trace.txt")
    assertFileExists("trace.pickle")
    assertFileExists("results.txt")

  def testLogging(self):
    root_logger = logging.getLogger()
    original_level = root_logger.getEffectiveLevel()
    root_logger.setLevel(logging.DEBUG)

    fake_trace = test_data.LoadTrace("tap_basic.trace")
    benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})

    self.assertIn("Trigger Camera", benchmark.log)
    self.assertIn("Tap", benchmark.log)

    root_logger.setLevel(original_level)

  def testExceptionCapture(self):
    def FakeProcessTrace():
      raise Exception("Error42")

    fake_trace = test_data.LoadTrace("tap_basic.trace")
    runner = FakeBenchmarkRunner(fake_trace=fake_trace)
    with runner.UseSubject(runner.benchmark_system.fake_subject):
      benchmark = runner.CreateBenchmark("fake", "tap", "fake", {}, {})
      benchmark.ProcessTrace = FakeProcessTrace
      runner.RunBenchmark(benchmark)
      self.assertIn("Error42", benchmark.results.error)

  def testCalibrationError(self):
    def FakeCreateScreenCalibration(video_reader):
      raise Exception("Error42")

    runner = FakeBenchmarkRunner()
    runner._calib_video_path = self.tempdir
    # Inject Exception into screen calibration
    runner.video_processor.CreateScreenCalibration = FakeCreateScreenCalibration

    # Exception has to be passed up
    try:
      runner.OpenAndCalibrateSubject(runner.benchmark_system.fake_subject)
    except Exception, e:
      self.assertEqual(str(e), "Error42")

    # And a calibration video has to be stored
    self.assertIn("calibration_000.avi", os.listdir(self.tempdir))

  def assertBenchmarkComplete(self, benchmark):
    num_taps = 4
    msrmnts = benchmark.results.measurements
    self.assertEqual(len(benchmark.trace), num_taps * 4)
    self.assertEqual(len(msrmnts[0]["DownLatency"]), num_taps)
    self.assertEqual(len(msrmnts[0]["UpLatency"]), num_taps)
