# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Simple test case management and execution framework.

Provides the TestCase and TestRunner class. The TestRunner can be fed
with multiple TestCases and execute these on the robot fully automatically while
handling potential error cases by resetting or recalibrating the device.
"""
from contracts import contract
from fnmatch import fnmatch
import itertools
import os
import sys
import time
import traceback

from optofidelity.system import TestApp, CameraCalibration
from optofidelity.system import RetryFunction, DUTException
from optofidelity.videoproc import VideoException
from optofidelity.test_run import TestClass, TestRun


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
  def __init__(self, system, path, dump_all=False):
    self.test_classes = {}
    self.test_apps = {}
    self.system = system
    self.dump_all = dump_all
    self.results_path = os.path.join(path, "results")
    self.failures_path = os.path.join(path, "failures")

  @contract(test_class=type)
  def AddTestClass(self, test_class):
    self.test_classes[test_class.name] = test_class()

  @contract(app=TestApp)
  def AddApp(self, app):
    self.test_apps[str(app)] = app

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

    # Group test cases by DUT and run all of them
    start_t = time.time()
    sorted_cases = sorted(test_cases, key=lambda c: c.app.dut)
    results = {}
    for dut, cases in itertools.groupby(sorted_cases, key=lambda c: c.app.dut):
      dut_results = RetryFunction(lambda: self._RunDUTTests(dut, cases, debug),
                                  dut.Reset,
                                  "Running tests: " + str(dut))
      results.update(dut_results)
    if debug["perf"]:
      print "PERF: All tests: %f s" % (time.time() - start_t)
    return results

  def _RunDUTTests(self, dut, cases, debug):
    dut.Home()
    dut.LocateButtons()

    # Group test cases by app and run all of them
    results = {}
    sorted_cases = sorted(cases, key=lambda c: c.app)
    for app, cases in itertools.groupby(sorted_cases, key=lambda c: c.app):
      dut.EnterApp(app.name)
      function = lambda: self._RunAppTests(dut, app, cases, debug)
      app_results = RetryFunction(function, app.Reset,
                                  "Running tests: " + str(app))
      results.update(app_results)
      dut.ExitApp()
    return results

  def _RunAppTests(self, dut, app, cases, debug):
    app.LocateButtons()

    # Calibrate camera by making the screen flash

    start_t = time.time()
    calibration = CameraCalibration()
    calibration.Calibrate(app, self.system.camera, debug["calibration"])
    if debug["perf"]:
      print "PERF: Calibration: %f s" % (time.time() - start_t)

    # Cache calibration video to disk. The video on the camera will get
    # overwritten by the test runs.
    if self.dump_all:
      calibration.CacheVideo()

    # Run all test cases with that calibration
    results = {}
    for case in cases:
      for i in range(case.test_class.repetitions):
        function = lambda: self._RunTest(dut, app, case, calibration, debug)
        case_results = RetryFunction(function, app.Reset,
                                     "Running test: %s (rep %d)"
                                     % (case, i + 1))
        for key, values in case_results.iteritems():
          if key not in results:
            results[key] = []
          results[key].extend(values)
    return results


  def _RunTest(self, dut, app, case, calibration, debug):
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
      if debug["perf"]:
        print "PERF: %s: %f s" % (str(case), time.time() - start_t)
      return results
    except Exception, e:
      print "%s: Processing failed: %s" % (case, e)
      traceback.print_exc()
      run.SaveAll(failure_path)
      raise e



