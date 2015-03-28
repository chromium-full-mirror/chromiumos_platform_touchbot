# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
import os
import shutil
import sys
import time

import numpy as np
import skimage
import skimage.color

import cv2

from .util import Viewer

CODEC = cv2.cv.CV_FOURCC(*"mp4v")


class PrefetchEnabled(object):
  """Helper object to be used in the with-statement.

  It will enable prefetch on entering the with block and make sure the camera
  is left in a good state upon exiting.
  """
  def __init__(self, reader):
    self.reader = reader

  def __enter__(self):
    self.reader.prefetch_enabled = True

  def __exit__(self, type, value, traceback):
    self.reader.ClearPrefetch()
    self.reader.prefetch_enabled = False


class VideoReader(object):
  """Abstract base class for Video Reader.

  Provides common functionality for accessing videos.
  """
  def __init__(self, num_frames, framerate, perf_enabled=False):
    self.current_frame = -1
    self.interactive = False
    self.num_frames = num_frames
    self.transfer_times = []
    self.perf_enabled = perf_enabled
    self.prefetch_enabled = False
    self.framerate = framerate
    self.frametime = 1.0 / framerate

  @property
  def frame_shape(self):
    frame = self.FrameAt(self.current_frame)
    return frame.shape

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.Close()

  def Close():
    pass

  def PrefetchEnabled(self):
    """Safely enables prefetch in combination with the with statement.

    Use as follows:
      with reader.PrefetchEnabled():
        use reader
    It will automatically clear any outstanding prefetches to leave the reader
    in a good state.
    """
    return PrefetchEnabled(self)

  def _SeekTo(self, frame):
    """Seek to an absolute location in the video.

    This method is for internal use and to be implemented by
    a subclass. Use the more convenient Seek method.
    """
    pass

  def Prefetch(self, frame):
    pass

  def ClearPrefetch(self):
    pass

  def Read(self):
    """Return the current frame image.

    This method is to be implemented by a subclass. The image
    is to be returned as a grayscale float image represented as
    a numpy array.
    """
    pass

  def Seek(self, to=None, forward=None, backward=None):
    """Seek to a location in the video.

    to: seek to an absolute frame number. Can be negative to
        seek to a location from the end of the file.
    forward: seek forward by a number of frames
    backward: seek backward by a number of frames
    """
    if forward:
      to = self.current_frame + forward
    if backward:
      to = self.current_frame - backward
    if to is not None:
      if to < 0:
        to = self.num_frames + to
      if to > self.num_frames or to < 0:
        return False
      return self._SeekTo(to)
    return True

  def FrameAt(self, frame):
    """Return image at a location as a grayscale float image."""
    start = time.time()
    self.Seek(to=frame)
    res = self.Read()
    if self.perf_enabled:
      self.transfer_times.append(time.time() - start)
    return res

  def Next(self):
    """Go to the next frame."""
    return self.Seek(forward=1)

  def Prev(self):
    """Go to the previous frame."""
    return self.Seek(backward=1)

  def EnterInteractive(self):
    """Enable interactive mode in Frames().

    After the interactive mode is enabled, Frames() will stop and wait for
    user input:
      j: go to next frame
      k: go to previous frame
      c: continue playing
    """
    self.interactive = True

  def Frames(self, start=0, stop=None, step=1, frames=None):
    """Yield frames until the video ends.

    This method might block when the interactive mode is used.
    start: first frame to yield.
    stop: last frame to yield.
    step: step size between frames.
    frames: Custom array of frame numbers to yield. Overrides all
            other parameters.
    """
    if not frames:
      if stop is None:
        stop = self.num_frames
      frames = range(start, stop, step)
    i = 0
    while True:
      if i < 0 or i >= len(frames):
        break

      if self.prefetch_enabled and not self.interactive and i + 1 < len(frames):
        self.Prefetch(frames[i + 1])

      frame = self.FrameAt(frames[i])

      yield frames[i], frame

      if self.interactive:
        key = cv2.waitKey() & 0xFF
        if key == ord('k'):
          i -= 1
        elif key == ord('l'):
          i -= 10
        elif key == ord(';'):
          i -= 100
        elif key == ord('j'):
          i += 1
        elif key == ord('h'):
          i += 10
        elif key == ord('g'):
          i += 100
        elif key == ord('c'):
          self.interactive = False
          i += 1
      else:
        i += 1

  def DebugView(self):
    print "Press p to enter interactive mode"
    print "Press c to close"
    for i, frame in self.Frames():
      key = Viewer.VideoFrame(frame)
      if key == ord('p'):
        print "Entering Interactive Mode"
        print "  Press j/k to move by 1 frame"
        print "  Press h/l to move by 10 frames"
        print "  Press c to continue playback"
        self.EnterInteractive()
      if key == ord('c'):
        break

  def Save(self, filename, print_progress):
    width = self.frame_shape[1]
    height = self.frame_shape[0]
    writer = cv2.VideoWriter(filename, CODEC, self.framerate,
                             (width, height))

    for i, frame in self.Frames():
      if print_progress:
        sys.stdout.write("\rWriting frame %d/%d" % (i, self.num_frames))
        sys.stdout.flush()
      frame = skimage.img_as_ubyte(frame)
      frame = skimage.color.gray2rgb(frame)
      writer.write(frame)
    if print_progress:
      print ""
    writer.release()

  def __getstate__(self):
    raise Exception("VideoReader cannot be pickled")


