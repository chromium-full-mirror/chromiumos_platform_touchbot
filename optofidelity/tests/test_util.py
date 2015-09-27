# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the GSUtil functions."""
from tempfile import NamedTemporaryFile
from unittest import TestCase
import os
import time
import numpy as np
from optofidelity.util import (Cambrionix, GSFile, GSFindUniqueFilename,
                               GSFolder, GSOpenFile, GSTouch,
                               SingleInstanceLock, nputil)
from tests.config import CONFIG


class GSUtilTests(TestCase):
  def setUp(self):
    self.gs_folder = CONFIG["gs_folder_url"]
    self.gs_file = os.path.join(self.gs_folder, "test.txt")

  def tearDown(self):
    os.system("gsutil rm " + self.gs_file)

  def testUniqueFilename(self):
    path1, file1 = GSFindUniqueFilename(self.gs_folder, "base_name")
    GSTouch(os.path.join(path1, ".exists"))
    path2, file2 = GSFindUniqueFilename(self.gs_folder, "base_name")
    self.assertTrue(file1.startswith("base_name"))
    self.assertTrue(file2.startswith("base_name"))
    self.assertNotEqual(file1, file2)

  def testGSOpenFile(self):
    with NamedTemporaryFile() as temp_file:
      # Test same behavior for local file as well as remote file
      for path in (self.gs_file, temp_file.name):
        with GSOpenFile(path, "w") as file_obj:
          file_obj.write("42")

        with GSOpenFile(path, "a") as file_obj:
          file_obj.write("42")

        with GSOpenFile(path, "r") as file_obj:
          self.assertEqual(file_obj.read(), "4242")

  def testPreserveSuffix(self):
    with GSFile(self.gs_file) as gs_file:
      self.assertTrue(gs_file.endswith(".txt"))

  def testFolder(self):
    with GSFolder(self.gs_folder) as folder:
      with open(os.path.join(folder, "test.txt"), "w") as file_obj:
        file_obj.write("42")

    with GSFolder(self.gs_folder, download=True, upload=False) as folder:
      with open(os.path.join(folder, "test.txt")) as file_obj:
        self.assertEqual(file_obj.read(), "42")


class SingleInstanceLockTests(TestCase):
  def testSingleInstanceSuccess(self):
    with SingleInstanceLock("test"):
      print "Hello"

  def testSingleInstanceFailure(self):
    def ThisShouldFail():
      with SingleInstanceLock("test"):
        print "Hello"
    with SingleInstanceLock("test"):
      self.assertRaises(Exception, ThisShouldFail)


class CambrionixTests(TestCase):
  def testPortMode(self):
    cambrionix = Cambrionix(CONFIG["cambrionix_serial_device"])

    for mode in ("charge", "sync", "off"):
      cambrionix.SetPortMode(mode)
      time.sleep(1)
      for port in cambrionix.ports_status.itervalues():
        self.assertEqual(port.mode, mode)

  def testSinglePortMode(self):
    cambrionix = Cambrionix(CONFIG["cambrionix_serial_device"])
    target_port = 8

    cambrionix.SetPortMode("off")
    for mode in ("charge", "sync", "off"):
      cambrionix.SetPortMode(mode, port=target_port)
      time.sleep(1)
      for port in cambrionix.ports_status.itervalues():
        if port.id == target_port:
          self.assertEqual(port.mode, mode)
        else:
          self.assertEqual(port.mode, "off")

