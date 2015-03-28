# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.import os.path as path

import cPickle as pickle
import os.path as path

import skimage.color as color
import skimage.io as io

from optofidelity.videoproc import FileVideoReader

_data_dir = path.dirname(path.realpath(__file__))

def CalibrationWhiteImage():
  return LoadImage("calibration_white.png")

def CalibrationBlackImage():
  return LoadImage("calibration_black.png")

def CalibrationVideo():
  return FileVideoReader(Path("calibration.avi"), 300)

def TouchMoveVideo():
  return FileVideoReader(Path("touch_move.avi"), 300)

def LineDrawTrace():
  return pickle.load(Path("line_draw_trace.pickle"))

def Path(filename):
  return path.join(_data_dir, filename)

def LoadImage(filename):
  image = io.imread(Path(filename))
  return color.rgb2gray(image)
