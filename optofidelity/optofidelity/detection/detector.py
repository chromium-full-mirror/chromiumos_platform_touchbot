# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np
from optofidelity.videoproc import Viewer, Filter

class Frame(object):
  """This class stores multiple versions and views of a camera frame.

  This class stores a cropped version of the image, enhances it with noise
  filtering and calculates the reflectance.
  """
  def __init__(self, im, prev_im, test_area, index=0):
    self.original = im
    self.rectified = im
    self.index = index
    self.test_area = test_area

    if test_area:
      self.crop_shape = test_area.shape
      self.rectified = test_area.Rectify(im)

    # noise filtered reflectance
    self.reflectance = Filter.Reflectance(self.rectified, disk_size=40,
                                          scale=0.5)
    self.reflectance = Filter.Median(self.reflectance, disk_size=1)

    if prev_im is not None:
      self.delta = im - prev_im
    else:
      self.delta = np.zeros(im.shape)


class Video(object):
  """Wraps around a video_reader and yields Frame instances."""
  def __init__(self, video_reader, test_area):
    self.video_reader = video_reader
    self.test_area = test_area

  def Frames(self, start=0, stop=None, step=1, frames=None):
    prev_image = None
    for i, image in self.video_reader.Frames(start, stop, step, frames):
      yield Frame(image, prev_image, self.test_area, i)
      prev_image = image

  def FrameAt(self, i):
    return Frame(self.video_reader.FrameAt(i), None, self.test_area, i)


class Detector(object):
  """Base class for detectors that extract event traces from videos."""
  name = NotImplemented

  def Initialize(self, video, debug=False):
    """To be called to initialize the detector for a specific video.

    The detector might query specific frames from the video stream to
    initialize itself.
    Returns True if the detector is fully functional for this video stream.
    """
    return True

  def Preprocess(self, frame, debug=False):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. It is
    is stateless and can be called on any frames out of order (i.e. also in
    parallel processes)
    """
    raise NotImplementedError()

  def GenerateEvents(self, preprocessed_data, timestamp, debug_canvas=None):
    """Perform detection on the preprocessed data and return events.

    This method has to be called in order, and should offload as much of the
    heavy processing to Preprocess as possible.
    """
    raise NotImplementedError()