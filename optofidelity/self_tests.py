#! /usr/bin/env python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Module for running video based integration tests.

Provides automated testing of test runs dumped to video files.
The tests are organized in a folder structure under self_tests, one folder
for each test class, organized into two subfolders good and bad.
Videos in the good folder require the test to successfully process, while
videos in the bad folder are expected to fail and return an error.
"""

from fnmatch import fnmatch
from optparse import OptionParser
import os
import traceback
import numpy as np
import warnings

from optofidelity.latency import TouchMoveLatencyTest
from optofidelity.test_runner import TestRunner
from optofidelity.videoproc import VideoException
from main import RegisterTestClasses


script_dir = os.path.dirname(os.path.realpath(__file__))
tests_dir = os.path.join(script_dir, "self_tests")

gs_path = "gs://touchbot/optofidelity/self_tests"

class TestCase(object):
  def __init__(self, name, expect_success):
    self.name = name
    self.expect_success = expect_success

  @staticmethod
  def DiscoverAll(runner):
    for test_class in runner.test_classes.keys() + ["ScreenDetection"]:
      good_folder = os.path.join(test_class, "good")
      for name in TestCase.DiscoverTestNamesInFolder(good_folder):
        yield TestCase(name, True)

      bad_folder = os.path.join(test_class, "bad")
      for name in TestCase.DiscoverTestNamesInFolder(bad_folder):
        yield TestCase(name, False)

  @staticmethod
  def DiscoverTestNamesInFolder(folder):
    abs_dir = os.path.join(tests_dir, folder)
    for filename in os.listdir(abs_dir):
      if filename.endswith(".mov"):
        test_name = os.path.join(folder, filename[:-4])
        yield test_name

def RunTests(glob, debug):
  runner = TestRunner(None)
  RegisterTestClasses(runner)

  cases = TestCase.DiscoverAll(runner)
  if glob:
    cases = [c for c in cases if fnmatch(c.name, glob)]

  results = {}
  for case in cases:
    print "Running test", case.name
    results[case.name] = False
    try:
      path = os.path.join(tests_dir, case.name)
      runner.ProcessVideoFromFile(path, debug)
      if case.expect_success:
        results[case.name] = True
      else:
        print "Expected detection failure."
    except VideoException, e:
      if case.expect_success:
        traceback.print_exc()
        results[case.name] = False
      else:
        print "Expected exception:", e
        results[case.name] = True
      continue
    except Exception:
      traceback.print_exc()
  return results

usage = """Self-Tests usage examples

The self-test requires test videos in the self_tests folder, which are not
included in the git repository. Instead they have to be downloaded from
cloud storage by running:

$ %prog --download

After that you can:

Run all tests:
$ %prog

Run a selected list of tests:
$ %prog ScreenDetection/*

Debug a tests:
$ %prog TestName --debug=all

View normalized image and line debugging:
$ %prog TestName --debug=normalized,line
"""

def Main():
  parser = OptionParser(usage=usage)
  parser.add_option("--debug",
                    dest="debug", default=None,
                    help="Enable debug printouts and images.")
  parser.add_option("--upload", "-u",
                    dest="upload", default=False, action="store_true",
                    help="Upload local self test videos to cloud storage. "+
                         "Note: You need write access to gs://touchbot, "+
                         "contact denniskempin@google.com.")
  parser.add_option("--download", "-d",
                    dest="download", default=False, action="store_true",
                    help="Download self test videos from cloud storage.")
  (options, args) = parser.parse_args()

  glob = None
  if args:
    glob = args[0]

  debug = []
  if options.debug:
    debug = options.debug.split(",")

  if options.upload:
    os.system("gsutil -m rsync -r %s %s" % (tests_dir, gs_path))
    os.system("gsutil -m acl -r set public-read %s" % gs_path)
    return

  if options.download:
    os.system("gsutil rsync -r %s %s" % (gs_path, tests_dir))

  np.seterr(all='raise')
  warnings.filterwarnings('error', category=UserWarning)

  results = RunTests(glob, debug)

  print "Self-Test Results:"
  for name, result in results.items():
    msg = "Success" if result else "Failure"
    print "\t", msg, name

if __name__ == "__main__":
  Main()