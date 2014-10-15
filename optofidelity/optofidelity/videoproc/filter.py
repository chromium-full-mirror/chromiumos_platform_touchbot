# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Filtering algorithms for image analysis and segmentation."""
from contracts import contract
import numpy as np
import skimage
import skimage.exposure as exposure
import skimage.filter
import skimage.filter.rank as rank_filter
import skimage.morphology as morphology
import skimage.transform as transform


class Filter(object):
  """A collection of commonly used image processing filters."""

  epsilon = 1e-5
  """Everything below epsilon is considered to zero."""

  stable_extreme_number_of_elements = 50
  """Number of maximum elements to pick for stable min/maximum."""

  @staticmethod
  @contract(image="image")
  def StableMax(image):
    """Return the noise-immune maximum value of the image."""
    k = Filter.stable_extreme_number_of_elements
    k_max = np.sort(image.flat)[-k:]
    return np.mean(k_max)

  @staticmethod
  @contract(image="image")
  def StableMin(image):
    """Return the noise-immune minimum value of the image."""
    k = Filter.stable_extreme_number_of_elements
    k_min = np.sort(image.flat)[:k]
    return np.mean(k_min)

  @staticmethod
  @contract(image="image")
  def StableMidRange(image):
    """Return the noise-immune min-range of the image."""
    return (Filter.StableMax(image) + Filter.StableMin(image)) / 2

  @staticmethod
  @contract(image="image", min_val="number", max_val="number")
  def Truncate(image, min_val=0.0, max_val=1.0):
    """Truncate values below 0 or above 1."""
    image = np.copy(image)
    image[image < min_val] = 0.0
    image[image > max_val] = 1.0
    return image

  @staticmethod
  @contract(image="image")
  def Equalize(image):
    """Rescale grayscale to range from 0 to 1."""
    return exposure.rescale_intensity(image)

  @staticmethod
  @contract(image="image", returns="binary_image")
  def OtsuSegmentation(image):
    """Return a binary imageage segmented using the Otsu threshold algorithm."""
    t_otsu = skimage.filter.threshold_otsu(image)
    return image > t_otsu

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
  @contract(image="image", disk_size="int,>0", scale="int,>0")
  def _ScaledRankOrderFilter(filter_fn, image, disk_size, scale=1):
    work_image = transform.rescale(image, (scale, scale))
    # transform.rescale always returns a float64 image, however rank order
    # filter functions such as rank_filter.median need a uint8 image.
    work_image = (work_image * 255).astype(np.uint8)
    work_image = filter_fn(work_image, morphology.disk(disk_size))
    work_image = transform.resize(work_image, image.shape)
    return work_image

  @staticmethod
  @contract(image="image", disk_size="int,>0", scale="int,>0")
  def Reflectance(image, disk_size, scale=1):
    """Return the reflectance part of the image.

    An image A can be described as a multiplication of illuminance I
    and reflectance R: A = I * R. We estimate the illuminance part with
    a strong median rank order filter, then calculate the reflectance.
    """
    illuminance = Filter.Median(image, disk_size, scale)
    illuminance[illuminance < Filter.epsilon] = Filter.epsilon
    reflectance = image / illuminance
    return Filter.Truncate(reflectance)

  @staticmethod
  @contract(image="image", disk_size="int,>0", scale="int,>0")
  def ExtractBlackOnWhite(image, disk_size, scale=1):
    lowpass = Filter.Median(image, disk_size, scale)
    highpass = 1.0 - (lowpass - image)
    return Filter.Truncate(highpass)

  @staticmethod
  @contract(image="array[NxM](float), N>0, M>0",
            high_ref="array[M](float)|None", low_ref="array[M](float)|None",
            returns="array[M](float)")
  def ExtractProfile(image, high_ref=None, low_ref=None):
    profile = np.sum(image, 0)

    if high_ref is not None:
      if low_ref is not None:
        profile = profile - low_ref
        high_ref = high_ref - low_ref
      normalized = np.zeros(profile.shape)
      non_zero = [high_ref > Filter.epsilon]
      normalized[non_zero] = (profile[non_zero] / high_ref[non_zero])

      profile = np.clip(normalized, 0, 1)
    return profile
