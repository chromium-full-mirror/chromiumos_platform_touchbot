# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ADBNavigator."""

from unittest import TestCase
import os
import sys

from optofidelity.system.navigator import NativeADBNavigator, WebADBNavigator
from tests.config import TEST_ADB_DEVICE_ID

_script_dir = os.path.dirname(os.path.realpath(__file__))

class AbstractNavBackendTests(TestCase):
  def assertUserAccepts(self, instructions):
    print instructions
    print "Press enter to accept"
    sys.stdin.readline()

  def createBackend(self):
    self.skipTest("Abstract TestCase class")

  def testOpenCloseSubjectTest(self):
    backend = self.createBackend()
    backend.Open(False)
    self.assertUserAccepts("Verify the subject has been opened.")
    backend.Close()
    self.assertUserAccepts("Verify the subject has been closed.")

  def testOpenCloseActivityTest(self):
    backend = self.createBackend()
    backend.Open(False)
    backend.OpenActivity("Flash")
    self.assertUserAccepts("Verify the flash page has been opened.")
    backend.CloseActivity()
    self.assertUserAccepts("Verify the flash page has been closed.")
    backend.Close()

  def testReset(self):
    backend = self.createBackend()
    backend.Open(False)
    backend.OpenActivity("Flash")
    self.assertUserAccepts("Verify the flash page has been opened.")
    backend.Reset()
    self.assertUserAccepts("Verify the subject has been reset.")


class WebADBNavigatorTests(AbstractNavBackendTests):
  CHROME_COMPONENT = "com.android.chrome/com.google.android.apps.chrome.Main"
  FLASH_FILE = os.path.join(_script_dir, "../../html/flash.html")

  def createBackend(self):
    if TEST_ADB_DEVICE_ID is None:
        self.skipTest("Specify TEST_ADB_DEVICE_ID to test live adb subject.")
    nav = WebADBNavigator(TEST_ADB_DEVICE_ID, self.CHROME_COMPONENT,
                          stay_alive=True)
    nav.AddActivity("Flash", dict(file=self.FLASH_FILE))
    return nav

class NativeADBNavigatorTests(AbstractNavBackendTests):
  PACKAGE_NAME = "org.chromium.touchlatency"
  APK_FILE = os.path.join(_script_dir, "../../apks/touchlatency.apk")

  def createBackend(self):
    if TEST_ADB_DEVICE_ID is None:
        self.skipTest("Specify TEST_ADB_DEVICE_ID to test live adb subject.")
    nav = NativeADBNavigator(TEST_ADB_DEVICE_ID, self.APK_FILE,
                             self.PACKAGE_NAME, stay_alive=True)
    nav.AddActivity("Flash", dict(intent="FlashActivity"))
    return nav
