# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ADBNavigator."""

from unittest import TestCase
import os

from optofidelity.system.fake import FakeDUTBackend, FakeNavigator
from optofidelity.system.navigator import (ManualNavigator, NativeADBNavigator,
                                           RobotNavigator, WebADBNavigator)
from optofidelity.util import CreateComponentFromXML
from tests.config import CONFIG, CreateTestDUTBackend

_script_dir = os.path.dirname(os.path.realpath(__file__))

class AbstractNavBackendTests(object):
  def createBackend(self):
    pass

  def openCloseActivityTest(self, activity_name):
    backend = self.createBackend()
    backend.SetUp()
    backend.Open()
    backend.OpenActivity(activity_name)
    CONFIG.AskUserAccept("Verify the '%s' activity has been opened." %
                         activity_name)
    backend.Cleanup()

  def testCalibrationFlow(self):
    self.openCloseActivityTest("calibration")

  def testReset(self):
    backend = self.createBackend()
    backend.SetUp()
    backend.Open()
    backend.OpenActivity("calibration")
    CONFIG.AskUserAccept("Verify the calibration page has been opened.")
    backend.Reset()
    CONFIG.AskUserAccept("Verify the subject has been reset.")

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

  def createBackend(self):
    configuration = WEB_ADB_CONFIG.format(data=self.DATA_PATH,
                                          adb=CONFIG["adb_device_id"])
    return CreateComponentFromXML(WebADBNavigator, configuration, [None])


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

  def createBackend(self):
    configuration = NATIVE_ADB_CONFIG.format(adb=CONFIG["adb_device_id"],
                                             apk=self.APK_FILE)
    return CreateComponentFromXML(NativeADBNavigator, configuration, [None])

  def testHomeScreenFlow(self):
    self.openCloseActivityTest("home")


ROBOT_CONFIG_FORMAT = """\
<navigator>
  <activity name="neutral" icon="{data}/neutral.shm" />
  <activity name="calibration" icon="{data}/flash.shm" />
  <activity name="tap" text="tap" />
</navigator>
"""

ROBOT_CONFIG_FORMAT_IPHONE = """\
<navigator>
  <activity name="neutral" icon="{data}/neutral.shm" />
  <activity name="calibration" icon="{data}/flash.shm" />
</navigator>
"""

class RobotNavigatorTests(TestCase, AbstractNavBackendTests):
  DATA_PATH = os.path.join(_script_dir, "../../config/icons")
  ROBOT_CONFIG = ROBOT_CONFIG_FORMAT.format(data=DATA_PATH)
  ROBOT_CONFIG_IPHONE = ROBOT_CONFIG_FORMAT_IPHONE.format(data=DATA_PATH)

  def createBackend(self):
    dut = CreateTestDUTBackend()
    return CreateComponentFromXML(RobotNavigator, self.ROBOT_CONFIG_IPHONE,
                                  [dut])

  def createFakeBackend(self):
    dut = FakeDUTBackend("fake")
    return CreateComponentFromXML(RobotNavigator, self.ROBOT_CONFIG, [dut]), dut

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
    CONFIG.Require("user_interaction")
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
