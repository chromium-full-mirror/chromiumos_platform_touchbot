# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.import os.path as path

import cPickle as pickle
import os.path as path

import skimage.color as color
import skimage.io as io

from optofidelity.videoproc import FileVideoReader

_data_dir = path.dirname(path.realpath(__file__))

def LoadVideo(filename):
  return FileVideoReader(Path(filename), 300)

def Path(filename):
  return path.join(_data_dir, filename)

def LoadImage(filename):
  return color.rgb2gray(io.imread(Path(filename)))

def LoadTrace(filename):
  with open(Path(filename), "r") as file_obj:
    return pickle.load(file_obj)

_data_dir = path.dirname(path.realpath(__file__))
