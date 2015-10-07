# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase
import os
import shutil
import tempfile

from optofidelity.orchestrator.collector import (ChromeProfileCollector,
                                                 SystraceCollector)
from optofidelity.util import CreateComponentFromXML
from tests.config import CONFIG


class TestSystraceCollector(TestCase):
  def setUp(self):
    self.tempdir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testCollection(self):
    adb_device = CONFIG["adb_device_id"]
    sdk_path = CONFIG["android_sdk_path"]
    config = "<collector adb='{adb}' sdk-path='{sdk_path}' />".format(
        adb=adb_device, sdk_path=sdk_path)

    collector = CreateComponentFromXML(SystraceCollector, config)
    collector.Start(1000)
    collector.Stop()
    collector.Save(self.tempdir)

    filename = os.path.join(self.tempdir, "systrace.html")
    self.assertTrue(os.path.exists(filename))

    CONFIG.AskUserAccept("Verify file://" + filename)


class TestChromeProfileCollector(TestCase):
  def setUp(self):
    self.tempdir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.tempdir)

  def testCollection(self):
    adb_device = CONFIG["adb_device_id"]
    chromium_path = CONFIG["chromium_path"]
    config_str = ("<collector adb='{adb}' chromium-path='{chromium_path}' " +
                  "browser='stable' />")
    config = config_str.format(adb=adb_device, chromium_path=chromium_path)

    collector = CreateComponentFromXML(ChromeProfileCollector, config)
    collector.Start(1000)
    collector.Stop()
    collector.Save(self.tempdir)

    filename = os.path.join(self.tempdir, "chrome_profile.html")
    self.assertTrue(os.path.exists(filename))

    CONFIG.AskUserAccept("Verify file://" + filename)
