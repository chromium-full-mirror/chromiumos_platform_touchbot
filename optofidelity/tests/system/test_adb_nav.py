# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ADBNavigator."""

from unittest import TestCase
import sys

from optofidelity.system._navigators import ADBNavigator


ADB_DEVICE_ID = None

class ADBNavBackendTests(TestCase):
  CHROME_COMPONENT = "com.android.chrome/com.google.android.apps.chrome.Main"

  def assertUserAccepts(self, instructions):
    print instructions
    print "Press enter to accept"
    sys.stdin.readline()

  def testOpeningClosing(self):
    if ADB_DEVICE_ID is None:
        self.skipTest("Specify ADB_DEVICE_ID to test live adb subject.")
    nav_backend = ADBNavigator(ADB_DEVICE_ID, self.CHROME_COMPONENT)
    nav_backend.Open(False)
    nav_backend.OpenPage("Flash")
    self.assertUserAccepts("Verify the tap page has been opened.")
    nav_backend.ClosePage()
    self.assertUserAccepts("Verify the tap page has been closed.")
    nav_backend.Close()