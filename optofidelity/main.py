#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""

from optparse import OptionParser
import numpy as np
import os
import warnings

from optofidelity import (OptofidelityTestSystem, TestRunner, TestRun, Reporter,
                          ProcessorDebugger, MockTestSystem, MockLatencyTest,
                          MeasurementList)
from optofidelity.system.calibration import LEDCalibration

usage = """TestRunner usage examples

Run all tests:
$ %prog

(Re-)calibrate the robot before running the tests.
$ %prog --calibrate
"""

script_dir = os.path.dirname(os.path.realpath(__file__))
config_file = os.path.join(script_dir, "optofidelity.xml")
state_file = os.path.join(script_dir, "optofidelity.state")

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


def Process(path, what, repetition_name, debug):
  test_run = TestRun.Load(path)
  measurements = MeasurementList()
  led_latency = 0
  if test_run.led_calibration:
    led_latency = (test_run.led_calibration.finger_down_delay +
                   test_run.led_calibration.finger_up_delay) / 2
  reporter = Reporter("test_report", led_latency)
  reporter.CopyResources()
  if repetition_name:
    repetitions = [test_run.repetitions[repetition_name]]
  else:
    repetitions = test_run.repetitions.values()

  if what == "calibration" or what == "all":
    test_run.ProcessCalibrationVideo(debug)

  for repetition in repetitions:
    print "Processing repetition", repetition

    if what == "video" or what == "all":
      repetition.ProcessTestVideo(debug)
      print repetition.test_trace
    elif what == "trace" or what == "all":
      repetition_measurements = repetition.ProcessTestTrace(debug)
      print str(repetition_measurements)
      measurements.extend(repetition_measurements)
      reporter.GenerateRepetitionReport(repetition, repetition_measurements)

  reporter.PrintSummary(measurements)
  test_run.Save()


def RunTests(glob, debug, options):
  if options.mock:
    system = MockTestSystem(options.mock)
    TestRunner.RegisterTestClass(MockLatencyTest)
  elif os.path.exists(state_file) and not options.update_config:
    system = OptofidelityTestSystem.LoadState(state_file)
  else:
    system = OptofidelityTestSystem(config_file)
    if os.path.exists(state_file):
      old_system = OptofidelityTestSystem.LoadState(state_file)
      system.led_calibration = old_system.led_calibration

  runner = TestRunner(system, script_dir, options.dump_all, options.skip_calib)
  if options.led_calib or system.led_calibration is None:
    system.led_calibration = LEDCalibration()
    #system.led_calibration.Calibrate(system.calibration_dut, system.camera,
    #                                 debug)
    print "Calibration Results:"
    print "  Finger down: %f %s" % (system.led_calibration.finger_down_delay,
                                    system.led_calibration.finger_down_delays)
    print "  Finger up: %f %s" % (system.led_calibration.finger_up_delay,
                                  system.led_calibration.finger_up_delays)

  system.SaveState(state_file)
  results = runner.RunTests(glob, debug)

  ms_per_frame = 1.0 / system.camera.fps * 1000
  reporter = Reporter("", ms_per_frame)
  reporter.PrintSummary(results)

  system.SaveState(state_file)

def Main():
  parser = OptionParser(usage=usage)
  parser.add_option("--dump-all",
                    dest="dump_all", default=False, action="store_true",
                    help="Dump debug info for all executed tests.")
  parser.add_option("--process",
                    dest="process", default=None,
                    help="Process local files")
  parser.add_option("--repetition",
                    dest="repetition", default=None,
                    help="Use with --process. Pick which repetition to" +
                         "process. Defaults to all.")
  parser.add_option("--update-config",
                    dest="update_config", default=False, action="store_true",
                    help="Update robot configuration.")
  parser.add_option("--skip-calib",
                    dest="skip_calib", default=False, action="store_true",
                    help="Skip screen calibration.")
  parser.add_option("--led-calib",
                    dest="led_calib", default=False, action="store_true",
                    help="Perform LED calibration before tests.")
  parser.add_option("--mock",
                    dest="mock", default=None,
                    help="Use mock robot system using data from provided path.")

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
    Process(glob, options.process, options.repetition, debug)
  else:
    RunTests(glob, debug, options)


if __name__ == "__main__":
  Main()