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
from videoproc import FileVideoReader, Viewer, Shape


class TestPreProcessing(unittest.TestCase):
  @unittest.skip("")
  def test_pre_process(self):
    video = FileVideoReader("line.avi")
    im = video.FrameAt(30)
    frame = Frame(im, None, None)
    frame.DebugView()

  @unittest.skip("")
  def test_screen_detection(self):
    flash_video = FileVideoReader("screen.avi")
    screen = Screen()
    screen.DetectScreen(flash_video.Frames(step=10), debug=True)
    im = flash_video.FrameAt(30)
    frame = Frame(im, None, screen)
    frame.DebugView()


class TestsWithScreenDetection(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    flash_video = FileVideoReader("videos/N5_flash.avi")
    cls.screen = Screen()
    cls.screen.DetectScreen(flash_video.Frames(step=10))

  def get_screen(self, mirrored=False):
    if mirrored:
      return self.screen.Mirrored()
    else:
      return Screen(self.screen)

  def detect_line(self, video, mirrored=False, debug=False):
    screen = self.get_screen(mirrored)
    line = Line()

    for i, im in video.Frames(start=-1, stop=-100, step=-10):
      if mirrored:
        im = np.fliplr(im)
      frame = Frame(im, None, screen)
      if line.DetectTargetLine(frame, debug=debug):
        print i, "Target line detected"
        break
      else:
        print i, "No target line detected"
    return line

  def iterate_video_test(self, video, frame_function, start=0, mirrored=False):
    screen = self.get_screen(mirrored)
    prev_im = None
    for i, im in video.Frames(start=start):
      print i
      if mirrored:
        im = np.fliplr(im)
      frame = Frame(im, prev_im, screen, i)
      debug_im, pause = frame_function(frame)
      key = Viewer.VideoFrame(debug_im)
      if pause or key == ord('p'):
        video.EnterInteractive()
      prev_im = im

  @unittest.skip("")
  def test_screen_draw_fine_tuning(self):
    video = FileVideoReader("tap.avi")

    screen = self.get_screen()
    def frame_function(frame):
      data = screen.Preprocess(frame)
      events = screen.GenerateEvents(data, frame.index, debug_frame=frame)
      print "events:", events
      return screen.debug_canvas.Scaled(2), events
    self.iterate_video_test(video, frame_function, start=100)

  @unittest.skip("")
  def test_line_target_detection(self):
    video = FileVideoReader("line.avi")
    self.detect_line(video, debug=True)

  @unittest.skip("")
  def test_line_draw_fine_tuning(self):
    mirrored = True
    video = FileVideoReader("videos/line.avi")
    line = self.detect_line(video, mirrored=mirrored)

    def frame_function(frame):
      data = line.Preprocess(frame, debug=True)
      events = line.GenerateEvents(data, frame.index, debug_frame=frame)
      print "events:", events
      return line.debug_canvas.Scaled(4), events
    self.iterate_video_test(video, frame_function, start=80, mirrored=mirrored)

  #@unittest.skip("")
  def test_finger_detection(self):
    video = FileVideoReader("videos/N5_tap.avi")

    finger = Finger(self.get_screen())
    def frame_function(frame):
      data = finger.Preprocess(frame)
      events = finger.GenerateEvents(data, frame.index, debug_frame=frame)
      print "events:", events
      return finger.debug_canvas.image, False
    self.iterate_video_test(video, frame_function, start=170)

if __name__ == '__main__':
    unittest.main()