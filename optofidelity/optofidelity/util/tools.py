# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities.

This module provides globally available python utilities.
"""
from contextlib import contextmanager
from StringIO import StringIO
import fcntl
import logging
import os
import sys
import tempfile
import threading
import time
import traceback


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

class LogCapture(object):
  def __init__(self, stream=None, level=logging.DEBUG):
    self._log_stream = stream or StringIO()
    self._level = level

    self._log_handler = logging.StreamHandler(self._log_stream)
    formatter = logging.Formatter("%(levelname)s:%(name)s: %(message)s")
    self._log_handler.setFormatter(formatter)

  def __enter__(self):
    root = logging.getLogger("optofidelity")
    root.addHandler(self._log_handler)

  def __exit__(self, type_, value, tb):
    root = logging.getLogger("optofidelity")
    if type_:
      root.error("Exception", exc_info=(type_, value, tb))
    root.removeHandler(self._log_handler)

  @property
  def log(self):
    return self._log_stream.getvalue()

class ProgressPrinter(object):
  def __init__(self, log):
    self._log = log

  def Exception(self, header, message="Caught Exception"):
    self.Error(header, message)
    traceback.print_exc(limit=1)
    self._log.exception(message)

  def Info(self, header, message):
    self.Print(header, message, logging.INFO)

  def Error(self, header, message):
    self.Print(header, message, logging.ERROR)

  def Print(self, header, message, level):
    color = "32"
    if level == logging.ERROR:
      color = "31"

    pretty_format = "\033[1m\033[0;%sm%s:\033[0m \033[1m%s\033[0m"
    log_line = pretty_format % (color, header, message)
    self._log.log(level, log_line)
    print log_line

@contextmanager
def SingleInstanceLock(lock_name):
  lockfile = os.path.join(tempfile.gettempdir(), "%s.lock" % lock_name)
  # race condition exists here, but is highly improbable in our use case.
  if os.path.exists(lockfile):
    raise Exception("Another instance is already running. If that is not " +
                    "the case, delete: %s" % lockfile)
  open(lockfile, 'w').close()
  try:
    yield
  finally:
    os.unlink(lockfile)
