# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.orchestrator.subject_setup import ADBSettingsSetup
from optofidelity.util import CreateComponentFromXML
from tests.config import CONFIG
from optofidelity.util import ADB


SETTINGS_CONFIG = """
<setup adb="{adb}">
  <setting name="screen_brightness" value="42" />
</setup>
"""

class TestADBSettingsSetup(TestCase):
  def testSettings(self):
    adb = ADB(CONFIG["adb_device_id"])

    config = SETTINGS_CONFIG.format(adb=CONFIG["adb_device_id"])
    setup = CreateComponentFromXML(ADBSettingsSetup, config)
    setup.SetUp()
    self.assertEqual(adb.GetSetting("system", "screen_brightness"), "42")

    adb = ADB(CONFIG["adb_device_id"])
    adb.PutSetting("system", "screen_brightness", "255")
