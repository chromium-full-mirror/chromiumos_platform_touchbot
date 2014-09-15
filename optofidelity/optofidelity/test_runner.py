# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Simple test case management and execution framework.

Provides the TestCase and TestRunner class. The TestRunner can be fed
with multiple TestCases and execute these on the robot fully automatically while
handling potential error cases by resetting or recalibrating the device.
"""
from system import RetryFunction
from trace_generator import TraceGenerator
import itertools

class TestCase(object):
  """Base class for test cases.

  A test case has to perform two actions:
  1. It has to execute the test on the robot, instructing camera and robot
     to perform and record the test.
  2. It has to process the resulting trace, returning the test results.
  """
  def __init__(self, app):
    self.app = app
    self.name = "Unnamed"

  def __str__(self):
    return "%s/%s" % (str(self.app), self.name)

  def ExecuteTest(self, app, dut, camera):
    """Execute test on the robot.

    This method has to instruct the camera and robot to perform and record the
    test, then return the recorded video as a VideoReader.
    """
    raise NotImplementedError()

  def ProcessTrace(self, trace):
    """Process the trace and return a dictionary of results.

    The trace is being generated from the video returned by ExecuteTest. This
    method calculates the test results from the trace and should return a
    dictionary describing the test results, such as:
    { "begin_latency": 32, "end_latency": 55 }.
    """
    raise NotImplementedError()


class TestRunner(object):
  """Runs a collection of TestCases and handles potential error cases.

  If an error happens during the execution, the robot will first try to reset,
  then re-calibrate if the errors continue.
  During execution, the test cases are sorted in a way that involves as little
  app and dut switching as possible.
  """
  def __init__(self, system):
    self.test_cases = []
    self.camera = system.camera

  def AddTestCase(self, case):
    self.test_cases.append(case)

  def _RunTest(self, dut, app, case):
    trace_generator = TraceGenerator(app.screen)
    video = case.ExecuteTest(app, dut, self.camera)
    trace = trace_generator.ProcessVideo(video)
    scores = case.ProcessTrace(trace)
    print scores

  def _RunAppTests(self, dut, app, cases):
    dut.EnterApp(app.name)
    for case in cases:
      RetryFunction(lambda: self._RunTest(dut, app, case),
                    app.Reset,
                    "Running test: " + str(case))
    dut.ExitApp()

  def _RunDUTTests(self, dut, cases):
    dut.ExitApp()
    sorted_cases = sorted(cases, key=lambda c: c.app)
    for app, cases in itertools.groupby(sorted_cases, key=lambda c: c.app):
      RetryFunction(lambda: self._RunAppTests(dut, app, cases),
                    dut.Reset,
                    "Running tests: " + str(app))

  def RunTests(self):
    sorted_cases = sorted(self.test_cases, key=lambda c: c.app.dut)
    for dut, cases in itertools.groupby(sorted_cases, key=lambda c: c.app.dut):
      RetryFunction(lambda: self._RunDUTTests(dut, cases),
                    lambda: dut.Calibrate(self.camera) and dut.Reset(),
                    "Running tests: " + str(dut))
