#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Module for running video based integration tests.

Provides automated testing of test runs dumped to video files.
The tests are organized in a folder structure under self_tests, one folder
for each test class, organized into two subfolders good and bad.
Videos in the good folder require the test to successfully process, while
videos in the bad folder are expected to fail and return an error.
"""

import os
import traceback

from optofidelity.latency import TouchMoveLatencyTest
from optofidelity.test_runner import TestRunner
from optofidelity.videoproc import VideoException

def DiscoverTests(folder):
  for filename in os.listdir(folder):
    if filename.endswith(".mov"):
      test_name = folder + filename[:-4]
      yield test_name

def RunTests():
  runner = TestRunner(None)
  runner.AddTestClass(TouchMoveLatencyTest)

  results = {}
  for test_class in runner.test_classes.keys() + ["ScreenDetection"]:
    for test_name in DiscoverTests("self_tests/%s/bad/" % test_class):
      try:
        runner.ProcessVideoFromFile(test_name)
      except VideoException, e:
        print e
        print "Exception excpected. Success."
        results[test_name] = True
        continue
      except Exception:
        traceback.print_exc()
      print "Processing should have failed."
      results[test_name] = False

    for test_name in DiscoverTests("self_tests/%s/good/" % test_class):
      try:
        runner.ProcessVideoFromFile(test_name)
        results[test_name] = True
        continue
      except VideoException, e:
        print e
        print "Exception unexpected."
      except Exception:
        traceback.print_exc()
      results[test_name] = False

  print "Self-Test Results:"
  for name, result in results.items():
    msg = "Success" if result else "Failure"
    print "\t", msg, name

if __name__ == "__main__":
  RunTests()