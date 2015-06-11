# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Benchmark class."""

from unittest import TestCase
import os
import re
import shutil
import sys
import tempfile
import webbrowser

from optofidelity.benchmark import AggregateResults
from optofidelity.benchmark.fake import FakeBenchmarkRunner
from optofidelity.reporting import BenchmarkReport, AggregateReport

from . import test_data


class ReportTests(TestCase):
  USER_VERIFICATION = False

  def setUp(self):
    self.tempdir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testLineDrawReport(self):
    self.runReportTest("line_draw_basic.trace", "touch_move")

  def testTapReport(self):
    self.runReportTest("tap_basic.trace", "tap")

  def runReportTest(self, filename, benchmark_type, xkcd=False):
    metadata = {"OS Version": "23.0", "App Version": "42.0"}

    fake_trace = test_data.LoadTrace(filename)
    benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, benchmark_type,
                                              metadata)
    benchmark.trace.ApplyFingerLocationCalib(10)
    benchmark.trace.ApplyLEDCalib(-10, 10)
    report = BenchmarkReport(self.tempdir, "report.html", xkcd=xkcd)
    report.GenerateReport(benchmark.results, benchmark.trace,
                          benchmark.screen_calibration, benchmark.video)
    benchmark.Save(self.tempdir, debug_info=True)
    self.assertReportFilesExist(report.html_filename)
    self.userVerification(report.html_filename)

  def testAggregateReport(self):
    metadata = {"OS Version": "23.0", "App Version": "42.0"}

    fake_trace = test_data.LoadTrace("tap_basic.trace")
    benchmark = FakeBenchmarkRunner.FromTrace(fake_trace, "tap", metadata)

    aggregateResults = AggregateResults("fake_subject", "tap", metadata)
    for repetition in range(3):
      aggregateResults.AddRepetition(benchmark.results)

    report = AggregateReport(self.tempdir, "report.html")
    report.GenerateReport(aggregateResults)
    benchmark.Save(self.tempdir, debug_info=True)

    self.assertReportFilesExist(report.html_filename)
    self.userVerification(report.html_filename)

  def testXKCDReport(self):
    self.runReportTest("line_draw_basic.trace", "touch_move", xkcd=True)

  def assertReportFilesExist(self, filename):
    with open(filename, "r") as file:
      html = file.read()

    def FindHTMLPaths(html):
      SRC_REGEX = "src=\"([^\"]+)\""
      HREF_REGEX = "href=\"([^\"]+)\""
      for regex in (SRC_REGEX, HREF_REGEX):
        for match in re.finditer(regex, html):
          yield match.group(1)
    for path in FindHTMLPaths(html):
      if (path.startswith("http") or path.startswith("#") or
          path.endswith(".avi")):
        continue
      full_path = os.path.join(self.tempdir, path)
      self.assertTrue(os.path.exists(full_path),
                      "referenced file %s does not exist." % path)

  def userVerification(self, filename):
    if not self.USER_VERIFICATION:
      return
    webbrowser.open("file://" + filename)
    print "Opening report in browser. Please verify results."
    print "Press Enter to continue."
    sys.stdin.readline()
