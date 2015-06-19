#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""
import logging
logging.basicConfig(filename="orchestrator.log", level=logging.WARN)
logging.getLogger("optofidelity").setLevel(level=logging.INFO)
logging.getLogger("optofidelity.detection").setLevel(level=logging.DEBUG)
logging.getLogger("optofidelity.system.tnt").setLevel(level=logging.DEBUG)
logging.captureWarnings(True)

from optparse import OptionParser
import os
import sys

from optofidelity.benchmark import BenchmarkRunner
from optofidelity.detection import MultithreadedVideoProcessor
from optofidelity.orchestrator import Dashboard, Orchestrator
from optofidelity.builder import SystemBuilder

from config import (config_file, dashboard_endpoint, results_db_url,
                    results_url, state_file)


usage_string = """Orchestrator usage examples:

The orchestrator runs tests and updates multiple devices. All results
are stored in the local benchmark_results folder, with a database file
containing a summary of all results.

$ %s *
Run all tests on all devices in current state.

$ %s --update *
Update all devices to the latest chrome version, then run tests on updated
devices.

$ %s --update *
Update all devices to the specifiedchrome version, then run tests.

The wildcard * can be replaced with any glob such as:

$ %s nexus5/*
Run all tests on nexus5

$ %s */tap
Run tap test on all devices
"""


def RunBenchmarks(match, skip_update, debug_flags, force_version, history,
                  xkcd):
  config = SystemBuilder.FromFile(config_file)
  system = config.benchmark_system
  video_processor = MultithreadedVideoProcessor()
  runner = BenchmarkRunner(system, video_processor)
  dashboard = Dashboard(dashboard_endpoint)
  orchestrator = Orchestrator(system, runner, dashboard, results_url,
                              results_db_url, xkcd=xkcd)

  if os.path.exists(state_file):
    system.LoadState(state_file)

  if history:
    orchestrator.RunHistoryBenchmarks(match, debug_flags, history)
  else:
    orchestrator.UpdateAndRunBenchmarks(match, debug_flags, force_version,
                                        skip_update=skip_update)


def Main():
  usage = usage_string % ((sys.argv[0],) * 5)
  parser = OptionParser(usage=usage)
  parser.add_option("--update", "-u",
                    dest="update", default=False, action="store_true",
                    help="Update devices before running tests.")
  parser.add_option("--force-version", "-f",
                    dest="force_version", default=None,
                    help="Force update to specific version.")
  parser.add_option("--history",
                    dest="history", default=None,
                    help="Benchmark all versions since specified version.")
  parser.add_option("--xkcd",
                    dest="xkcd", default=False, action="store_true",
                    help="Give reports more authority.")
  (options, args) = parser.parse_args()
  match = args[0] if len(args) > 0 else "*"

  RunBenchmarks(match, not options.update, [], options.force_version,
                options.history, options.xkcd)


if __name__ == "__main__":
  Main()
