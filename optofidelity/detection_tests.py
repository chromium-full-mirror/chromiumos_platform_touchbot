# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
    screen = Screen()
    screen.DetectScreen(flash_video.Frames(step=10), debug=True)


class TestsWithScreenDetection(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    flash_video = FileVideoReader("screen.avi")
    def MirrorFrames(step):
      for i, frame in flash_video.Frames(step=step):
        yield i, np.fliplr(frame)

    screen = Screen()
    screen.DetectScreen(flash_video.Frames(step=10))
    cls.screen_shape = screen.shape

    flash_video.Seek(0)
    mirrored_screen = Screen()
    mirrored_screen.DetectScreen(MirrorFrames(step=10))
    cls.mirrored_screen_shape = mirrored_screen.shape

  @unittest.skip("")
  def test_screen_draw_detection(self):
    screen = Screen(self.screen_shape)

    video = FileVideoReader("tap.avi")
    for i, im in video.Frames():
      frame = Frame(im, screen.shape)
      screen.Update(frame, debug=True)

      color = "W" if screen.color else "B"
      draw = "END DRAW" if screen.draw_ended else ""
      print color, draw

      key = Viewer.VideoFrame(frame.cropped)
      if screen.draw_ended or key == ord('p'):
        video.EnterInteractive()

  @unittest.skip("")
  def test_line_target_detection(self):
    screen = Screen(self.screen_shape)

    video = FileVideoReader("line.avi")
    frame = Frame(video.FrameAt(-1), screen.shape)

    line = Line()
    line.DetectTargetLine(frame, debug=True)

  @unittest.skip("")
  def test_mirrored_line_draw_detection(self):
    video = FileVideoReader("line.avi")

    screen = Screen(self.mirrored_screen_shape)

    im = np.fliplr(video.FrameAt(-1))
    frame = Frame(im, screen.shape)

    line = Line()
    line.DetectTargetLine(frame)

    video.Seek(130)
    for i, im in video.Frames():
      print i
      frame = Frame(np.fliplr(im), screen.shape)
      line.Update(frame, debug=True)

      if line.draw_ended:
        print "END DRAW"

  @unittest.skip("")
  def test_finger_detection(self):
    video = FileVideoReader("line.avi")
    screen = Screen(self.screen_shape)
    frame = Frame(video.FrameAt(-1), screen.shape)

    line = Line()
    line.DetectTargetLine(frame)
    finger = Finger(line)

    video.Seek(150)
    for i, im in video.Frames():
      print i
      frame = Frame(im, screen.shape)
      finger.Update(frame, debug=True)

  @unittest.skip("")
  def test_all_detections(self):
    video = FileVideoReader("line.avi")

    screen = Screen(self.screen_shape)
    frame = Frame(video.FrameAt(-1), screen.shape)

    line = Line()
    line.DetectTargetLine(frame)
    finger = Finger(line)

    video.Seek(150)
    for i, im in video.Frames():
      frame = Frame(im, screen.shape)

      screen.Update(frame)
      line.Update(frame)
      finger.Update(frame)

      out = Canvas(frame.original, frame.crop_shape)
      out.DrawContour([0, 1, 0], line.line_shape)
      out.DrawContour([1, 1, 0], line.target_shape)
      out.DrawContour([0, 0, 1], finger.finger_shape)
      out.DrawContour([1, 0, 0], screen.shape, no_crop=True)
      out.DrawLine([0, 1, 0], x=line.location)
      out.DrawLine([0, 0, 1], x=finger.location)

      Viewer.VideoFrame(out.image)

  @unittest.skip("")
  def test_line_draw_fine_tuning(self):
    video = FileVideoReader("line.avi")

    screen = Screen(self.screen_shape)
    frame = Frame(video.FrameAt(-1), screen.shape)

    line = Line()
    line.DetectTargetLine(frame)

    video.Seek(150)
    for i, im in video.Frames():
      print i
      frame = Frame(im, screen.shape)

      line.Update(frame)

      out = Canvas(frame.cropped)
      out.DrawContour([0, 1, 0], line.line_shape)
      out.DrawContour([1, 1, 0], line.target_shape)
      out.DrawLine([0, 1, 0], x=line.location)

      key = Viewer.VideoFrame(out.image)

      if line.draw_ended or key == ord('p'):
        video.EnterInteractive()


if __name__ == '__main__':
    unittest.main()