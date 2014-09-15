# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Test cases for testing video processing features.

These are manual tests that require a screen.avi file to work.
Per default all tests are skipped, it is up to the developer to pick which
test to run and manually validate the results.
"""
import numpy as np
import unittest

from videoproc import FileVideoReader, Viewer, Filter, Shape

class TestVideoProc(unittest.TestCase):

  def setUp(self):
    self.video = FileVideoReader("screen.avi")

  @unittest.skip("")
  def test_video_display(self):
    print "Displaying video"
    for i, frame in self.video.Frames():
      print "frame", i
      Viewer.VideoFrame(frame)

  @unittest.skip("")
  def test_video_display_with_skip(self):
    print "Displaying video with frameskip=10"
    for i, frame in self.video.Frames(step=10):
      print "frame", i
      Viewer.VideoFrame(frame)

  @unittest.skip("")
  def test_filters(self):
    im = self.video.FrameAt(20)
    Viewer.DebugView(
        "gray",
        original=im,
        truncate=Filter.Truncate(im, 0.1, 0.2),
        reflectance=Filter.Reflectance(im, 50, 1.0),
        median=Filter.Median(im, 5, 0.5),
        min=Filter.Min(im, 5, 0.5),
        max=Filter.Max(im, 5, 0.5)
    )

  @unittest.skip("")
  def test_shape_masks(self):
    im = self.video.FrameAt(20)
    rect = np.zeros(im.shape).astype(np.bool)
    rect[200:500, 200:500] = 1

    shape = Shape(rect)
    Viewer.DebugView(
        "gray",
        mask=shape.mask,
        with_margin=shape.WithMargin(100, -100).mask,
        contour=shape.contour
    )
    print shape.top, shape.left, shape.bottom, shape.right


  @unittest.skip("")
  def test_object_edges(self):
    im = self.video.FrameAt(20)
    rect = np.zeros(im.shape).astype(np.bool)
    rect[200:500, 200:500] = 1

    shape = Shape(rect)
    Viewer.DebugView(
        "gray",
        mask=shape.mask,
        contour=shape.contour,
        horizontal_edge=shape.horizontal_edges,
        vertical_edges=shape.vertical_edges
    )

  #@unittest.skip("")
  def test_video_playback_control(self):
    for i, frame in self.video.Frames():
      print "frame", i
      key = Viewer.VideoFrame(frame)
      if key == ord('p'):
        self.video.EnterInteractive()


if __name__ == '__main__':
    unittest.main()