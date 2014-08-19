# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Test cases for testing detection features.

These are manual tests that require a screen.avi and line.avi file to work.
Per default all tests are skipped, it is up to the developer to pick which
test to run and manually validate the results.
"""
import numpy as np
import unittest

from detection import Frame, Screen, Line, Finger
from videoproc import FileVideoReader, Viewer, Shape, Canvas


class TestPreProcessing(unittest.TestCase):
  @unittest.skip("")
  def test_pre_process(self):
    video = FileVideoReader("line.avi")
    im = video.FrameAt(30)
    frame = Frame(im)
    frame.DebugView()

  @unittest.skip("")
  def test_pre_process_masking(self):
    video = FileVideoReader("line.avi")
    im = video.FrameAt(30)
    mask = np.zeros(im.shape).astype(np.bool)
    mask[200:500, 200:500] = 1

    frame = Frame(im, Shape(mask))
    frame.DebugView()

  @unittest.skip("")
  def test_screen_detection(self):
    flash_video = FileVideoReader("screen.avi")
    Screen(flash_video.Frames(step=10), debug=True)


class TestsWithScreenDetection(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    flash_video = FileVideoReader("screen.avi")

    screen = Screen(flash_video.Frames(step=10))
    cls.screen_shape = screen.shape
    cls.mirrored_screen_shape = Shape(np.fliplr(cls.screen_shape.mask))

  def get_screen(self, mirrored=False):
    if mirrored:
      return Screen(shape=self.mirrored_screen_shape)
    else:
      return Screen(shape=self.screen_shape)

  def iterate_video_test(self, video, frame_function, start=0, mirrored=False):
    screen = self.get_screen(mirrored)
    for i, im in video.Frames(start=start):
      print i
      if mirrored:
        im = np.fliplr(im)
      frame = Frame(im, screen.shape, i)
      debug_im, pause = frame_function(frame)
      key = Viewer.VideoFrame(debug_im)
      if pause or key == ord('p'):
        video.EnterInteractive()

  @unittest.skip("")
  def test_screen_draw_fine_tuning(self):
    video = FileVideoReader("screen.avi")

    screen = self.get_screen()
    def frame_function(frame):
      data = screen.Preprocess(frame)
      events = screen.GenerateEvents(data, frame.index, debug_frame=frame)
      print "events:", events
      return frame.cropped, events
    self.iterate_video_test(video, frame_function)

  @unittest.skip("")
  def test_line_target_detection(self):
    screen = Screen(shape=self.screen_shape)

    video = FileVideoReader("line.avi")
    frame = Frame(video.FrameAt(-1), screen.shape)

    Line(frame, debug=True)

  @unittest.skip("")
  def test_line_draw_fine_tuning(self):
    mirrored = True
    video = FileVideoReader("line.avi")
    screen = self.get_screen(mirrored)

    im = video.FrameAt(-1)
    end_frame = Frame(np.fliplr(im) if mirrored else im, screen.shape)
    line = Line(end_frame)

    def frame_function(frame):
      data = line.Preprocess(frame, debug=True)
      events = line.GenerateEvents(data, frame.index, debug_frame=frame)
      print "events:", events
      return line.debug_canvas.Scaled(4), events
    self.iterate_video_test(video, frame_function, start=80, mirrored=mirrored)

  @unittest.skip("")
  def test_finger_detection(self):
    video = FileVideoReader("line.avi")

    finger = Finger()
    def frame_function(frame):
      data = finger.Preprocess(frame, debug=True)
      finger.GenerateEvents(data, frame.index, debug_frame=frame)
      return finger.debug_canvas.Scaled(4), False
    self.iterate_video_test(video, frame_function)

if __name__ == '__main__':
    unittest.main()