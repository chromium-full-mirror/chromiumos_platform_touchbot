# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
import cv2
import skimage
import skimage.color
import sys
import time

CODEC = cv2.cv.CV_FOURCC(*"xvid")
if sys.platform == "darwin":
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
  def __init__(self, num_frames, perf_enabled=False):
    self.current_frame = 0
    self.interactive = False
    self.num_frames = num_frames
    self.transfer_times = []
    self.perf_enabled = perf_enabled
    self.prefetch_enabled = False

  @property
  def frame_shape(self):
    frame = self.FrameAt(self.current_frame)
    return frame.shape

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
    self.Seek(to=frame)
    return self.Read()

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

      start = time.time()

      if self.prefetch_enabled and not self.interactive and i + 1 < len(frames):
        self.Prefetch(frames[i + 1])

      frame = self.FrameAt(frames[i])

      if self.perf_enabled:
        self.transfer_times.append(time.time() - start)

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


class FileVideoReader(VideoReader):
  """Implementation of a VideoReader for reading from files using OpenCV.

  Note, any operation that seeks backwards in a file will be slow since
  the video has to be re-opened and walked through until the requested
  frame.
  """
  def __init__(self, filename):
    self.cap = cv2.VideoCapture(filename)
    self.filename = filename
    self.frame_cache = None

    num_frames = int(self.cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))
    VideoReader.__init__(self, num_frames)

  def _SeekTo(self, frame):
    if frame < self.current_frame:
      self.cap.release()
      self.cap = cv2.VideoCapture(self.filename)
      self.current_frame = 0
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
      self.writer = cv2.VideoWriter(self.filename, CODEC, 15, (width, height))

  def Write(self, reader):
    if not self.writer:
      first_frame = reader.FrameAt(0)
      self.Initialize(first_frame)

    for i, frame in reader.Frames():
      sys.stdout.write("\rWriting frame %d/%d" % (i, reader.num_frames))
      sys.stdout.flush()
      self.WriteFrame(frame)
    print ""
