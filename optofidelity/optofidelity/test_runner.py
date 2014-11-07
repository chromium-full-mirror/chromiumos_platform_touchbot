# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Simple test case management and execution framework.

Provides the TestCase and TestRunner class. The TestRunner can be fed
with multiple TestCases and execute these on the robot fully automatically while
handling potential error cases by resetting or recalibrating the device.
"""
from collections import defaultdict
from contracts import contract
from fnmatch import fnmatch
import itertools
import os
import sys
import time
import traceback

from optofidelity.system import TestApp, CameraCalibration
from optofidelity.system import DUTException
from optofidelity.videoproc import VideoException
from optofidelity.test_run import TestClass, TestRun


def IterGroups(iterable, key):
  return itertools.groupby(sorted(iterable, key=key), key=key)


def PrintPerf(msg, start_t, debug):
  if debug["perf"]:
    print "PERF: %s: %f s" % (msg, time.time() - start_t)


class TestCase(object):
  """A test case is defined as a test_class executed on an app."""
  @contract(app=TestApp, test_class=TestClass)
  def __init__(self, app, test_class):
    self.app = app
    self.test_class = test_class

  def __str__(self):
    return "%s/%s" % (self.app, self.test_class.name)


class TestRunner(object):
  """Runs a collection of TestCases and handles potential error cases.

  If an error happens during the execution, the robot will first try to reset,
  then re-calibrate if the errors continue.
  During execution, the test cases are sorted in a way that involves as little
  app and dut switching as possible.
  """
  test_classes = {}
  max_tries = 3

  def __init__(self, system, path, dump_all=False, skip_calib=False):
    self.test_apps = {}
    self.system = system
    self.dump_all = dump_all
    self.skip_calib = skip_calib
    self.results_path = os.path.join(path, "results")
    self.failures_path = os.path.join(path, "failures")

    for dut in system:
      for app in dut:
        self.test_apps[str(app)] = app

  @classmethod
  @contract(test_class=type)
  def RegisterTestClass(cls, test_class):
    cls.test_classes[test_class.name] = test_class()

  def RunTests(self, glob, debug):
    # Discover all test cases
    test_cases = []
    for app in self.test_apps.values():
      for test_class in self.test_classes.values():
        test_cases.append(TestCase(app, test_class))

    if glob:
      test_cases = [c for c in test_cases if fnmatch(str(c), glob)]

    if debug["robot"]:
      for case in test_cases:
        case.app.LocateButtons()
        case.test_class.ExecuteTest(case.app, case.app.dut, self.system.camera)
      return {}

    print "Running the following tests:"
    for case in test_cases:
      print "  %s" % str(case)
    print

    # Group test cases by DUT and run all of them
    start_t = time.time()
    results = {}
    for dut, cases in IterGroups(test_cases, lambda c: c.app.dut):
      print "Running tests for: " + str(dut)
      dut_results = self._RunDUTTests(dut, cases, debug, False)
      results.update(dut_results)

    PrintPerf("All tests", start_t, debug)
    return results

  def _RunDUTTests(self, dut, test_cases, debug, safe):
    # Reset device
    if safe:
      dut.Reset()
    else:
      dut.Home()
    dut.LocateButtons(force=safe)

    # Group test cases by app and run all of them
    try:
      results = {}
      for app, cases in IterGroups(test_cases, lambda c: c.app):
        mode = "(safe mode)" if safe else ""
        print "Running tests for: %s %s" % (str(app), mode)
        dut.EnterApp(app)
        app_results = self._RunAppTests(dut, app, cases, debug, safe)
        results.update(app_results)
        dut.ExitApp()
      return results
    except:
      traceback.print_exc()
      if not safe:
        return self._RunDUTTests(dut, cases, debug, True)
      return {}

  def _RunAppTests(self, dut, app, cases, debug, safe):
    app.LocateButtons(force=safe)

    # Calibrate camera by making the screen flash
    start_t = time.time()
    if self.skip_calib and app.calibration and not safe:
      print "Skipping screen calibration"
    else:
      print "Calibrating screen"
      app.calibration = CameraCalibration()
      app.calibration.Calibrate(app, self.system.camera, debug["calibration"])
    PrintPerf("Calibration", start_t, debug)

    # Cache calibration video to disk. The video on the camera will get
    # overwritten by the test runs.
    if self.dump_all:
      app.calibration.CacheVideo()

    # Run all test cases on this app
    results = defaultdict(list)
    for case in cases:
      num_failures = 0
      # Each test class defines how often the test should be repeated
      for i in range(case.test_class.repetitions):
        # Retry until it failed max_tries consecutive times
        while num_failures < self.max_tries:
          try:
            # Run test and collect results
            mode = "(safe mode)" if safe else ""
            print "Running test: %s (rep %d retry %d) %s" % (
                case, i + 1, num_failures, mode)
            case_results = self._RunTest(dut, app, case, debug)
            for key, values in case_results.iteritems():
              results[key].extend(values)
            num_failures = 0
            break
          except:
            num_failures += 1
            traceback.print_exc()
    return results

  def _RunTest(self, dut, app, case, debug):
    # Path to store results in
    timestamp = time.strftime("%Y_%m_%d-%H%M")
    result_path = os.path.join(self.results_path, str(case), timestamp)
    failure_path = os.path.join(self.failures_path, str(case), timestamp)

    # Record test video on the robot
    start_t = time.time()
    run = TestRun(case.test_class, app, calibration, self.results_path)
    run.RecordTestVideo(self.system)
    try:
      # Process video and trace, return latency results
      run.ProcessTestVideo(debug)
      run.ProcessTestTrace(debug)
      if self.dump_all:
        run.SaveAll(result_path)
      print "Results:"
      results = {}
      for key, value in run.test_results.iteritems():
        new_key = "%s/%s" % (str(case), key)
        print "  %s: %s" % (new_key, str(value))
        results[new_key] = value
      PrintPerf(str(case), start_t, debug)
      return results
    except Exception, e:
      print "%s: Processing failed: %s" % (case, e)
      traceback.print_exc()
      run.SaveAll(failure_path)
      raise e



