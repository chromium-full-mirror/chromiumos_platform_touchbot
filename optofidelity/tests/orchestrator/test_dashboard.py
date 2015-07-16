# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.orchestrator import ChromePerfDashboard, SpreadsheetDashboard
from optofidelity.orchestrator.omaha import GetLatestChromeVersions
from optofidelity.util import AskUserContinue
from tests.config import (TEST_CHROMEPERF_ENDPOINT, TEST_OAUTH_KEY_FILE,
                          TEST_SPREADSHEET_KEY)
import gspread

from . import test_data


class DashboardTests(TestCase):
  def setUp(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.dashboard = ChromePerfDashboard("subject_name", "touchbot.dev",
                                         TEST_CHROMEPERF_ENDPOINT)

  def testDashboardJSON(self):
    version = GetLatestChromeVersions("beta")[0]
    request = self.dashboard._FormatRequest(self.benchmark.results, version,
                                            "http://fake.com")
    print request

  def testDashboardReport(self):
    for version in GetLatestChromeVersions("beta"):
      self.dashboard.ReportResults(self.benchmark.results, version,
                                   "http://fake.com")


class SpreadsheetTests(TestCase):
  def setUp(self):
    if not TEST_SPREADSHEET_KEY or not TEST_OAUTH_KEY_FILE:
      self.skipTest("Undefined TEST_SPREADSHEET_KEY and TEST_OAUTH_KEY_FILE.")

    tap_trace = test_data.LoadTrace("tap_basic.trace")
    self.tap_bench = FakeBenchmarkRunner.FromTrace(tap_trace, "tap", {})
    line_trace = test_data.LoadTrace("line_draw_basic.trace")
    self.line_bench = FakeBenchmarkRunner.FromTrace(line_trace, "line_draw", {})

    self.dashboard = SpreadsheetDashboard("dut/subject", TEST_SPREADSHEET_KEY,
                                          TEST_OAUTH_KEY_FILE)
    document = self.dashboard.document
    try:
      subject_sheet = document.worksheet("dut/subject")
      document.del_worksheet(subject_sheet)
    except gspread.WorksheetNotFound:
      pass

    try:
      summary_sheet = document.worksheet("summary")
      document.del_worksheet(summary_sheet)
    except gspread.WorksheetNotFound:
      pass

  def testSpreadsheets(self):
    self.dashboard.ReportResults(self.line_bench.results, "1.0",
                                 "http://fake.com")
    AskUserContinue("Verify that the sheets have been created with line draw " +
                    "latencies.")

    self.dashboard.ReportResults(self.tap_bench.results, "1.0",
                                 "http://fake.com")
    AskUserContinue("Verify that the sheets have been updated with tap " +
                    "latencies.")


  def testTapAggregate(self):
    results = test_data.LoadPickle("tap.aggregate-results")
    self.dashboard.ReportResults(results, "1.0", results.report_url)
    AskUserContinue("Verify that the tap latency report has been added.")
