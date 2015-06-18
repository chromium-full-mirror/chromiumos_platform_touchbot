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
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.tempdir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testRun(self):
    self.assertBenchmarkComplete(self.benchmark)

  def testSaveDebugInfo(self):
    self.benchmark.Save(self.tempdir, debug_info=True)
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
    self.benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})

    self.assertIn("Trigger Camera", self.benchmark.log)
    self.assertIn("Tap", self.benchmark.log)

    root_logger.setLevel(original_level)

  def assertBenchmarkComplete(self, benchmark):
    num_taps = 4
    msrmnts = benchmark.results.measurements
    self.assertEqual(len(benchmark.trace), num_taps * 4)
    self.assertEqual(len(msrmnts[0]["DownLatency"]), num_taps)
    self.assertEqual(len(msrmnts[0]["UpLatency"]), num_taps)
