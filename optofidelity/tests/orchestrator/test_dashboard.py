# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.orchestrator import ChromePerfDashboard

from . import test_data

#ENDPOINT_URL = "https://chromeperf.appspot.com/add_point"
ENDPOINT_URL = None

class DashboardTests(TestCase):
  def setUp(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.dashboard = ChromePerfDashboard("", ENDPOINT_URL)

  def testDashboardJSON(self):
    request = self.dashboard._FormatRequest(self.benchmark.results, "1.0",
                                             1, "http://fake.com")
    print request

  def testDashboardReport(self):
    self.dashboard.ReportResults(self.benchmark.results, "1.0", 1,
                                 "http://fake.com")
