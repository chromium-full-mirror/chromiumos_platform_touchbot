# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np
from optofidelity.videoproc import Viewer, Filter

class Frame(object):
  """This class stores multiple versions and views of a camera frame.

  This class stores a cropped version of the image, enhances it with noise
  filtering and calculates the reflectance.
  """
  def __init__(self, im, prev_im, screen, index=0):
    self.original = im
    self.rectified = im
    self.index = index
    self.screen = screen

    if screen:
      self.crop_shape = screen.shape
      self.rectified = screen.Rectify(im)

    # noise filtered reflectance
    self.reflectance = Filter.Reflectance(self.rectified, disk_size=40,
                                          scale=0.5)
    self.reflectance = Filter.Median(self.reflectance, disk_size=1)

    if prev_im is not None:
      self.delta = im - prev_im
    else:
      self.delta = np.zeros(im.shape)

  def DebugView(self):
    Viewer.DebugView(original=self.original,
                     rectified=self.rectified,
                     reflectance=self.reflectance)
