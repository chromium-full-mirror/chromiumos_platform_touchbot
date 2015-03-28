# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Benchmark class."""

from unittest import TestCase
import os
import shutil
import tempfile

from optofidelity.benchmark.benchmark import Benchmark
from optofidelity.benchmark._delegate import BenchmarkDelegate
from optofidelity.system.fake import FakeBenchmarkSystem

from . import test_data


class TestDelegate(BenchmarkDelegate):
  """A test delegate to measure the latency between screen draws.

  Instead of using a camera to record the subject this class returns the
  calibration video from test_data.
  """
  calibration_video = test_data.CalibrationVideo()

  def InitializeProcessor(self, processor):
    processor.EnableDetectors(screen_draw=True)

  def ExecuteOnSubject(self, subject):
    return self.calibration_video

  def ProcessTrace(self, trace, results):
    results.AddMeasurement("test measurement", trace[0], trace[1])


class BenchmarkTests(TestCase):
  def setUp(self):
    self.system = FakeBenchmarkSystem()
    self.tempdir = tempfile.mkdtemp()
    subject = self.system.subjects.values()[0]
    self.benchmark = Benchmark(subject.name, "fake", {}, TestDelegate())
    self.benchmark.UseExistingCalibration(test_data.Calibration())

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testRunSaveLoad(self):
    self.benchmark.Run(self.system, [])
    self.benchmark.Save(self.tempdir)
    after = Benchmark.Load(self.tempdir)
    self.assertBenchmarkComplete(after)

  def testSaveLoadRun(self):
    self.benchmark.Save(self.tempdir)
    after = Benchmark.Load(self.tempdir)
    after.Run(self.system, [])
    self.assertBenchmarkComplete(after)

  def testProcessTraceAfterLoad(self):
    self.benchmark.ExecuteOnSubject(self.system)
    self.benchmark.ProcessVideo([], False, False)
    self.benchmark.Save(self.tempdir)
    after = Benchmark.Load(self.tempdir)
    after.ProcessTrace()
    self.assertBenchmarkComplete(after)

  def testProcessVideoAfterLoad(self):
    self.benchmark.ExecuteOnSubject(self.system)
    # Save with debug info, which is required to access the video after loading.
    self.benchmark.Save(self.tempdir, video=True)
    after = Benchmark.Load(self.tempdir)
    after.ProcessVideo([], False, False)
    after.ProcessTrace()
    self.assertBenchmarkComplete(after)

  def testSaveDebugInfo(self):
    self.benchmark.Run(self.system, [])
    self.benchmark.Save(self.tempdir, debug_info=True)
    after = Benchmark.Load(self.tempdir)
    self.assertBenchmarkComplete(after)

    def assertFileExists(filename):
      self.assertTrue(os.path.exists(os.path.join(self.tempdir, filename)))
    assertFileExists("trace.txt")
    assertFileExists("trace.pickle")
    assertFileExists("results.txt")

  def assertBenchmarkComplete(self, benchmark):
    self.assertEqual(len(benchmark.trace), 2)
    self.assertEqual(len(benchmark.results.measurement_list), 1)