class NPUtilTests(TestCase):
  def assertNearlyEqual(self, a, b, epsilon=0.01):
    if len(a) != len(b) or np.any(np.abs(a - b) > epsilon):
      self.fail("%s != %s" % (a, b))

  def testFindZeroCrossings(self):
    input = np.asarray([-1, 0, 1, 0.1, -0.1])
    expected = [2, 4]
    self.assertNearlyEqual(nputil.FindZeroCrossings(input), expected)

  def testFindLocalExtemes(self):
    input = np.asarray([-1, 0, 1, 0, -1, 0, -1])
    expected = [2, 4, 5]
    self.assertNearlyEqual(nputil.FindLocalExtremes(input), expected)

  def testTruncate(self):
    self.assertEqual(nputil.Truncate(0, -1, 1), 0)
    self.assertEqual(nputil.Truncate(-2, -1, 1), -1)
    self.assertEqual(nputil.Truncate(2, -1, 1), 1)

    input = np.asarray([-2, -1, 0, 1, 2])
    expected = np.asarray([-1, -1, 0, 1, 1])
    self.assertNearlyEqual(nputil.Truncate(input, -1, 1), expected)

  def testLowPass(self):
    input = np.asarray([0, 0, 0, 1, 0, 0, 0])
    expected = np.asarray([0, 0, 0.33, 0.33, 0.33, 0, 0])
    self.assertNearlyEqual(nputil.LowPass(input, 3), expected)

  def testBoxFilter(self):
    input = np.asarray([0, 1, 0, 1, 10, 11, 10, 1, 0, 1])
    expected = np.asarray([0, 0, 0, 0, 10, 10, 10, 1, 1, 1])
    self.assertNearlyEqual(nputil.BoxFilter(input, 5), expected)

  def testDeDuplicate(self):
    input = np.asarray([0, 9, 10, 11, 20])
    expected = [0, 11, 20]
    self.assertEqual(list(nputil.DeDuplicate(input, 5)), expected)

  def testSegment(self):
    input = np.asarray([0, 1, 1, 1, 0, 1, 1, 0, 1], dtype=np.bool)
    expected = [(1, 3), (5, 6), (8, 8)]
    self.assertEqual(list(nputil.Segment(input)), expected)

  def testEstimateShift(self):
    static = np.asarray([0, 0, 0, 0.5, 1, 0.5, 0])
    shifting = np.asarray([0, 0.5, 1, 0.5, 0])
    for technique in ("mse", "mae"):
      self.assertEqual(nputil.EstimateShift(static, shifting, technique), 2)

  def testShift(self):
    input = np.asarray([0, 1, 2, 3])
    self.assertNearlyEqual(nputil.Shift(input, 1, "edge"), [0, 0, 1, 2])
    self.assertNearlyEqual(nputil.Shift(input, -1, "edge"), [1, 2, 3, 3])
    self.assertNearlyEqual(nputil.Shift(input, 1, "wrap"), [3, 0, 1, 2])
    self.assertNearlyEqual(nputil.Shift(input, -1, "wrap"), [1, 2, 3, 0])

  def testAlignArrays(self):
    target = np.asarray([0, 0, 0, 0.5, 1, 0.5, 0])
    def assertMatches(shifting, shift):
      aligned = nputil.AlignArrays(target, shifting, shift)
      self.assertNearlyEqual(aligned, target)
    assertMatches([0, 0.5, 1, 0.5, 0, 0, 0], 2)

  def testFindSettlingIndex(self):
    input = [0, 0.1, 0.5, 0.8, 0.79, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0]

    def SettlingTest(params, expected):
      self.assertEqual(nputil.FindSettlingIndex(input, 2, **params), expected)
    SettlingTest(dict(min_value=1.0), 7)
    SettlingTest(dict(min_value=1.0, max_distance=4), None)
    SettlingTest(dict(max_slope=0.1), 3)

  def testFindStateChanges(self):
    input = np.asarray([0, 0, 0.1, 0.5, 0.7, 0.6, 0.9, 1.0, 1.0])
    actual = nputil.FindStateChanges(input, dict(max_value=0.0),
                                     dict(min_value=1.0))
    expected = [(1, 7)]
    self.assertEqual(list(actual), expected)


  def testFindPeaks(self):
    input = np.asarray([0, 0, 0.1, 0.5, 1.0, 1.0, 0.5, 0.1, 0, 0])
    actual = nputil.FindPeaks(input, max_value=0.0)
    expected = [(1, 8)]
    self.assertEqual(list(actual), expected)
