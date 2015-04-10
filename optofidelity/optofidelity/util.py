# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities.

This module provides globally available python utilities.
"""
import threading
import time
import sys


class const_property(object):
  """Variant of the @property decorator that caches values.

  The cache never expires, leading to the name const_property, and can allows
  properties to be used to calculate expensive values only when requested.
  """
  def __init__(self, fget, doc=None):
    self.fget = fget
    self.__doc__ = doc or fget.__doc__
    self.__name__ = fget.__name__
    self.__module__ = fget.__module__

  def __get__(self, inst, owner):
    try:
      value = inst._cache[self.__name__]
    except (KeyError, AttributeError):
      value = self.fget(inst)
      try:
        cache = inst._cache
      except AttributeError:
        cache = inst._cache = {}
      cache[self.__name__] = value
    return value


class ProgressBar(threading.Thread):
  """Command line progress bar helper.

  This class is to be used as a context manager in the with statement:

  >>> with ProgressBar("Message", "End"):
  >>>  time.sleep(10)
  Message..........End

  This will print the message with a dot every seconds on the command line until
  the with block is done.
  """
  def __init__(self, msg, done_msg="Done!", suppress=False):
    """
    :param str msg: Message to print at start.
    :param str done_msg: Message to print at the end.
    :param bool suppress: Suppress all prints.
    """
    super(ProgressBar, self).__init__()
    self.stop = False
    self.msg = msg
    self.done_msg = done_msg
    self.suppress = suppress
    self.daemon = True

  def __enter__(self):
    if not self.suppress:
      self.start()

  def __exit__(self, type, value, tb):
    if not self.suppress:
      self.stop = True
      self.join()

  def run(self):
    sys.stdout.write(self.msg)
    sys.stdout.flush()

    i = 0
    while not self.stop:
      if i > 10:
        sys.stdout.write(".")
        sys.stdout.flush()
        i = 0
      i = i+1
      time.sleep(0.1)
    print " " + self.done_msg
