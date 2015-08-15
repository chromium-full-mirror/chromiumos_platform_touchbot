# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.orchestrator import (AndroidUpdater, ChromeUpdater,
                                       FakeUpdater, ManualUpdater)
from optofidelity.util import AskUserContinue, CreateComponentFromXML
from tests.config import ALLOW_USER_INTERACTION, TEST_ADB_DEVICE_ID


class UpdaterTests(TestCase):
  def installLatestVersionTest(self, updater):
    latest = updater.available_versions[0]
    updater.Install(latest)
    self.assertEqual(updater.installed_version, latest)

  def uninstallTest(self, updater):
    updater.Uninstall()
    self.assertEqual(updater.installed_version, None)


class ChromeUpdaterTests(UpdaterTests):
  def testInstallUninstallFlow(self):
    if TEST_ADB_DEVICE_ID is None:
      self.skipTest("Specify TEST_ADB_DEVICE_ID to test live adb subject.")
      return

    for channel in ("stable", "beta", "dev"):
      config = "<updater adb='{adb}' channel='{channel}' />"
      config = config.format(adb=TEST_ADB_DEVICE_ID, channel=channel)
      updater = CreateComponentFromXML(ChromeUpdater, config)
      self.installLatestVersionTest(updater)
      updater.Verify()
      if channel is not "stable":
        self.uninstallTest(updater)


class AndroidUpdaterTests(UpdaterTests):
  def testInstalledVersion(self):
    if TEST_ADB_DEVICE_ID is None:
      self.skipTest("Specify TEST_ADB_DEVICE_ID to test live adb subject.")
      return

    config = "<updater adb='{adb}' />".format(adb=TEST_ADB_DEVICE_ID)
    updater = CreateComponentFromXML(AndroidUpdater, config)
    version = updater.installed_version
    self.assertIsNotNone(version)
    if ALLOW_USER_INTERACTION:
      AskUserContinue("Android version is: %s" % version)


class ManualUpdaterTests(UpdaterTests):
  def testInstalledVersion(self):
    config = "<updater version='42' />"
    updater = CreateComponentFromXML(ManualUpdater, config)
    self.assertEqual(updater.installed_version, "42")


class FakeUpdaterTests(UpdaterTests):
  def testInstallUninstallFlow(self):
    updater = CreateComponentFromXML(FakeUpdater, "<updater />")
    updater._available_versions = ["42"]
    self.installLatestVersionTest(updater)
    updater.Verify()
    self.uninstallTest(updater)