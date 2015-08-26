#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for debugging command line interface"""
from optparse import OptionParser
import logging
import os

from optofidelity.benchmark import Benchmark
from optofidelity.builder import SystemBuilder
from optofidelity.detection import (MultithreadedVideoProcessor,
                                    ScreenCalibration,
                                    SinglethreadedVideoProcessor)
from optofidelity.reporting import BenchmarkReport
from optofidelity.util import GSDownload, GSPathExists, ProgressBar


usage_string = """
"""

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")


def LoadBenchmarkFromURL(url_or_uid):
  builder = SystemBuilder.FromFile("config/base.xml", object())
  logging.getLogger("optofidelity").setLevel(level=logging.DEBUG)

  if os.path.exists(url_or_uid) or url_or_uid.startswith("gs://"):
    url = url_or_uid
  else:
    uid = url_or_uid
    url = os.path.abspath(os.path.join(CACHE_DIR, uid))
    if not os.path.exists(url):
      gs_url = os.path.join(builder.attrib["results"], uid)
      with ProgressBar("Downloading %s" % gs_url):
        def CacheFile(filename):
          gs_path = os.path.join(gs_url, filename)
          if GSPathExists(gs_path):
            GSDownload(gs_path, url)
        os.mkdir(url)
        CacheFile("benchmark.pickle")
        CacheFile("video.avi")
  return Benchmark.Load(url), url


def ProcessBenchmark(url_or_uid, what, debug_flags):
  benchmark, url = LoadBenchmarkFromURL(url_or_uid)
  benchmark.screen_calibration.Validate()
  try:
    if what in ("all", "video"):
      print debug_flags
      if len(debug_flags):
        video_processor = SinglethreadedVideoProcessor()
      else:
        video_processor = MultithreadedVideoProcessor()
      benchmark.ProcessVideo(video_processor, debug_flags)
      print benchmark.trace
    if what in ("all", "video", "trace"):
      print "Processing Trace"
      try:
        benchmark.ProcessTrace()
        print benchmark.results
      except:
        import traceback
        traceback.print_exc()
    if what in ("all", "video", "trace", "report"):
      print "Generating Report"
      report = BenchmarkReport(url)
      report.GenerateReport(benchmark.results, benchmark.trace,
                            benchmark.screen_calibration, benchmark.video)
      print "Test Failed: file://%s/report.html" % url
  finally:
    benchmark.Save(url, debug_info=True)


def Main():
  usage = usage_string
  parser = OptionParser(usage=usage)
  parser.add_option("--debug","-d",
                    dest="debug_flags", default="",
                    help="Dump flags.")
  parser.add_option("--process", "-p",
                    dest="process", default="all",
                    help="Process local files")

  (options, args) = parser.parse_args()
  debug_flags = []
  if options.debug_flags:
    debug_flags = options.debug_flags.split(",")
  ProcessBenchmark(args[0], options.process, debug_flags)

if __name__ == "__main__":
  Main()
