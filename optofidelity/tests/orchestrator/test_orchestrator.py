# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase
import os
import shutil
import tempfile

from optofidelity.benchmark import Benchmark
from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.orchestrator import Orchestrator, Dashboard

from . import test_data


class OrchestratorTests(TestCase):
  def setUp(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.runner = FakeBenchmarkRunner(fake_trace=fake_trace)
    self.subject = self.runner.benchmark_system.fake_subject
    self.subject.updater._available_versions = ["2.0", "1.0"]
    self.tempdir = tempfile.mkdtemp()

  def createOrchestrator(self):
    dashboard = Dashboard("", fake=True)
    db_url = "sqlite:///" + os.path.join(self.tempdir, "results.db")
    orchestrator = Orchestrator(self.runner.benchmark_system, self.runner,
                                dashboard, self.tempdir, db_url,
                                print_progress=True)
    orchestrator.MIN_NUMBER_SAMPLES = 0
    return orchestrator

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testResultsDatabase(self):
    orchestrator = self.createOrchestrator()
    orchestrator.UpdateAndRunBenchmarks("*/tap", [], skip_update=True)
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
    orchestrator.MIN_NUMBER_SAMPLES = 20
    orchestrator.UpdateAndRunBenchmarks("*/tap", [], skip_update=True)
    results = list(orchestrator.QueryResults())
    # Should repeat test 5 times, with 2 measurement id's each
    # resulting in 10 entries in the database.
    self.assertEqual(len(results), 10)

  def testResultsPersistence(self):
    orchestrator = self.createOrchestrator()
    orchestrator.UpdateAndRunBenchmarks("*/tap", [], skip_update=True)

    # Create new instance to test if data is stored persistently
    orchestrator = self.createOrchestrator()
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 2)

  def testErrorRepetition(self):
    # Create benchmark results and set an error message.
    with self.runner.UseSubject(self.subject):
      benchmark = self.runner.RunBenchmark("tap", {}, [])
    benchmark.results.error = "Error Message"
    # Return this errornous benchmark with this runner.
    self.runner.fake_benchmark = benchmark

    orchestrator = self.createOrchestrator()
    orchestrator.UpdateAndRunBenchmarks("*/tap", [], skip_update=True)
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 3)
    for result in results:
      self.assertEqual(result["error"], "Error Message")

  def testUpdateAndRun(self):
    orchestrator = self.createOrchestrator()

    # The subject should be updated to 2.0 then have tests run
    orchestrator.UpdateAndRunBenchmarks("*/tap", [])
    self.assertEqual(self.subject.updater.installed_version, "2.0")

    # Force test run with version 1.0
    orchestrator.UpdateAndRunBenchmarks("*/tap", [], forced_version="1.0")
    self.assertEqual(self.subject.updater.installed_version, "1.0")

    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 4)

    versions_tested = [r["subject_version"] for r in results]
    self.assertIn("1.0", versions_tested)
    self.assertIn("2.0", versions_tested)

  def testUpdateSubject(self):
    orchestrator = self.createOrchestrator()

    # The subject should be updated to 2.0 then have tests run
    ret = orchestrator.UpdateSubject(self.subject)
    self.assertEqual(ret, True)
    self.assertEqual(self.subject.updater.installed_version, "2.0")

    # Force test run with version 1.0
    ret = orchestrator.UpdateSubject(self.subject, forced_version="1.0")
    self.assertEqual(ret, True)
    self.assertEqual(self.subject.updater.installed_version, "1.0")

    # Update back to latest version. Next update call should return False
    orchestrator.UpdateSubject(self.subject)
    ret = orchestrator.UpdateSubject(self.subject)
    self.assertEqual(ret, False)
    self.assertEqual(self.subject.updater.installed_version, "2.0")

  def testOnlineOrchestrator(self):
    DB = ""
    GS = ""

    if not DB or not GS:
      self.skipTest("Define DB and GS to run online test.")

    orchestrator = Orchestrator(self.runner.benchmark_system, self.runner,
                                GS, DB, print_progress=True)

    orchestrator.UpdateAndRunBenchmarks("*/tap", [], skip_update=True)
    results = list(orchestrator.QueryResults())
    db_result = results[-1]

    benchmark = Benchmark.Load(os.path.join(GS, db_result["uid"]))
    bench_result = benchmark.results

    self.assertEqual(bench_result.subject_name, db_result["subject_name"])
    self.assertEqual(bench_result.benchmark_type, db_result["benchmark_type"])