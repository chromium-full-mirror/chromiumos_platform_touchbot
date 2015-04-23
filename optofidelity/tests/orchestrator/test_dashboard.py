# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.orchestrator import Dashboard

from . import test_data

#ENDPOINT_URL = "https://chromeperf.appspot.com/add_point"
ENDPOINT_URL = ""

class DashboardTests(TestCase):
  def setUp(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.runner = FakeBenchmarkRunner(fake_trace=fake_trace)
    self.subject = self.runner.benchmark_system.fake_subject

    if ENDPOINT_URL:
      self.dashboard = Dashboard(ENDPOINT_URL)
    else:
      self.dashboard = Dashboard("", fake=True)

  def testDashboardJSON(self):
    benchmark = self.runner.RunBenchmark(self.subject, "tap", {}, [])

    request = self.dashboard._FormatRequest(benchmark.results, "1.0", 1,
                                            "http://fake.com")
    print request

  def testDashboardReport(self):
    benchmark = self.runner.RunBenchmark(self.subject, "tap", {}, [])
    self.dashboard.ReportResults(benchmark.results, "1.0", 1, "http://fake.com")
