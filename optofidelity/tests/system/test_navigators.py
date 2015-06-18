# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ADBNavigator."""

from unittest import TestCase
import sys

from optofidelity.system.navigator import WebADBNavigator, NativeADBNavigator


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

  def testOpenClosePageTest(self):
    backend = self.createBackend()
    backend.Open(False)
    backend.OpenPage("Flash")
    self.assertUserAccepts("Verify the flash page has been opened.")
    backend.ClosePage()
    self.assertUserAccepts("Verify the flash page has been closed.")
    backend.Close()

  def testReset(self):
    backend = self.createBackend()
    backend.Open(False)
    backend.OpenPage("Flash")
    self.assertUserAccepts("Verify the flash page has been opened.")
    backend.Reset()
    self.assertUserAccepts("Verify the subject has been reset.")


class WebADBNavigatorTests(AbstractNavBackendTests):
  CHROME_COMPONENT = "com.android.chrome/com.google.android.apps.chrome.Main"
  ADB_DEVICE_ID = None

  def createBackend(self):
    if self.ADB_DEVICE_ID is None:
        self.skipTest("Specify ADB_DEVICE_ID to test live adb subject.")
    return WebADBNavigator(self.ADB_DEVICE_ID, self.CHROME_COMPONENT)


class NativeADBNavigatorTests(AbstractNavBackendTests):
  PACKAGE_NAME = "org.chromium.touchlatency"
  APK_FILE = "touchlatency.apk"
  ADB_DEVICE_ID = None

  def createBackend(self):
    if self.ADB_DEVICE_ID is None:
        self.skipTest("Specify ADB_DEVICE_ID to test live adb subject.")
    return NativeADBNavigator(self.ADB_DEVICE_ID, self.APK_FILE,
                              self.PACKAGE_NAME)