class FileVideoReader(VideoReader):
  """Implementation of a VideoReader for reading from files using OpenCV.

  Note, any operation that seeks backwards in a file will be slow since
  the video has to be re-opened and walked through until the requested
  frame.
  """
  def __init__(self, filename, framerate):
    self.cap = cv2.VideoCapture(filename)
    self.filename = filename
    self.frame_cache = None

    num_frames = int(self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))
    VideoReader.__init__(self, num_frames, framerate)

  @property
  def frame_shape(self):
    width = int(self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH))
    height = int(self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT))
    return (height, width)

  def _SeekTo(self, frame):
    if frame < self.current_frame:
      self.cap.open(self.filename)
      self.current_frame = -1
      frame = frame + 1
    else:
      frame = frame - self.current_frame

    for i in range(frame):
      if not self.cap.grab():
        raise Exception("Cannot grab frame")

    self.current_frame += frame
    self.frame_cache = None
    return True

  def Read(self):
    if self.frame_cache is None:
      # cache current frame in case it's requested again.
      ret, self.frame_cache = self.cap.retrieve()
      if not ret:
        raise Exception("Cannot read frame")
    return skimage.img_as_float(self.frame_cache[:, :, 0])

  def Close(self):
    self.cap.release()

  def Save(self, filename, print_progress):
    if os.path.abspath(self.filename) != os.path.abspath(filename):
      shutil.copyfile(self.filename, filename)

class FakeVideoReader(VideoReader):
  """Fake VideoReader returning nothing but black frames."""
  def __init__(self, num_frames, size, framerate):
    self.size = size
    VideoReader.__init__(self, num_frames, framerate)

  def _SeekTo(self, frame):
    return (frame < self.num_frames and frame >= 0)

  def Read(self):
    return np.zeros(self.size, dtype=np.float)


class VideoWriter(object):
  def __init__(self, filename):
    self.filename = filename
    self.writer = None

  def WriteFrame(self, frame):
    frame = skimage.img_as_ubyte(frame)
    frame = skimage.color.gray2rgb(frame)
    self.writer.write(frame)

  def Initialize(self, frame):
      width = frame.shape[1]
      height = frame.shape[0]
      self.writer = cv2.VideoWriter(self.filename, None, 15, (width, height))

  def Write(self, reader):
    if not self.writer:
      first_frame = reader.FrameAt(0)
      self.Initialize(first_frame)

    for i, frame in reader.Frames():
      sys.stdout.write("\rWriting frame %d/%d" % (i, reader.num_frames))
      sys.stdout.flush()
      self.WriteFrame(frame)
    print ""
