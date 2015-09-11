# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from unittest import SkipTest
import sys

from optofidelity.system.backend_tnt import TnTRobotBackend
from optofidelity.system.fake import FakeDUTBackend


class TestConfig(dict):
  """Special dictionary for test configuration values.

  This dictionary will raise SkipTest exceptions if a value is set to None.
  It will also treat any value that is set to None as non-existant.
  """
  def __getitem__(self, key):
    value = super(TestConfig, self).__getitem__(key)
    if value is None:
      raise SkipTest("Specify '%s' to run test." % key)
    return value

  def __contains__(self, key):
    if super(TestConfig, self).__contains__(key):
      return self.get(key) is not None
    return False

  def get(self, key, default=None):
    value = super(TestConfig, self).get(key)
    return value if value is not None else default

  def Require(self, key):
    self.__getitem__(key)

  def AskUserAccept(self, message):
    print message
    print "Accept test case? [Y,n]"
    if self.get("user_interaction"):
      response = sys.stdin.readline().strip()
      if response in ("n", "N"):
        raise AssertionError("User did not accept test result")

CONFIG = TestConfig(
  adb_device_id = None,
  robot_ip = None,
  phantom_ip = None,
  dut_name = None,
  spreadsheet_key = None,
  oauth_key_file = None,
  chromeperf_endpoint = None,
  gs_folder_url = None,
  android_sdk_path = None,

  cambrionix_serial_device = None,
  cambrionix_dut_port_id = None,
  user_interaction = None,
)

def CreateTestDUTBackend():
  if "robot_ip" not in CONFIG or "dut_name" not in CONFIG:
    print "Running tests on fake robot backend."
    return FakeDUTBackend("fake")
  else:
    robot = TnTRobotBackend(CONFIG["robot_ip"])
    return robot.GetDUTBackend(CONFIG["dut_name"])
