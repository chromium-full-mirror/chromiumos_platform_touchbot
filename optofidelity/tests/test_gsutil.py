# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the GSUtil functions."""
from tempfile import NamedTemporaryFile
from unittest import TestCase
import os

from optofidelity.gsutil import GSFile, GSFolder, GSOpenFile

GS_URL = None
GS_FILE_URL = os.path.join(GS_URL, "test.txt") if GS_URL else None

class GSUtilTests(TestCase):
  def setUp(self):
    if GS_URL is None:
      self.skipTest("Specify GS_URL to run gs_util tests.")

  def tearDown(self):
    os.system("gsutil rm " + GS_FILE_URL)

  def testGSOpenFile(self):
    with NamedTemporaryFile() as temp_file:
      # Test same behavior for local file as well as remote file
      for path in (GS_FILE_URL, temp_file.name):
        with GSOpenFile(path, "w") as file_obj:
          file_obj.write("42")

        with GSOpenFile(path, "a") as file_obj:
          file_obj.write("42")

        with GSOpenFile(path, "r") as file_obj:
          self.assertEqual(file_obj.read(), "4242")

  def testPreserveSuffix(self):
    with GSFile(GS_FILE_URL) as gs_file:
      self.assertTrue(gs_file.endswith(".txt"))

  def testFolder(self):
    with GSFolder(GS_URL) as folder:
      with open(os.path.join(folder, "test.txt"), "w") as file_obj:
        file_obj.write("42")

    with GSFolder(GS_URL, download=True, upload=False) as folder:
      with open(os.path.join(folder, "test.txt")) as file_obj:
        self.assertEqual(file_obj.read(), "42")
