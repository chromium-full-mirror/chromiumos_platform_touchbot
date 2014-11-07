# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import traceback

class DUTException(Exception):
  """Exceptions in handling a device under test.

  Usually these Exceptions can be recovered from by resetting the App or DUT.
  """
  def __init__(self, dut, error):
    Exception.__init__(self)
    self.dut = dut
    self.error = error

  def __str__(self):
    return str(self.dut) + ": " + str(self.error)
