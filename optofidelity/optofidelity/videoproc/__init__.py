# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos."""

# Register contract shorthands for numpy array based images
from contracts import new_contract
new_contract('image', 'array[HxW](float),H>0,W>0')
new_contract('binary_image', 'array[HxW](bool),H>0,W>0')

from optofidelity.videoproc.filter import Filter
from optofidelity.videoproc.io import FileVideoReader, VideoReader, VideoWriter
from optofidelity.videoproc.shape import Shape
from optofidelity.videoproc.util import VideoException, Viewer, Canvas