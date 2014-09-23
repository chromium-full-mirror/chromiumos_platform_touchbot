# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Simple test case management and execution framework.

Provides the TestCase and TestRunner class. The TestRunner can be fed
with multiple TestCases and execute these on the robot fully automatically while
handling potential error cases by resetting or recalibrating the device.
"""
import h5py
import itertools
import os
import sys
import time
import traceback

from detection import TestArea, VideoProcessor
from system import RetryFunction, DUTException
from videoproc import VideoException, VideoWriter, FileVideoReader


class TestClass(object):
  """Base class for test cases.

  A test case has to perform two actions:
  1. It has to execute the test on the robot, instructing camera and robot
     to perform and record the test.
  2. It has to process the resulting trace, returning the test results.
  """
  name = "Unnamed"
  required_events = []

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

class TestCase(object):
  """A test case is defined as a test_class executed on an app."""
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
  def __init__(self, system, dump_all=False):
    self.test_classes = {}
    self.test_apps = {}
    self.system = system
    self.dump_all = dump_all

  def AddTestClass(self, test_class):
    self.test_classes[test_class.name] = test_class()

  def AddApp(self, app):
    self.test_apps[str(app)] = app

  def ProcessVideoFromFile(self, name, debug=False):
    if os.path.exists(name + ".test_class"):
      test_class_name = open(name + ".test_class").read()
      test_class = self.test_classes[test_class_name]

      video = FileVideoReader(name + ".mov")
      test_area = TestArea.Load(h5py.File(name + ".test_area", "r"))

      res = self._ProcessVideo(test_class, video, test_area, debug=debug)
      print res
    else:
      # no test_class, this is a screen detection recording
      video = FileVideoReader(name + ".mov")
      print "Detecting Screen in", (name + ".mov")
      test_area = TestArea()
      test_area.Detect(video.Frames(step=10))

  def _DumpDebugInfo(self, case, video, dump_last_exception=False):
    print "%s: Dumping debug info:" % case
    basename = str(case).replace("/", "_") + "_" + str(int(time.time()))

    # Save video
    writer = VideoWriter(basename + ".mov")
    writer.Write(video)

    # Save screen calibration
    case.app.test_area.Save(h5py.File(basename + ".test_area", "w"))

    # Save name of test case
    open(basename + ".test_class", "w").write(case.test_class.name)

    # Dump error messages
    if dump_last_exception:
      open(basename + ".error", "w").write(traceback.format_exc())
    print "%s: Debug with: %s --debug-video %s" % (case, sys.argv[0], basename)

  def _ProcessVideo(self, test_class, video, test_area, debug=False):
    processor = VideoProcessor(test_area)
    processor.Initialize(video, debug=debug)

    print "Validating video"
    generated_events = processor.SkimVideo(video, debug=debug)
    if debug:
      print "Generated event types: %s" % (generated_events)
    for event_type in test_class.required_events:
      if event_type not in generated_events:
        msg = "Video did not generate required %s events" % event_type
        raise VideoException(msg)

    print "Generating trace"
    trace = processor.ProcessVideo(video, debug=debug)
    print "Processing trace"
    return test_class.ProcessTrace(trace)

  def _RunTest(self, dut, app, case):
    video = case.test_class.ExecuteTest(app, dut, self.system.camera)
    try:
      res = self._ProcessVideo(case.test_class, video, app.test_area)
      if self.dump_all:
        self._DumpDebugInfo(case, video, False)
      return res
    except VideoException, e:
      print "%s: Video processing failed: %s" % (case, e)
      self._DumpDebugInfo(case, video, True)
      raise DUTException(dut, "Video processing failure")

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
    test_cases = []
    for app in self.test_apps.values():
      for test_class in self.test_classes.values():
        test_cases.append(TestCase(app, test_class))

    sorted_cases = sorted(test_cases, key=lambda c: c.app.dut)
    for dut, cases in itertools.groupby(sorted_cases, key=lambda c: c.app.dut):
      RetryFunction(lambda: self._RunDUTTests(dut, cases),
                    lambda: dut.Reset(),
                    "Running tests: " + str(dut))
