# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities.

This module provides globally available python utilities.
"""

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