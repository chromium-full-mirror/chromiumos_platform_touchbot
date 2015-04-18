# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
from abc import abstractmethod
import os
import shutil
import sys
import time
import warnings

from safetynet import InterfaceMeta
import cv2
import numpy as np
import skimage
import skimage.color
import skimage.io

CODEC = cv2.cv.CV_FOURCC(*"mp4v")


def SaveImage(filename, image):
  # imsave issues a warning when saving a low-contrast image, which we do
  # in many test cases. We want to ignore this warning.
  with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)
    skimage.io.imsave(filename, image)


class PrefetchEnabled(object):
  """Helper object to be used in the with-statement.

  It will enable prefetch on entering the with block and make sure the camera
  is left in a good state upon exiting.
  """
  def __init__(self, reader):
    self.reader = reader

  def __enter__(self):
    self.reader._prefetch_enabled = True

  def __exit__(self, type, value, traceback):
    self.reader._ClearPrefetch()
    self.reader._prefetch_enabled = False


class VideoReader(object):
  """Abstract base class for Video Reader.

  Provides common functionality for accessing videos.
  """
  __metaclass__ = InterfaceMeta

  def __init__(self, num_frames, framerate, perf_enabled=False):
    self.num_frames = num_frames
    self.transfer_times = []
    self.perf_enabled = perf_enabled
    self.framerate = framerate
    self.ms_per_frame = 1000.0 / framerate
    self._current_index = -1
    self._prefetch_enabled = False

  @property
  def frame_shape(self):
    """:rtype Tuple[int, int]"""
    frame = self.FrameAt(self._current_index)
    return frame.shape

  def Frames(self, start=0, stop=None, step=1):
    """Yield frames until the video ends.

    :param int start: first frame to yield.
    :param int stop: last frame to yield.
    :param int step: step size between frames.

    yields tuples of (frame_index, frame_data) with frame_data being a grayscale
    float image.
    """
    if stop is None:
      stop = self.num_frames
    frames = range(start, stop, step)

    for i, frame in enumerate(frames):
      if self._prefetch_enabled and i + 1 < len(frames):
        self.Prefetch(frames[i + 1])
      yield frame, self.FrameAt(frame)

  def Save(self, filename, print_progress):
    """Save video to file.

    :type filename: str
    :param bool print_progress: print progress to stdout
    """
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

  @abstractmethod
  def Close():
    """Close video stream and free resourced."""

  def PrefetchEnabled(self):
    """Safely enables prefetch in combination with the with statement.

    Use as follows:
      with reader.PrefetchEnabled():
        use reader
    It will automatically clear any outstanding prefetches to leave the reader
    in a good state.

    :rtype PrefetchEnabled
    """
    return PrefetchEnabled(self)

  @abstractmethod
  def Prefetch(self, frame_index):
    """Prefetch frame.

    :param int frame_index: Frame index to prefetch
    """

  def FrameAt(self, frame_index):
    """Seeks to location in video stream and returns image.

    :type frame_index: int
    :rtype GrayscaleImage
    """
    start = time.time()
    self._SeekTo(frame_index)
    res = self._Read()
    if self.perf_enabled:
      self.transfer_times.append(time.time() - start)
    return res

  def __getstate__(self):
    raise Exception("VideoReader cannot be pickled")

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.Close()

  @abstractmethod
  def _SeekTo(self, frame_index):
    """Seek to an absolute location in the video.

    This method is for internal use and to be implemented by
    a subclass.

    :type frame_index: int
    :returns bool: True if successful
    """

  @abstractmethod
  def _Read(self):
    """Return the current frame image.

    :rtype GrayscaleImage
    """

  @abstractmethod
  def _ClearPrefetch(self):
    """Clears current prefetch buffer."""


class FileVideoReader(VideoReader):
  """Implementation of a VideoReader for reading from files using OpenCV.

  Note, any operation that seeks backwards in a file will be slow since
  the video has to be re-opened and walked through until the requested
  frame.
  """
  def __init__(self, filename, framerate):
    """
    :type filename: str
    :type framerate: int
    """
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

  def _SeekTo(self, frame_index):
    if frame_index < self._current_index:
      self.cap.open(self.filename)
      self._current_index = -1
      index_delta = frame_index + 1
    else:
      index_delta = frame_index - self._current_index

    for i in range(index_delta):
      if not self.cap.grab():
        raise Exception("Cannot grab frame_index")

    self._current_index += index_delta
    self.frame_cache = None
    return True

  def _Read(self):
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

  def Prefetch(self, frame_index):
    pass

  def _ClearPrefetch(self):
    pass


class FakeVideoReader(VideoReader):
  """Fake VideoReader returning nothing but black frames."""

  def __init__(self, num_frames, size, framerate):
    self.size = size
    VideoReader.__init__(self, num_frames, framerate)

  def _SeekTo(self, frame_index):
    return (frame_index < self.num_frames and frame_index >= 0)

  def _Read(self):
    return np.zeros(self.size, dtype=np.float)

  def Close(self, frame_index):
    pass

  def Prefetch(self, frame_index):
    pass

  def _ClearPrefetch(self):
    pass
