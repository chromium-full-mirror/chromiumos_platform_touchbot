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

from optofidelity.benchmark.fake import FakeBenchmark
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

  def runReportTest(self, filename, benchmark_type):
    metadata = {"OS Version": "23.0", "App Version": "42.0"}
    trace = test_data.LoadTrace(filename)
    benchmark = FakeBenchmark("test_dut(test_app)", benchmark_type, metadata,
                              None, trace, None)
    benchmark.ProcessTrace()
    report = benchmark.GenerateReport(self.tempdir)

    self.userVerification(report.html_filename)
    self.assertReportFilesExist(report.html_filename)

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
      if path.startswith("http") or path.startswith("#"):
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
