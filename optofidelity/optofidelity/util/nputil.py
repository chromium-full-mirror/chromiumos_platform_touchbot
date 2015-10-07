# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Numerical python utilities.

Numpy offers a lot, but not everything we need. This module includes a couple
of algorithms for working with 1 dimensional arrays.
"""

import numpy as np
import scipy.signal as signal
from matplotlib import pyplot

def FindZeroCrossings(array):
  """Returns indices of zero crossings.

  The returned indices point to the number AFTER the zero crossing.

  :param np.ndarray array: 1 dimensional array of floating point values.
  """
  pos = array > 0
  npos = ~pos
  return ((pos[:-1] & npos[1:]) | (npos[:-1] & pos[1:])).nonzero()[0] + 1


def NonNan(array):
  return array[~np.isnan(array)]


def MinMaxRange(array):
  nonnan = NonNan(array)
  if not len(nonnan):
    return 0
  return np.max(NonNan(array)) - np.min(NonNan(array))


def FindLocalExtremes(array):
  """Returns local extreme indices of array."""
  deriv1 = np.diff(array)
  return FindZeroCrossings(deriv1)


def Truncate(array, min=0.0, max=1.0):
  """Truncates number or array to min and max."""
  if isinstance(array, np.ndarray):
    array[array < min] = min
    array[array > max] = max
    return array
  else:
    if array < min:
      return min
    if array > max:
      return max
    return array


def Normalize(array):
  """Normalize array to 0..1"""
  min = np.min(NonNan(array))
  max = np.max(NonNan(array))
  if np.allclose(min, max):
    return array
  return (array - min) / (max - min)


def NormalizeStates(array, crossing_threshold=0.5):
  """Normalize array to 0..1"""
  pre_norm = Normalize(array)
  min = np.median(pre_norm[pre_norm < crossing_threshold])
  max = np.median(pre_norm[pre_norm > crossing_threshold])
  return (pre_norm - min) / (max - min)


def HysteresisThreshold(array, t_low, t_high, initial=False):
  """Hysteresis thresholding of array."""
  result = np.empty(array.shape, dtype=np.bool)
  current = initial
  for index, value in enumerate(array):
    if value > t_high:
      current = True
    elif value < t_low:
      current = False
    result[index] = current
  return result


def LowPass(array, kernel_size=5):
  """Returns low pass filtered array."""
  kernel = np.ones(kernel_size,) / kernel_size
  array = np.pad(array, (kernel_size / 2, kernel_size / 2), "edge")
  return signal.convolve(array, kernel, "valid")


def BoxFilter(array, box_size):
  filtered = np.zeros(array.shape)
  current = np.nan
  for i in range(len(array)):
    if np.isnan(array[i]):
      current = np.nan
    elif np.isnan(current) or np.abs(array[i] - current) > box_size:
      current = array[i]
    filtered[i] = current
  return filtered


def DeDuplicate(items, min_distance):
  if not len(items):
    return
  for i in range(len(items) - 1):
    if items[i+1] - items[i] > min_distance:
      yield items[i]
  yield items[len(items) - 1]


def Segment(binary_array):
  """Returns list of start, end indicies of connected True values."""
  if np.all(~binary_array):
    return

  delta_array = np.diff(binary_array.astype(np.int))
  start = 0
  for i, delta in enumerate(delta_array):
    if delta > 0:
      start = i + 1
    elif delta < 0:
      yield (start, i)
      start = 0
  if start > 0:
    yield (start, len(binary_array)-1)



def EstimateShift(static, shifting, technique, max_shift=None, debug=False):
  """Estimates shift between two arrays.

  :param np.ndarray static: Array that stays stationary.
  :param np.ndarray shifting: Array that is supposed to be shifted to match
         the static array.
  :param str technique: Describes which error measure to use.
         - mae: Mean absolute error
         - mse: Mean square error
  :param Optional[int] max_shift: Maximum shift allowed.
  :param bool debug: Show matplotlib debug window after calculation
  """
  if max_shift is None:
    max_shift = len(shifting)

  if technique == "mae":
    metric = lambda deltas: np.mean(np.abs(deltas))
  elif technique == "mse":
    metric = lambda deltas: np.mean(deltas ** 2)
  else:
    raise ValueError("Unknown technique=%s" % technique)

  errors = []
  for shift in range(max_shift):
    shifted = AlignArrays(static, shifting, shift, mode="wrap")
    delta = shifted - static
    errors.append(metric(delta[~np.isnan(delta)]))

  shift = np.argmin(errors)
  if debug:
    pyplot.figure()

    shifted = AlignArrays(static, shifting, shift, mode="wrap")
    pyplot.subplot(2, 1, 0)
    pyplot.plot(static)
    pyplot.plot(shifted)
    pyplot.plot(static - shifted)

    pyplot.subplot(2, 1, 1)
    pyplot.plot(errors)
    pyplot.show()
  return shift


def Shift(array, shift, mode="edge"):
  """Shift array left or right without wrap-around.

  :param str mode: How to deal with empty space in shifted array
         - edge: Fill empty space with value of array at the edge
         - wrap: Wrap around array when shifting
  """
  if mode == "edge":
    if shift > 0:
      return np.pad(array, (shift, 0), mode="edge")[:-shift]
    else:
      shift = -shift
      return np.pad(array, (0, shift), mode="edge")[shift:]
  elif mode == "wrap":
    return np.roll(array, shift)
  else:
    raise ValueError("No such mode: %s" % mode)


def AlignArrays(target, array, shift, mode="edge"):
  """Aligns two arrays by shifting one and trimming it to the same size"""
  shifted = np.copy(Shift(array, shift, mode))
  shifted.resize((len(target)))
  return shifted


def FindSettlingIndex(profile, start, window_size=8,
                      min_value=None, max_value=None, max_mid_range=None,
                      max_slope=None, max_distance=None, max_mean_distance=None,
                      max_rel_mean_distance=None, combination="and",
                      debug=False):
  """Returns index of first settled value."""
  smoothed = LowPass(profile, 5)
  increasing = smoothed[start] < smoothed[start + 1]

  for i in range(start, len(profile) - 1):
    debug_values = []
    conditions = []
    def AddCondition(threshold, value, name, condition):
      if threshold is None:
        return
      if debug:
        debug_values.append(u"%s=%.2f%s" % (name, value, u"\u2713" if condition else ""))
      conditions.append(condition)
    def MinCondition(threshold, value, name):
      AddCondition(threshold, value, name, value > threshold)
    def MaxCondition(threshold, value, name):
      AddCondition(threshold, value, name, value < threshold)

    value = profile[i]
    window_end = Truncate(i + window_size, 0, len(profile))
    moving_window = profile[i:(window_end + 1)]
    window_mean = np.mean(moving_window[1:])
    window_std = np.std(moving_window[1:])
    mean_distance = window_mean - value
    if not increasing:
      mean_distance *= -1;

    MinCondition(min_value, value, "v")
    MaxCondition(max_value, value, "v")
    MaxCondition(max_slope, np.abs(profile[i + 1] - profile[i]), "s")
    MaxCondition(max_mid_range, np.max(moving_window) - np.min(moving_window), "mr")
    MaxCondition(max_mean_distance, mean_distance, "md")
    MaxCondition(max_rel_mean_distance, mean_distance / window_std, "rmd")

    if debug:
      separator = u" %s " % combination
      print "%03d: d=%d" % (i, (i - start)), separator.join(debug_values)

    if max_distance is not None and (i - start) > max_distance:
      return None

    if combination == "and":
      if np.all(conditions):
        return i
    elif combination == "or":
      if np.any(conditions):
        return i
    else:
      raise ValueError("Combination has to be one of: (and, or)")

  return len(profile) - 1


def FindSettlingIndexReverse(profile, start, debug=False, **kwargs):
  rprofile = profile[::-1]
  rstart = len(profile) - start - 1
  if debug:
    print "Reverse %d->%d" % (start, rstart)
  rindex = FindSettlingIndex(rprofile, rstart, debug=debug, **kwargs)
  return len(profile) - rindex - 1

def FindStateChanges(array, low_thresholds, high_thresholds,
                     crossing_threshold=0.5, debug=False):
  """Returns tuples of indices to the start and end of state changes.

  The input array is expected to be an array between 0..1. A state change
  is a change of values from 0 to 1. The change can happen over multiple values,
  and this method will return the indices of the start and end of this change.
  The start index points to the first value that breaks away from the original
  state, and the end index points to the first value that is considered to be
  settled into the new state.
  """
  # Find indices when the array is crossing the threshold, then find the start
  # and end for each crossing.
  crossings = FindZeroCrossings(LowPass(array, 5) - crossing_threshold)

  for crossing in crossings:
    prev = array[max(crossing - 5, 0)]
    if array[crossing] - prev > 0:
      start = FindSettlingIndexReverse(array, crossing, debug=debug,
                                       **low_thresholds)
      end = FindSettlingIndex(array, crossing, debug=debug, **high_thresholds)
    else:
      start = FindSettlingIndexReverse(array, crossing, debug=debug,
                                       **high_thresholds)
      end = FindSettlingIndex(array, crossing, debug=debug, **low_thresholds)
    if start is not None and end is not None:
      yield (start, end)


def FindPeaks(array, crossing_threshold=0.5, **kwargs):
  for segment_start, segment_end in Segment(array > crossing_threshold):
    start = FindSettlingIndexReverse(array, segment_start, **kwargs)
    end = FindSettlingIndex(array, segment_end, **kwargs)
    if start is not None and end is not None:
      yield (start, end)
