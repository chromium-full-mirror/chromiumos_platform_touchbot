#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""

from optparse import OptionParser
import cPickle as pickle
import numpy as np
import os
import warnings

from optofidelity import (OptofidelityTestSystem, TestRunner, TestRun,
                          ProcessorDebugger)
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
  if os.path.exists(state_file) and not options.update_config:
    system = pickle.load(open(state_file, "r"))
  else:
    system = OptofidelityTestSystem(config_file)
    if os.path.exists(state_file):
      old_system = pickle.load(open(state_file, "r"))
      system.led_calibration = old_system.led_calibration

  runner = TestRunner(system, script_dir, options.dump_all, options.skip_calib)

  if options.led_calib or system.led_calibration is None:
    system.led_calibration = LEDCalibration()
    system.led_calibration.Calibrate(system.calibration_dut, system.camera,
                                     debug)
    print "Calibration Results:"
    print "  Finger down: %f %s" % (system.led_calibration.finger_down_delay,
                                    system.led_calibration.finger_down_delays)
    print "  Finger up: %f %s" % (system.led_calibration.finger_up_delay,
                                  system.led_calibration.finger_up_delays)

  pickle.dump(system, open(state_file, "w"), protocol=-1)
  results = runner.RunTests(glob, debug)

  print "Latency Results:"
  for name, result in results.iteritems():
    std = np.std(result)
    mean = np.mean(result)
    print "  %s: %f (std=%f)" % (name, mean, std)

  pickle.dump(system, open(state_file, "w"), protocol=-1)

def Main():
  parser = OptionParser(usage=usage)
  parser.add_option("--dump-all",
                    dest="dump_all", default=False, action="store_true",
                    help="Dump debug info for all executed tests.")
  parser.add_option("--process",
                    dest="process", default=None,
                    help="Process local files")
  parser.add_option("--update-config",
                    dest="update_config", default=False, action="store_true",
                    help="Update robot configuration.")
  parser.add_option("--skip-calib",
                    dest="skip_calib", default=False, action="store_true",
                    help="Skip screen calibration.")
  parser.add_option("--led-calib",
                    dest="led_calib", default=False, action="store_true",
                    help="Perform LED calibration before tests.")

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