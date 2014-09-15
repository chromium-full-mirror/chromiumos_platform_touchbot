#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""

from optparse import OptionParser
import os

from optofidelity.latency import TouchMoveLatencyTest
from optofidelity.system import OptofidelityTestSystem
from optofidelity.test_runner import TestRunner


usage = """TestRunner usage examples

Run all tests:
$ %prog

(Re-)calibrate the robot before running the tests.
$ %prog --calibrate
"""

script_dir = os.path.dirname(os.path.realpath(__file__))
config_file = os.path.join(script_dir, "optofidelity.cfg")
calibration_file = os.path.join(script_dir, "calibration.hdf5")


def RunTests(calibrate, debug):
  system = OptofidelityTestSystem(config_file)

  if calibrate or not os.path.exists(calibration_file):
    system.Calibrate()
    system.SaveCalibration(calibration_file)
  else:
    system.LoadCalibration(calibration_file)

  runner = TestRunner(system)
  for dut in system:
    for app in dut:
      runner.AddTestCase(TouchMoveLatencyTest(app))
  runner.RunTests()


def Main():
  parser = OptionParser(usage=usage)
  parser.add_option("--calibrate",
                    dest="calibrate", default=False, action="store_true",
                    help="re-calibrate the robot system.")
  parser.add_option("--debug",
                    dest="debug", default=False, action="store_true",
                    help="Enable debug printouts and images.")
  (options, args) = parser.parse_args()

  RunTests(options.calibrate, options.debug)


if __name__ == "__main__":
  Main()