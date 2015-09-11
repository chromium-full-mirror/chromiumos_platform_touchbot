# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase
import os
import shutil
import tempfile

from optofidelity.benchmark import BenchmarkMeasurements
from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.builder import SystemBuilder
from optofidelity.orchestrator import OrchestratorSubject
from tests.config import CONFIG

from . import test_data


unit_test_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <benchmark-runner type="fake" />
  <video-processor type="fake" />

  <orchestrator results="{tempdir}" generate-reports="False" />

  <dut name="test_dut">
    <subject name="test_subject">
      <navigator type="fake" />
      <updater type="fake" />
      <dashboard type="fake" />
      <collector type="fake" />
      <benchmark name="tap" type="tap" activity="tap" />
      <benchmark name="tap2" type="tap" activity="tap" />
    </subject>
  </dut>
</config>
"""

def AlwaysRaiseException(*args, **kwargs):
  raise Exception("Error42")

class OrchestratorTests(TestCase):
  def setUp(self):
    self.tempdir = tempfile.mkdtemp()
    config = unit_test_config.format(tempdir=self.tempdir)
    builder = SystemBuilder.FromString(config)

    self.video_processor = builder.video_processor
    self.runner = builder.benchmark_runner
    self.orchestrator = builder.orchestrator

    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.video_processor.fake_trace = fake_trace

    self.successful = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.failed = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.failed.results.error = "Error42"
    self.empty = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.empty.results.measurements = BenchmarkMeasurements()

    self.subject = self.orchestrator._subjects.values()[0]
    self.subject.updater.Install("2.0")
    self.subject.updater._available_versions = ["1.0", "2.0", "3.0", "4.0"]

    self.benchmark_def = self.subject.benchmark_defs["tap"]

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testSetup(self):
    self.orchestrator.SetUpSubjects("*", "1")
    self.assertEqual(self.subject.updater.installed_version, "1.0")

  def testPrepareSubjects(self):
    self.orchestrator.PrepareSubjects()

  def testVerifySubjects(self):
    self.orchestrator.VerifySubjects()

  def testPrintInfo(self):
    self.orchestrator.PrintInfo("*")
    CONFIG.AskUserAccept("Verify the printed output")

  def testVideoProcessingErrorHandling(self):
    self.video_processor.ProcessVideo = AlwaysRaiseException
    self.orchestrator.UpdateAndRunBenchmarks("*", "3.0", True)
    # Should save reports of 3 tries of 2 benchmarks
    self.assertEqual(len(os.listdir(self.tempdir)), 6)
    # Nothing should be reported to the dashboard
    self.assertEqual(len(self.subject.dashboard.results), 0)

  def testDashboardErrorHandling(self):
    self.subject.dashboard.ReportResults = AlwaysRaiseException
    self.orchestrator.UpdateAndRunBenchmarks("*", "3.0", True)
    # Should save benchmarks regardless of dashboard error
    self.assertGreater(len(os.listdir(self.tempdir)), 0)

  def testCalibrationErrorHandling(self):
    self.video_processor.CreateScreenCalibration = AlwaysRaiseException
    self.orchestrator.UpdateAndRunBenchmarks("*", "installed:", True)
    # Does not run benchmarks, so there is nothing to save.
    self.assertEqual(len(os.listdir(self.tempdir)), 0)
    # Subject has to be in a state where it can be used again.
    self.subject.navigator.Open()
    self.subject.navigator.Close()

  def testVerificationErrorHandling(self):
    self.subject.navigator.Verify = AlwaysRaiseException
    self.orchestrator.UpdateAndRunBenchmarks("*", "installed:", True)
    # Does not run benchmarks, so there is nothing to save.
    self.assertEqual(len(os.listdir(self.tempdir)), 0)

  def testUpdateAndRunBenchmarks(self):
    self.orchestrator.UpdateAndRunBenchmarks("*", "installed:", True)
    # 2 versions with 2 benchmarks each
    self.assertEqual(len(self.subject.dashboard.results), 4)

  def testRunSubjectVersion(self):
    self.runner.fake_benchmarks = [self.successful]
    benchmark_defs = self.subject.benchmark_defs.values()
    with self.subject.access:
      self.orchestrator.RunSubjectVersion(self.subject, benchmark_defs, "3.0")
    self.assertEqual(self.subject.updater.installed_version, "3.0")
    self.assertEqual(len(self.subject.dashboard.results), 2)

  def testAggregation(self):
    self.runner.fake_benchmarks = [self.successful]
    with self.subject.access:
      aggregate = self.orchestrator.RunSubjectVersionBenchmark(
          self.subject, self.benchmark_def, "1.0")
    self.assertTrue(aggregate.measurements.HasMinNumSamples())
    self.assertEqual(len(aggregate.repetitions), 9)

    results_path = os.path.join(self.tempdir, aggregate.uid, "results.pickle")
    self.assertTrue(os.path.exists(results_path))

    reported_results = self.subject.dashboard.results[0]
    self.assertEqual(reported_results, aggregate)

  def testErrorRepetition(self):
    """Failing benchmarks should be repeated and saved as well."""
    self.runner.fake_benchmarks = [self.failed, self.failed, self.successful]
    with self.subject.access:
      benchmark = self.orchestrator.RunSubjectVersionBenchmarkRepetition(
          self.subject, self.benchmark_def, {})
    self.assertEqual(benchmark, self.successful)
    self.assertEqual(len(os.listdir(self.tempdir)), 3)

  def testTooManyErrors(self):
    """Failing benchmarks should be repeated and saved as well."""
    self.runner.fake_benchmarks = [self.failed]
    with self.subject.access:
      benchmark = self.orchestrator.RunSubjectVersionBenchmarkRepetition(
          self.subject, self.benchmark_def, {})
    self.assertIsNone(benchmark)

  def testEmptyEqualsError(self):
    self.runner.fake_benchmarks = [self.empty]
    with self.subject.access:
      benchmark = self.orchestrator.RunSubjectVersionBenchmarkRepetition(
          self.subject, self.benchmark_def, {})
    self.assertIsNone(benchmark)

  def testRepetitionSaving(self):
    with self.subject.access:
      with self.runner.UseSubject(self.subject):
        benchmark = self.orchestrator.RunSubjectVersionBenchmarkRepetition(
            self.subject, self.benchmark_def, {})

    self.assertEqual(os.listdir(self.tempdir), [benchmark.results.uid])
    loaded = benchmark.Load(os.path.join(self.tempdir, benchmark.results.uid))
    self.assertEqual(loaded.results.uid, benchmark.results.uid)

  def testCollection(self):
    self.assertEqual(len(self.subject.collectors), 1)
    collector = self.subject.collectors[0]

    with self.subject.access:
      with self.runner.UseSubject(self.subject):
        benchmark = self.orchestrator.RunSubjectVersionBenchmarkRepetition(
            self.subject, self.benchmark_def, {})

    self.assertTrue(collector.collected)

    filename = os.path.join(self.tempdir, benchmark.results.uid, "fake.log")
    self.assertTrue(os.path.exists(filename))

  def testVersionParsing(self):
    available = ["1.0", "1.1", "1.2", "2.0", "2.2", "3.0"]
    installed = "1.1"

    def Parse(string):
        return OrchestratorSubject._ParseVersionRange(string, installed,
                                                      available)
    self.assertEqual(Parse("installed"), ["1.1"])
    self.assertEqual(Parse("installed:"), ["1.1", "1.2", "2.0", "2.2", "3.0"])
    self.assertEqual(Parse("1-:1"), ["1.0", "1.1", "1.2"])
    self.assertEqual(Parse("2-:3"), ["2.0", "2.2", "3.0"])
    self.assertEqual(Parse("latest"), ["3.0"])
    self.assertEqual(Parse("2.0:latest"), ["2.0", "2.2", "3.0"])
