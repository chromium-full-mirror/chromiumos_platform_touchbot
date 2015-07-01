# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase
import os
import shutil
import tempfile

from optofidelity.benchmark import Benchmark, DrawEventLatencySeries
from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.orchestrator import (Dashboard, FakeUpdater, Orchestrator,
                                       OrchestratorSubject)

from . import test_data


class OrchestratorTests(TestCase):
  def setUp(self):
    self.fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.runner = FakeBenchmarkRunner(fake_trace=self.fake_trace)
    subject = self.runner.benchmark_system.fake_subject
    self.subject = OrchestratorSubject.FromBenchmarkSubject(subject)
    self.subject.DefineBenchmark("tap", "tap", "fake", {})
    self.subject.updater = FakeUpdater()
    self.subject.updater.Install("1.0")
    self.subject.updater._available_versions = ["1.0", "2.0"]
    self.tempdir = tempfile.mkdtemp()

  def createOrchestrator(self):
    db_url = "sqlite:///" + os.path.join(self.tempdir, "results.db")
    orchestrator = Orchestrator(self.runner.benchmark_system, self.runner,
                                self.tempdir, db_url,
                                generate_reports=False)
    orchestrator.AddSubject(self.subject)
    DrawEventLatencySeries.DEFAULT_MIN_NUM_SAMPLES = 0
    return orchestrator

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testResultsDatabase(self):
    orchestrator = self.createOrchestrator()
    orchestrator.UpdateAndRunBenchmarks("*/tap", "installed")
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 2)
    for result in results:
      data_folder = os.path.join(self.tempdir, str(result["uid"]))
      self.assertTrue(os.path.exists(data_folder))

      # Load and attempt to extract debug info for this benchmark to make sure
      # the stored data is consistent.
      benchmark = Benchmark.Load(data_folder)
      benchmark.Save(data_folder, debug_info=True)

  def testMinSamples(self):
    orchestrator = self.createOrchestrator()
    DrawEventLatencySeries.DEFAULT_MIN_NUM_SAMPLES = 8
    orchestrator.UpdateAndRunBenchmarks("*/tap", "installed")
    results = list(orchestrator.QueryResults())
    # Should repeat test 2 times, with 2 measurement id's each
    # resulting in 4 entries in the database.
    self.assertEqual(len(results), 4)

  def testResultsPersistence(self):
    orchestrator = self.createOrchestrator()
    orchestrator.UpdateAndRunBenchmarks("*/tap", "installed")

    # Create new instance to test if data is stored persistently
    orchestrator = self.createOrchestrator()
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 2)

  def testErrorRepetition(self):
    # Create benchmark results and set an error message.
    benchmark = FakeBenchmarkRunner.FromTrace(self.fake_trace, "tap", {})
    benchmark.results.error = "Error Message"
    # Return this errornous benchmark with this runner.
    self.runner.fake_benchmark = benchmark

    orchestrator = self.createOrchestrator()
    orchestrator.UpdateAndRunBenchmarks("*/tap", "installed")
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 6)
    for result in results:
      self.assertEqual(result["error"], "Error Message")

  def testUpdateAndRun(self):
    orchestrator = self.createOrchestrator()

    # The subject should be updated to 2.0 then have tests run
    orchestrator.UpdateAndRunBenchmarks("*/tap", "2.0")
    self.assertEqual(self.subject.updater.installed_version, "2.0")

    # Force test run with version 1.0
    orchestrator.UpdateAndRunBenchmarks("*/tap", "1.0")
    self.assertEqual(self.subject.updater.installed_version, "1.0")

    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 4)

    versions_tested = [r["subject_version"] for r in results]
    self.assertIn("1.0", versions_tested)
    self.assertIn("2.0", versions_tested)

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
