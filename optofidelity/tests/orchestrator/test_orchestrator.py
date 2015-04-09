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
from optofidelity.orchestrator import Orchestrator

from . import test_data


class OrchestratorTests(TestCase):
  def setUp(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.runner = FakeBenchmarkRunner(fake_trace=fake_trace)
    self.subject = self.runner.benchmark_system.fake_subject
    self.subject.Open(False)
    self.tempdir = tempfile.mkdtemp()

  def createOrchestrator(self):
    return Orchestrator(self.runner.benchmark_system, self.runner, self.tempdir)

  def tearDown(self):
    self.subject.Close()
    shutil.rmtree(self.tempdir)

  def testResultsDatabase(self):
    orchestrator = self.createOrchestrator()
    orchestrator.RunTests("*/tap", [])
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 2)
    for result in results:
      data_folder = os.path.join(self.tempdir, str(result["uid"]))
      self.assertTrue(os.path.exists(data_folder))

      # Load and attempt to extract debug info for this benchmark to make sure
      # the stored data is consistent.
      benchmark = Benchmark.Load(data_folder)
      benchmark.Save(data_folder, debug_info=True)

  def testResultsPersistence(self):
    orchestrator = self.createOrchestrator()
    orchestrator.RunTests("*/tap", [])

    # Create new instance to test if data is stored persistently
    orchestrator = self.createOrchestrator()
    results = list(orchestrator.QueryResults())
    self.assertEqual(len(results), 2)
