# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase
from optofidelity.system._updater import ChromeUpdater

ADB_DEVICE_ID = None

class ChromeUpdaterTests(TestCase):

  def setUp(self):
    if ADB_DEVICE_ID is None:
      self.skipTest("Specify ADB_DEVICE_ID to test live adb subject.")

  def testChromeBetaUpdater(self):
    updater = ChromeUpdater(ADB_DEVICE_ID, "beta")

    # Test uninstall
    if updater.installed_version:
      updater.Uninstall()
    self.assertEqual(updater.installed_version, None)

    # Test install of latest version
    latest = updater.available_versions[0]
    updater.Install(latest, print_progress=True)
    self.assertEqual(updater.installed_version, latest)

    # Test downgrading to previous version
    previous = updater.available_versions[1]
    updater.Install(previous, print_progress=True)
    self.assertEqual(updater.installed_version, previous)

  def testChromeStableUpdater(self):
    updater = ChromeUpdater(ADB_DEVICE_ID, "stable")

    # Test install of latest version
    latest = updater.available_versions[0]
    updater.Install(latest, print_progress=True)
    self.assertEqual(updater.installed_version, latest)

    # Test downgrading to previous version
    previous = updater.available_versions[1]
    updater.Install(previous, print_progress=True)
    self.assertEqual(updater.installed_version, previous)