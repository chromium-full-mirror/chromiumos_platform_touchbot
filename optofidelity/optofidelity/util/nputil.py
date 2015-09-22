# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np

def FindZeroCrossings(array):
  """Returns indices of zero crossings.

  The returned indices point to the number AFTER the zero crossing.

  :param np.ndarray array: 1 dimensional array of floating point values.
  """
  pos = array > 0
  npos = ~pos
  return ((pos[:-1] & npos[1:]) | (npos[:-1] & pos[1:])).nonzero()[0] + 1


def FindStateChanges(array, settled_threshold=0.05, lookahead_length=5):
  """Returns tuples of indices to the start and end of state changes.

  The input array is expected to be an array between 0..1. A state change
  is a change of values from 0 to 1. The change can happen over multiple values,
  and this method will return the indices of the start and end of this change.
  The start index points to the first value that breaks away from the original
  state, and the end index points to the first value that is considered to be
  settled into the new state.

  :param np.ndarray array: 1 dimensional array of floating point values.
  :param float settled_threshold: Threshold describing the maximum delta
         between values for them to be considered settled.
  :param int lookahead_length: Before accepting a value as settled the algorithm
         will look ahead by lookahead_length values to see if the state change
         is complete.
  :yields (start, end) pairs of indices
  """
  def FindStateChangeEnd(start, step):
    """Returns index of first settled value."""
    i = start + step
    delta_sign = np.sign(array[start] - array[start - 1])
    while i >= 1 and i < len(array):
      delta = array[i] - array[i - 1]
      # are we settled yet?
      if np.sign(delta) != delta_sign or np.abs(delta) < settled_threshold:
        # Look ahead to see if state change is complete or we are just at a
        # dip before the actual state change is done.
        lookahead_index = i + step * lookahead_length
        if (lookahead_length <= 0 or lookahead_index < 0 or
            lookahead_index >= len(array)):
          return i - step
        lookahead_delta = (array[lookahead_index] - array[i]) * step
        if (np.sign(lookahead_delta) != delta_sign or
            np.abs(lookahead_delta) < settled_threshold):
          return i - step
      i += step
    raise Exception("Cannot find end of state change")

  # Find indices when the array is crossing 0.5, then find the start and end
  # for each crossing.
  crossings = FindZeroCrossings(array - 0.5)
  for crossing in crossings:
    start = FindStateChangeEnd(crossing, -1)
    end = FindStateChangeEnd(crossing, +1)
    yield (start, end)
