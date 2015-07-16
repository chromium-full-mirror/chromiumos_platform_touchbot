# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cPickle as pickle
import os.path as path

_data_dir = path.dirname(path.realpath(__file__))

def Path(filename):
  return path.join(_data_dir, filename)

def LoadPickle(filename):
  with open(Path(filename), "rb") as file_obj:
    return pickle.load(file_obj)
LoadTrace = LoadPickle