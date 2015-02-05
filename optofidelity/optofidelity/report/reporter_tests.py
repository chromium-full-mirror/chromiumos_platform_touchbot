# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import numpy as np
import matplotlib
# Force matplotlib to not use any Xwindows backend.
matplotlib.use('Agg')
from reporter import Figure

class FigureTests(unittest.TestCase):
  def test_single_layout_scalability(self):
    for width in range(128, 1280, 128):
      image_path = "single_layout_%d.png" % width
      figure = Figure(width, 256)
      axes = figure.CreateSingleAxes("X Label", "Y Label")
      axes.plot(np.linspace(0, 100))
      figure.Save(image_path)
      print "Please validate", image_path, "manually."

  def test_secondary_axes_layout(self):
    for width in range(128, 1280, 128):
      image_path = "secondary_layout_%d.png" % width
      figure = Figure(width, 256)
      prim_axes, second_axes = figure.CreatePrimarySecondaryAxes(
          "X Label", "Primary Label", "Secondary Label")

      prim_axes.plot(np.linspace(0, 100))
      second_axes.plot(np.linspace(0, 100))
      figure.Save(image_path)
      print "Please validate", image_path, "manually."


if __name__ == "__main__":
  unittest.main()