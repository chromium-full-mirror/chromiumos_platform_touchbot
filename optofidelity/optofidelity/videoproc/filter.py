# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Filtering algorithms for image analysis and segmentation."""
import bottleneck
import numpy as np
import skimage.filters.rank as rank_filter
import skimage.morphology as morphology
import skimage.transform as transform


class Filter(object):
  """A collection of commonly used image processing filters."""

  epsilon = 1e-5
  """Everything below epsilon is considered to zero."""

  stable_extreme_number_of_elements = 50
  """Number of maximum elements to pick for stable min/maximum."""

  @staticmethod
  def StableMax(image):
    """Return the noise-immune maximum value of the image."""
    k = Filter.stable_extreme_number_of_elements
    temp = bottleneck.partsort(image.flat, image.size-k)
    k_max = temp[-k:]
    return np.mean(k_max)

  @staticmethod
  def StableMin(image):
    """Return the noise-immune minimum value of the image."""
    k = Filter.stable_extreme_number_of_elements
    temp = bottleneck.partsort(image.flat, k)
    k_min = temp[:k]
    return np.mean(k_min)

  @staticmethod
  def StableMidRange(image):
    """Return the noise-immune min-range of the image."""
    return (Filter.StableMax(image) + Filter.StableMin(image)) / 2

  @staticmethod
  def Truncate(image, min_val=0.0, max_val=1.0):
    """Truncate values below 0 or above 1."""
    image = np.copy(image)
    image[image < min_val] = 0.0
    image[image > max_val] = 1.0
    return image

  @staticmethod
  def Median(image, disk_size, scale=1):
    """Median rank order filter."""
    return Filter._ScaledRankOrderFilter(rank_filter.median, image, disk_size,
                                         scale)

  @staticmethod
  def Min(image, disk_size, scale=1):
    """Minimageum rank order filter."""
    return Filter._ScaledRankOrderFilter(rank_filter.minimum, image, disk_size,
                                         scale)

  @staticmethod
  def Max(image, disk_size, scale=1):
    """Maximageum rank order filter."""
    return Filter._ScaledRankOrderFilter(rank_filter.maximum, image, disk_size,
                                         scale)

  @staticmethod
  def _ScaledRankOrderFilter(filter_fn, image, disk_size, scale=1):
    work_image = transform.rescale(image, (scale, scale))
    # transform.rescale always returns a float64 image, however rank order
    # filter functions such as rank_filter.median need a uint8 image.
    work_image = (work_image * 255).astype(np.uint8)
    work_image = filter_fn(work_image, morphology.disk(disk_size))
    work_image = transform.resize(work_image, image.shape)
    return work_image
