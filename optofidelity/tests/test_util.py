# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the GSUtil functions."""
from tempfile import NamedTemporaryFile
from unittest import TestCase
import os

from optofidelity.util import (GSFile, GSFindUniqueFilename, GSFolder,
                               GSOpenFile, GSTouch, SingleInstanceLock)

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
