# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines type check methods that can be used with safetynet."""
import numpy as np


def Image(instance):
  """Returns True if instance is a 2D image."""
  if not isinstance(instance, np.ndarray):
    return False
  if len(instance.shape) < 2 or len(instance.shape) > 3:
    return False
  if len(instance.shape) == 3:
    if instance.shape[2] < 2 or instance.shape[2] > 4:
      return False
  return True


def RGBImage(instance):
  """Returns True if instance is a 2D RGB image."""
  if not Image(instance):
    return False
  shape = instance.shape
  return (len(shape) == 3 and shape[2] == 3 and instance.dtype == np.float)


def RGBAImage(instance):
  """Returns True if instance is a 2D RGBA image."""
  if not Image(instance):
    return False
  shape = instance.shape
  return (len(shape) == 3 and shape[2] == 4 and instance.dtype == np.float)


def GrayscaleImage(instance):
  """Returns True if instance is a 2D grayscale float image."""
  if not Image(instance):
    return False
  shape = instance.shape
  return (len(shape) == 2 and instance.dtype == np.float)


def BinaryImage(instance):
  """Returns True if instance is a 2D binary image."""
  if not Image(instance):
    return False
  shape = instance.shape
  return (len(shape) == 2 and instance.dtype == np.bool)
