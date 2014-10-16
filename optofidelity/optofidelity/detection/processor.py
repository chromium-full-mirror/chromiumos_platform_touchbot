# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides classes that generate traces from video files."""
from contracts import contract
import multiprocessing
import numpy as np
import sys

from optofidelity.detection.detector import Frame, Video, Detector
from optofidelity.detection.trace import Trace
from optofidelity.system import TestArea
from optofidelity.videoproc import (Canvas, Filter, VideoException, VideoReader,
                                    Viewer)


class VideoProcessor(object):
  """Processes and accumulates events from video into a trace."""

  inter_frame_unchanged_max_diff = 0.05
  """Maximum frame difference between two adjacent frames for them to be
     considered as not showing any relevant difference."""

  peek_frame_unchanged_max_diff = 0.2
  """Maximum frame difference between a frame and a distance reference frame
     for them to be considered as not showing any relevant difference."""

  peek_distances = (128, 64, 32, 16, 8)
  """Distances from the current frame to peek at when looking for frames to
     skip."""

  @contract(test_area=TestArea)
  def __init__(self, test_area):
    self.test_area = test_area
    self.detectors = {}

  @contract(detector=Detector)
  def AddDetector(self, detector):
    self.detectors[detector.name] = detector

  def Initialize(self, video_reader, debug=[]):
    # verify in the first frame that the test area is still valid
    first_frame = video_reader.FrameAt(0)
    self.test_area.VerifyFrame(first_frame,
                               "verification" in debug or "all" in debug)

    # initialize all detectors
    video = Video(video_reader, self.test_area)
    for detector in self.detectors.itervalues():
      debug_flag = debug and (detector.name in debug or "all" in debug)
      if not detector.Initialize(video, debug_flag):
        raise VideoException("Processor %s failed to initialize"
                             % detector.name)

  def Preprocess(self, frame, debug=[]):
    preprocessed_data = {}
    for detector in self.detectors.itervalues():
      debug_flag = debug and (detector.name in debug or "all" in debug)
      data = detector.Preprocess(frame, debug_flag)
      preprocessed_data[detector.name] = data
    return (frame.index, preprocessed_data)

  def GenerateEvents(self, trace, i, preprocessed_data, debug=[],
                     debug_canvas=None):
    for detector in self.detectors.itervalues():
      debug_flag = debug and (detector.name in debug or "all" in debug)
      data = preprocessed_data[detector.name]
      canvas = debug_canvas if debug_flag else None
      events = detector.GenerateEvents(data, i, canvas)
      if debug_flag and events:
        print events
      trace.AddAll(events)

  def SkimVideo(self, video, debug=[]):
    """Skims through video and return types of Events generated."""
    trace = self.ProcessVideo(video, step=15, debug=debug)
    event_types = []
    for event in trace.Events():
      if event.event_type not in event_types:
        event_types.append(event.event_type)
    return event_types

  def MakeDebugCanvas(self, debug, frame):
    if debug:
      if "normalized" in debug:
        return Canvas(frame.normalized)
      elif "rectified" in debug:
        return Canvas(frame.rectified)
      else:
        if "delta" in debug:
          canvas = Canvas(0.5 + frame.delta, self.test_area.Unrectify)
        else:
          canvas = Canvas(frame.original, self.test_area.Unrectify)
        canvas.DrawContour(Canvas.GREEN, self.test_area.shape)
        return canvas
    return None

  def DisplayDebugCanvas(self, debug_canvas, video):
    if debug_canvas:
      image = debug_canvas.image
      if debug_canvas.image.shape[0] < 500:
        image = debug_canvas.Scaled(2)
      key = Viewer.VideoFrame(image)
      if key == ord('p'):
        video.EnterInteractive()

  @contract(video=VideoReader)
  def ReadRelevantFrames(self, video, step=1):
    """Yield frames from video while omitting unecesssary frames.

    This method omits frames that show no change to the previous frame, thus
    reducing the number of frames that need to be read.

    Yields tuples (i, image) with i being the frame index and image the
    image data as a numpy array.
    """
    prev_image = None
    i = 0
    dont_peek_before = None
    while i < video.num_frames:
      # Read frame and calculate inter-frame difference
      image = video.FrameAt(i)
      diff = np.ones((1, 1))
      if prev_image is not None:
        diff = np.abs(prev_image - image)

      inter_max_diff = self.inter_frame_unchanged_max_diff
      if Filter.StableMax(diff) < inter_max_diff and i >= dont_peek_before:
        # This frame shows very little inter-frame difference, thus could be
        # omitted. Peek ahead a decreasing distance away from the previous
        # frame, looking for one that still shows little difference.
        for peek_ahead in self.peek_distances:
          peek_i = i + peek_ahead - 1
          if peek_i >= video.num_frames:
            continue
          peek_image = video.FrameAt(peek_i)
          diff = np.abs(prev_image - peek_image)
          peek_max_diff = self.peek_frame_unchanged_max_diff
          if Filter.StableMax(diff) < peek_max_diff:
            # The peeked at frame shows little difference, jump ahead.
            print ""
            print "skipped", peek_i - i, "frames"
            i = peek_i
            image = peek_image
            last_peek = peek_ahead
            break
        # Don't peek again for a while.
        dont_peek_before = i + min(self.peek_distances)

      # Yield next frame
      sys.stdout.write("\rReading frame %d/%d" % (i, video.num_frames))
      sys.stdout.flush()
      yield i, image
      prev_image = image
      i += 1
    print ""

  def ProcessVideo(self, video, step=1, debug=[]):
    """Process video and return a trace of all detected events."""
    trace = Trace()
    prev_image = None
    for i, image in self.ReadRelevantFrames(video):
      frame = Frame(image, prev_image, self.test_area, i)
      i, preprocessed_data = self.Preprocess(frame, debug)

      debug_canvas = self.MakeDebugCanvas(debug, frame)
      self.GenerateEvents(trace, i, preprocessed_data, debug, debug_canvas)
      self.DisplayDebugCanvas(debug_canvas, video)
      prev_image = image
    return trace


