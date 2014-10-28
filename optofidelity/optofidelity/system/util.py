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


def RetryFunction(function, recover_function, title, max_attempts=3):
  """Try to runs function() recover from possible DUTExceptions.

  function: The function to execute
  recover_function: A function executed when a DUTException is thrown
  title: For debug prints
  max_attempts: How often to try.
  """
  last_exc = None
  for i in range(max_attempts):
    try:
      print "%s (Attempt %d)" % (title, i+1)
      return function()
    except Exception as e:
      print "%s: FAILED" % title
      traceback.print_exc()
      print "%s: Trying to recover." % title
      if i < max_attempts - 1:
        recover_function()
      else:
        raise e
