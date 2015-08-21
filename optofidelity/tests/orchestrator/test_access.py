# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase

from optofidelity.orchestrator.access import CambrionixAccess
from optofidelity.util import ADB, CreateComponentFromXML
from tests.config import CONFIG
from tests.system.test_navigators import createNativeADBNavigator


class TestADBSettingsSetup(TestCase):
  def createAccess(self):
    SETTINGS_CONFIG = "<access serial='{serial}' port='{port}' adb='{adb}' />"
    config = SETTINGS_CONFIG.format(serial=CONFIG["cambrionix_serial_device"],
                                    port=CONFIG["cambrionix_dut_port_id"],
                                    adb=CONFIG["adb_device_id"])
    return CreateComponentFromXML(CambrionixAccess, config)

  def testSettings(self):
    adb = ADB(CONFIG["adb_device_id"])
    access = self.createAccess()

    self.assertRaises(Exception, adb.WaitForDevice)
    with access:
      adb.WaitForDevice()
    self.assertRaises(Exception, adb.WaitForDevice)

  def testWithNavigator(self):
    access = self.createAccess()
    navigator = createNativeADBNavigator()

    with access:
      navigator.SetUp()
      navigator.Open()
      CONFIG.AskUserAccept("Verify the subject has been opened.")
      navigator.Close()
    CONFIG.AskUserAccept("Verify the subject is turned off.")
