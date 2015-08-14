# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from optofidelity.system.fake import FakeDUTBackend
from optofidelity.system.backend_tnt import TnTRobotBackend

TEST_ADB_DEVICE_ID = None
TEST_ROBOT_IP = None
TEST_PHANTOM_IP = None
TEST_DUT_NAME = None

TEST_SPREADSHEET_KEY = None
TEST_OAUTH_KEY_FILE = None
TEST_CHROMEPERF_ENDPOINT = None

ALLOW_USER_INTERACTION = False

def CreateTestDUTBackend():
  if TEST_ROBOT_IP is None or TEST_DUT_NAME is None:
    print "Running tests on fake robot backend."
    return FakeDUTBackend("fake")
  else:
    robot = TnTRobotBackend(TEST_ROBOT_IP)
    return robot.GetDUTBackend(TEST_DUT_NAME)