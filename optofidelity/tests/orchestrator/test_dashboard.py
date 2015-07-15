# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.orchestrator import ChromePerfDashboard
from optofidelity.orchestrator.omaha import GetLatestChromeVersions

from . import test_data

import gspread

#ENDPOINT_URL = "https://chromeperf.appspot.com/add_point"
ENDPOINT_URL = None

class DashboardTests(TestCase):
  def setUp(self):
    fake_trace = test_data.LoadTrace("tap_basic.trace")
    self.benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", {})
    self.dashboard = ChromePerfDashboard("subject_name", "touchbot.dev", ENDPOINT_URL)

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
  def testSpreadsheets(self):


    # Login with your Google account
    gc = gspread.login('thedude@abid.es', 'password')

    # WARNING: The code above uses ClientLogin and was disabled
    # on April 20, 2015.

    # Please use OAuth2 authorization to access Google Sheets.

    # Open a worksheet from spreadsheet with one shot
    wks = gc.open("Where is the money Lebowski?").sheet1

    wks.update_acell('B2', "it's down there somewhere, let me take another look.")

    print wks.get_all_values()
