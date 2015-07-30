#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""
from optparse import OptionParser
import sys

from optofidelity.builder import SystemBuilder
from optofidelity.util import SingleInstanceLock


usage_string = """Orchestrator usage examples:

The orchestrator runs tests and updates multiple devices.

$ %s *
Run all tests on all devices in current state.

$ %s * -v version[:end_version]
Run benchmarks on single or range of versions. The versions can have the
following format:

  "-v 42" Last version that starts with 42.
  "-v 42-" First version that starts with 42.
  "-v installed" Currently installed version.
  "-v latest" Latest version.

You can also specify ranges of versions by separating the first and last version
to run with a colon. If nothing is specified on either side, the first or last
version is implied.

  "-v 42-:42" Every version that starts with 42.
  "-v installed:" All versions since the currently installed one.
  "-v :42" All versions until the last one that starts with 42..

The wildcard * can be replaced with any glob such as:

$ %s nexus5/*
Run all tests on nexus5

$ %s */tap
Run tap benchmark on all devices

Whereas the names of benchmarks are put together in the following format:
  dut_name/subject_name/benchmark_name

"""


def RunBenchmarks(matches, options):
  builder = SystemBuilder.FromFile(options.config, options)
  if options.prepare:
    builder.orchestrator.PrepareSubjects()
  for match in matches:
    if options.info:
      builder.orchestrator.PrintInfo(match)
    elif options.setup:
      builder.orchestrator.SetUpSubjects(match, options.versions)
    else:
      builder.orchestrator.UpdateAndRunBenchmarks(match, options.versions,
                                                  options.skip_installed)


def Main():
  usage = usage_string % ((sys.argv[0],) * 4)
  parser = OptionParser(usage=usage)
  parser.add_option("--skip-installed", "-s",
                    dest="skip_installed", default=False, action="store_true",
                    help="Skip tests on already installed versions.")
  parser.add_option("--versions", "-v",
                    dest="versions", default="installed",
                    help="Specify versions to test.")
  parser.add_option("--info", "-i",
                    dest="info", default=False, action="store_true",
                    help="Show info on subjects and benchmarks."),
  parser.add_option("--prepare", "-p",
                    dest="prepare", default=False, action="store_true",
                    help="Reset system and prepare devices.")
  parser.add_option("--config", "-c",
                    dest="config", default="config/dev.xml",
                    help="Specify config file to use.")
  parser.add_option("--setup",
                    dest="setup", default=False, action="store_true",
                    help="Setup specified devices.")
  parser.add_option("--save-video",
                    dest="save_video", default=False, action="store_true",
                    help="Save video of each benchmark.")
  parser.add_option("--quick",
                    dest="quick", default=False, action="store_true",
                    help="Quick benchmark without repetitions.")
  (options, args) = parser.parse_args()
  matches = args if len(args) > 0 else ["*"]

  RunBenchmarks(matches, options)


if __name__ == "__main__":
  with SingleInstanceLock("optofidelity"):
    Main()
