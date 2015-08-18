# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.orchestrator.updater import (AndroidUpdater, ChromeUpdater,
                                               FakeUpdater, ManualUpdater)
from optofidelity.util import CreateComponentFromXML
from tests.config import CONFIG


class UpdaterTests(TestCase):
  def installLatestVersionTest(self, updater):
    latest = updater.available_versions[-1]
    updater.Install(latest)
    self.assertEqual(updater.installed_version, latest)

  def uninstallTest(self, updater):
    updater.Uninstall()
    self.assertEqual(updater.installed_version, None)


class ChromeUpdaterTests(UpdaterTests):
  def testInstallUninstallFlow(self):
    for channel in ("stable", "beta", "dev"):
      config = "<updater adb='{adb}' channel='{channel}' />"
      config = config.format(adb=CONFIG["adb_device_id"], channel=channel)
      updater = CreateComponentFromXML(ChromeUpdater, config)
      self.installLatestVersionTest(updater)
      updater.Verify()
      if channel != "stable":
        self.uninstallTest(updater)


class AndroidUpdaterTests(UpdaterTests):
  def testInstallUninstallFlow(self):
    config = "<updater adb='{adb}' />".format(adb=CONFIG["adb_device_id"])
    updater = CreateComponentFromXML(AndroidUpdater, config)
    version = updater.installed_version
    self.assertIsNotNone(version)
    CONFIG.AskUserAccept("Android version is: %s" % version)


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
