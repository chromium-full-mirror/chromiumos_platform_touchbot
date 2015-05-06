#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""

from optparse import OptionParser
import logging
import os
import sys

from optofidelity.benchmark import Benchmark, LEDCalibrator
from optofidelity.detection import (MultithreadedVideoProcessor,
                                    ScreenCalibration)
from optofidelity.system import BenchmarkSystem

logging.basicConfig(level=logging.INFO)


usage_string = """Benchmark usage examples:

$ %s nexus5/clank touch_move -o dir [--save-video]
Run touch_move benchmark on nexus5/clank and store results into out_dir.
Optionally save video of test for re-running the processing locally.

$ %s -i dir -p video
Open benchmark from dir, re-process video. (Benchmark at dir had to be saved
with --save-video)

$ %s -i dir -p trace
Open benchmark from dir, re-process trace. Does not require video.
"""

script_dir = os.path.dirname(os.path.realpath(__file__))
config_file = os.path.join(script_dir, "optofidelity.xml")
state_file = os.path.join(script_dir, "optofidelity.state")


def ProcessBenchmarkFromFile(path, out_dir, what, debug_flags):
  if out_dir is None:
    out_dir = path
  benchmark = Benchmark.Load(path)
  try:
    if what in ("all", "video"):
      benchmark.ProcessVideo(debug_flags, multithreaded=len(debug_flags) == 0)
    if what in ("all", "video", "trace"):
      benchmark.ProcessTrace()
    if what in ("all", "video", "trace", "report"):
      benchmark.GenerateReport(out_dir)
  finally:
    benchmark.Save(out_dir, debug_info=True, video=True)


def RunBenchmark(subject_name, benchmark_name, out_dir, save_video,
                 debug_flags):
  system = BenchmarkSystem(config_file)
  if os.path.exists(state_file):
    system.LoadState(state_file)

  if not subject_name or not benchmark_name:
    print "specify subject_name and benchmark_name"
    return

  subject = system.subjects[subject_name]
  try:
    subject.Open(False)
    benchmark = Benchmark(subject_name, benchmark_name, {})
    benchmark.CalibrateScreen(system)
    results = benchmark.Run(system, debug_flags)
    print results
    subject.Close()
  finally:
    subject.Cleanup()
    system.SaveState(state_file)

    if out_dir:
      benchmark.Save(out_dir, debug_info=True, video=save_video)

    system.SaveState(state_file)


def LEDCalibration():
  system = BenchmarkSystem(config_file)
  video_processor = MultithreadedVideoProcessor()
  calibrator = LEDCalibrator(video_processor)

  down, up = calibrator.CalibrateLED(system.led_calibration_subject, True)
  print "Down Delay: %.2fms" % down
  print "Up Delay: %.2fms" % up


def Main():
  usage = usage_string % ((sys.argv[0],) * 3)
  parser = OptionParser(usage=usage)
  parser.add_option("--debug",
                    dest="debug_flags", default=[],
                    help="Dump flags.")
  parser.add_option("--save-video",
                    dest="save_video", default=False, action="store_true",
                    help="Save video to disk.")
  parser.add_option("--input", "-i",
                    dest="input", default=None,
                    help="Open benchmark from folder.")
  parser.add_option("--process", "-p",
                    dest="process", default=None,
                    help="Process local files")
  parser.add_option("--out", "-o",
                    dest="out", default=None,
                    help="output folder")
  parser.add_option("--led-calib",
                    dest="led_calib", default=False, action="store_true",
                    help="Screen Calibration")

  (options, args) = parser.parse_args()

  if options.led_calib:
    LEDCalibration()
  elif options.input:
    ProcessBenchmarkFromFile(options.input, options.out, options.process,
                             options.debug_flags)
  else:
    subject_name = args[0] if len(args) > 0 else None
    benchmark_name = args[1] if len(args) > 1 else None
    RunBenchmark(subject_name, benchmark_name, options.out,
                 options.save_video, options.debug_flags)


if __name__ == "__main__":
  Main()
