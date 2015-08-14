# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Filtering algorithms for image analysis and segmentation."""
from safetynet import TypecheckMeta, typecheck
import bottleneck
import numpy as np
import skimage.filters.rank as rank_filter
import skimage.morphology as morphology
import skimage.transform as transform

from .types import GrayscaleImage

class Filter(object):
  """A collection of commonly used image processing filters."""

  epsilon = 1e-5
  """Everything below epsilon is considered to zero."""

  stable_extreme_number_of_elements = 50
  """Number of maximum elements to pick for stable min/maximum."""

  @staticmethod
  @typecheck
  def StableMax(image):
    """Calculates noise-immune maximum value of an image.

    :type image: GrayscaleImage
    :rtype: float
    """
    k = Filter.stable_extreme_number_of_elements
    temp = bottleneck.partsort(image.flat, image.size-k)
    k_max = temp[-k:]
    return np.mean(k_max)

  @staticmethod
  @typecheck
  def StableMin(image):
    """Calculates noise-immune minimum value of an image.

    :type image: GrayscaleImage
    :rtype: float
    """
    k = Filter.stable_extreme_number_of_elements
    temp = bottleneck.partsort(image.flat, k)
    k_min = temp[:k]
    return np.mean(k_min)

  @staticmethod
  @typecheck
  def StableMidRange(image):
    """Calculates noise-immune mid range value of an image.

    :type image: GrayscaleImage
    :rtype: float
    """
    return (Filter.StableMax(image) + Filter.StableMin(image)) / 2

  @staticmethod
  @typecheck
  def Truncate(image, min_val=0.0, max_val=1.0):
    """Truncate image values to 0..1 or custom range.

    :type image: GrayscaleImage
    :type min_val: float
    :type max_val: float
    :rtype: GrayscaleImage
    """
    image = np.copy(image)
    image[image < min_val] = 0.0
    image[image > max_val] = 1.0
    return image