def PreProcessProcess(generator, frame_queue, data_queue):
  """Method to be called by subprocesses to run the pre-process step.

  This method reads images from the frame_queue, runs the pre-processing
  step of the Finger and Line detection code on them and outputs
  the results into the data_queue.

  See MultithreadedVideoProcessor.ProcessVideo().
  """
  while True:
    i, image, prev_image = frame_queue.get()
    if image is None:
      break
    frame = Frame(image, prev_image, generator.test_area, i)
    data_queue.put(generator.Preprocess(frame))


class MultithreadedVideoProcessor(VideoProcessor):
  """Processes and accumulates events from video into a trace.

  This implementation uses multiple processes to do the most computational
  intensive operations in parallel.
  """
  @contract(test_area=TestArea, num_processes=">=0|None")
  def __init__(self, test_area, num_processes=None):
    self.num_processes = num_processes or multiprocessing.cpu_count()
    VideoProcessor.__init__(self, test_area)

  def ProcessVideo(self, video, step=1, debug=[]):
    # Start pre-processing processes
    frame_queue = multiprocessing.Queue()
    data_queue = multiprocessing.Queue()
    processes = []
    for i in range(self.num_processes):
      process_args = (self, frame_queue, data_queue,)
      process = multiprocessing.Process(target=PreProcessProcess,
                                        args=process_args)
      process.start()
      processes.append(process)

    # Read frames and put them into the processing queue
    prev_image = None
    num_frames = 0
    for i, frame in self.ReadRelevantFrames(video, step=1):
      num_frames += 1
      frame_queue.put((i, frame, prev_image))
      prev_image = frame
    print ""

    # Terminate worker threads by passing None into the queue
    for i in range(self.num_processes):
      frame_queue.put((None, None, None))
    frame_queue.close()

    # Read pre-processing results and put them into a dict by frame index
    data_map = {}
    for i in range(num_frames):
      data_entry = data_queue.get()
      data_map[data_entry[0]] = data_entry[1]

    # Generate events from pre-processing results
    trace = Trace()
    def ProcessFrame(i, debug=[], debug_canvas=None):
      sys.stdout.write("\rProcessing frame %d/%d" % (i, video.num_frames))
      sys.stdout.flush()
      preprocessed_data = data_map[i]
      self.GenerateEvents(trace, i, preprocessed_data, debug, debug_canvas)

    # Process frames in order
    prev_image = None
    for i in sorted(data_map.keys()):
      if not debug:
        ProcessFrame(i)
      else:
        # Load frames from video again for debugging view
        image = video.FrameAt(i)
        frame = Frame(image, prev_image, self.test_area, i)
        debug_canvas = self.MakeDebugCanvas(debug, frame)
        ProcessFrame(i, debug, debug_canvas)
        self.DisplayDebugCanvas(debug_canvas, video)
        prev_image = image

    return trace
