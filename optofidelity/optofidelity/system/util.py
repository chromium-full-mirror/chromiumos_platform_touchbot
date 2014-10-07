# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
  for i in range(max_attempts):
    try:
      print "%s (Attempt %d)" % (title, i+1)
      function()
      return
    except DUTException as e:
      print "%s: FAILED" % title
      print "%s: Exception: %s" % (title, e)
      print "%s: Trying to recover." % title
      recover_function()
