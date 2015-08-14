# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ADBNavigator."""

from unittest import TestCase
import os
import sys

from optofidelity.system.fake import FakeDUTBackend, FakeNavigator
from optofidelity.system.navigator import (ManualNavigator, NativeADBNavigator,
                                           RobotNavigator, WebADBNavigator)
from optofidelity.util import CreateComponentFromXML
from tests.config import (ALLOW_USER_INTERACTION, TEST_ADB_DEVICE_ID,
                          CreateTestDUTBackend)

_script_dir = os.path.dirname(os.path.realpath(__file__))

class AbstractNavBackendTests(object):
  def assertUserAccepts(self, instructions):
    if not ALLOW_USER_INTERACTION:
      return
    print instructions
    print "Press enter to accept"
    sys.stdin.readline()

  def createBackend(self):
    self.skipTest("Abstract TestCase class")

  def openCloseActivityTest(self, activity_name):
    backend = self.createBackend()
    backend.SetUp()
    backend.Open()
    backend.OpenActivity(activity_name)
    self.assertUserAccepts("Verify the '%s' activity has been opened." %
                           activity_name)
    backend.Cleanup()

  def testCalibrationFlow(self):
    self.openCloseActivityTest("calibration")

  def testReset(self):
    backend = self.createBackend()
    backend.SetUp()
    backend.Open()
    backend.OpenActivity("calibration")
    self.assertUserAccepts("Verify the calibration page has been opened.")
    backend.Reset()
    self.assertUserAccepts("Verify the subject has been reset.")

  def testVerifyPrepare(self):
    backend = self.createBackend()
    backend.SetUp()
    backend.Verify()
    backend.Prepare()


WEB_ADB_CONFIG = """\
<navigator adb="{adb}" stay-alive="True"
           component="com.android.chrome/com.google.android.apps.chrome.Main">
  <activity name="calibration" file="{data}/flash.html" />
  <resource file="{data}/jquery.min.js" />
</navigator>
"""

class WebADBNavigatorTests(TestCase, AbstractNavBackendTests):
  CHROME_COMPONENT = "com.android.chrome/com.google.android.apps.chrome.Main"
  DATA_PATH = os.path.join(_script_dir, "../../apps/web")
  CONFIG = WEB_ADB_CONFIG.format(data=DATA_PATH, adb=TEST_ADB_DEVICE_ID)

  def createBackend(self):
    if TEST_ADB_DEVICE_ID is None:
        self.skipTest("Specify TEST_ADB_DEVICE_ID to test live adb subject.")
    return CreateComponentFromXML(WebADBNavigator, self.CONFIG, [None])


NATIVE_ADB_CONFIG = """\
<navigator adb="{adb}" package="org.chromium.touchlatency" apk="{apk}"
           stay-alive="True">
  <activity name="calibration" class-name="FlashActivity" />
  <activity name="home" action="android.intent.action.MAIN"
            category="android.intent.category.HOME"
            wait="True" force-stop="False" />
</navigator>
"""

class NativeADBNavigatorTests(TestCase, AbstractNavBackendTests):
  APK_FILE = os.path.join(_script_dir, "../../apps/Android/app/app-release.apk")
  CONFIG = NATIVE_ADB_CONFIG.format(adb=TEST_ADB_DEVICE_ID, apk=APK_FILE)

  def createBackend(self):
    if TEST_ADB_DEVICE_ID is None:
        self.skipTest("Specify TEST_ADB_DEVICE_ID to test live adb subject.")
    return CreateComponentFromXML(NativeADBNavigator, self.CONFIG, [None])

  def testHomeScreenFlow(self):
    self.openCloseActivityTest("home")


ROBOT_CONFIG = """\
<navigator>
  <activity name="neutral" icon="{data}/neutral.shm" />
  <activity name="calibration" icon="{data}/flash.shm" />
  <activity name="tap" text="Tap" />
</navigator>
"""

class RobotNavigatorTests(TestCase, AbstractNavBackendTests):
  DATA_PATH = os.path.join(_script_dir, "../../config/icons")
  CONFIG = ROBOT_CONFIG.format(data=DATA_PATH)

  def createBackend(self):
    dut = CreateTestDUTBackend()
    return CreateComponentFromXML(RobotNavigator, self.CONFIG, [dut])

  def createFakeBackend(self):
    dut = FakeDUTBackend("fake")
    return CreateComponentFromXML(RobotNavigator, self.CONFIG, [dut]), dut

  def testFailedWordDetection(self):
    nav, dut = self.createFakeBackend()
    dut._detect_words_rval = None
    self.assertRaises(Exception, nav.SetUp)

  def testFailedIconDetection(self):
    nav, dut = self.createFakeBackend()
    dut._detect_icon_rval = None
    self.assertRaises(Exception, nav.SetUp)

  def testStateKeeping(self):
    nav, dut = self.createFakeBackend()
    # Open fails if the navigator has not been set up.
    self.assertRaises(Exception, nav.Open)

    # Succeeds after SetUp.
    nav.SetUp()
    nav.Open()
    nav.Cleanup()

    # Also succeeds if the state has been saved.
    new_nav, dut = self.createFakeBackend()
    new_nav.state = nav.state
    new_nav.Open()
    new_nav.Cleanup()


class ManualNavigatorTests(TestCase, AbstractNavBackendTests):
  def createBackend(self):
    if not ALLOW_USER_INTERACTION:
      self.skipTest("Test requires user interaction.")
    return CreateComponentFromXML(ManualNavigator, "<navigator />", [None])


class BaseNavigatorTests(TestCase):
  def testCleanState(self):
    nav = FakeNavigator()
    self.assertRaises(Exception, nav.Close)
    self.assertRaises(Exception, lambda: nav.OpenActivity("calibration"))
    self.assertRaises(Exception, nav.CloseActivity)
    nav.Cleanup()
    nav.Reset()

  def testOpenState(self):
    nav = FakeNavigator()
    nav.Open()
    self.assertRaises(Exception, nav.Open)
    self.assertRaises(Exception, nav.CloseActivity)
    nav.Reset()

  def testActivityOpenState(self):
    nav = FakeNavigator()
    nav.Open()
    nav.OpenActivity("calibration")
    self.assertRaises(Exception, nav.Open)
    self.assertRaises(Exception, nav.Close)
    self.assertRaises(Exception, lambda: nav.OpenActivity("calibration"))
    nav.Cleanup()

  def testUnknownActivity(self):
    nav = FakeNavigator()
    nav.Open()
    self.assertRaises(Exception, lambda: nav.OpenActivity("unknown"))
