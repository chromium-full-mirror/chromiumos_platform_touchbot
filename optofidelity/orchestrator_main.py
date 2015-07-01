#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main module for command line interface to optofidelity latency tests."""
import logging
logging.basicConfig(filename="orchestrator.log", level=logging.WARN)

from optparse import OptionParser
import logging
import sys

from optofidelity.builder import SystemBuilder
from optofidelity.util import SingleInstanceLock


logging.getLogger("optofidelity").setLevel(level=logging.INFO)
logging.getLogger("optofidelity.failure").addHandler(
    logging.FileHandler("failures.log"))
logging.getLogger("optofidelity.perf").addHandler(
    logging.FileHandler("perf.log"))
logging.captureWarnings(True)


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
  "-v :42" All versions until and including the last one that starts with 42.

The wildcard * can be replaced with any glob such as:

$ %s nexus5/*
Run all tests on nexus5

$ %s */tap
Run tap benchmark on all devices

Whereas the names of benchmarks are put together in the following format:
  dut_name/subject_name/benchmark_name

"""


def RunBenchmarks(config, match, versions, list, skip_installed):
  builder = SystemBuilder.FromFile(config)

  if list:
    print "Available benchmarks:"
    for name in sorted(builder.orchestrator.benchmark_names):
      print "  ", name
  else:
    builder.orchestrator.UpdateAndRunBenchmarks(match, versions, skip_installed)


def Main():
  usage = usage_string % ((sys.argv[0],) * 4)
  parser = OptionParser(usage=usage)
  parser.add_option("--skip-installed", "-s",
                    dest="skip_installed", default=False, action="store_true",
                    help="Skip tests on already installed versions.")
  parser.add_option("--versions", "-v",
                    dest="versions", default="installed",
                    help="Specify versions to test.")
  parser.add_option("--list", "-l",
                    dest="list", default=False, action="store_true",
                    help="List all available benchmarks."),
  parser.add_option("--config", "-c",
                    dest="config", default="dev_config.xml",
                    help="Specify config file to use.")

  (options, args) = parser.parse_args()
  match = args[0] if len(args) > 0 else "*"

  RunBenchmarks(options.config, match, options.versions, options.list,
                options.skip_installed)


if __name__ == "__main__":
  with SingleInstanceLock("optofidelity"):
    Main()
