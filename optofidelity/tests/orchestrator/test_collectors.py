# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the Orchestrator class."""
from unittest import TestCase
import shutil
import tempfile
import os

from optofidelity.orchestrator.collector import SystraceCollector
from optofidelity.util import CreateComponentFromXML
from tests.config import CONFIG


class TestSystraceCollection(TestCase):
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
