#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""

from optparse import OptionParser
import numpy as np
import os
import warnings

from optofidelity.latency import TapLatencyTest, TouchMoveLatencyTest
from optofidelity.system import OptofidelityTestSystem
from optofidelity.test_runner import TestRunner
from optofidelity.test_run import TestRun
from optofidelity.detection import ProcessorDebugger

usage = """TestRunner usage examples

Run all tests:
$ %prog

(Re-)calibrate the robot before running the tests.
$ %prog --calibrate
"""

script_dir = os.path.dirname(os.path.realpath(__file__))
config_file = os.path.join(script_dir, "optofidelity.cfg")
calibration_file = os.path.join(script_dir, "calibration.hdf5")

def RegisterTestClasses(runner):
  runner.AddTestClass(TouchMoveLatencyTest)
  runner.AddTestClass(TapLatencyTest)

def AddDebugOptions(parser):
  parser.add_option("--debug",
                    dest="debug", default=None,
                    help="Enable debug printouts and images.")
  parser.add_option("--start",
                    dest="start", default=None,
                    help="Start processing at this frame")
  parser.add_option("--stop",
                    dest="stop", default=None,
                    help="Stop processing at this frame")

def BuildDebugger(options):
  return ProcessorDebugger(options.debug, options.start, options.stop)

def Process(path, what, debug):
  run = TestRun.Load(path)
  if what == "calibration":
    run.ProcessCalibrationVideo(debug)
  elif what == "video":
    run.ProcessTestVideo(debug)
    print run.test_trace
  elif what == "trace":
    run.ProcessTestTrace(debug)
    print run.test_results
  elif what == "all":
    run.ProcessCalibrationVideo(debug)
    run.ProcessTestVideo(debug)
    run.ProcessTestTrace(debug)
  run.Save()

def RunTests(glob, debug, options):
  system = OptofidelityTestSystem(config_file)

  if options.calibrate or not os.path.exists(calibration_file):
    system.Calibrate(options.dump_all)
    system.SaveCalibration(calibration_file)
  else:
    system.LoadCalibration(calibration_file)

  runner = TestRunner(system, script_dir, options.dump_all)
  RegisterTestClasses(runner)
  for dut in system:
    for app in dut:
      runner.AddApp(app)

  if options.debug_video:
    runner.ProcessVideoFromFile(options.debug_video, debug)
  else:
    runner.RunTests(glob, debug)

def Main():
  parser = OptionParser(usage=usage)
  parser.add_option("--calibrate",
                    dest="calibrate", default=False, action="store_true",
                    help="re-calibrate the robot system.")
  parser.add_option("--dump-all",
                    dest="dump_all", default=False, action="store_true",
                    help="Dump debug info for all executed tests.")
  parser.add_option("--process",
                    dest="process", default=None,
                    help="Process local files")

  AddDebugOptions(parser)
  (options, args) = parser.parse_args()

  if not options.debug:
    np.seterr(all='ignore')
    warnings.filterwarnings('ignore', category=UserWarning)

  glob=None
  if args:
    glob = args[0]

  debug = BuildDebugger(options)
  if options.process:
    Process(glob, options.process, debug)
  else:
    RunTests(glob, debug, options)


if __name__ == "__main__":
  Main()