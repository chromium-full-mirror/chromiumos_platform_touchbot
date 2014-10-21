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
from optofidelity.system import CameraCalibration
from optofidelity.videoproc import (Canvas, Filter, VideoException, VideoReader,
                                    Viewer)


class ProcessorDebugger(object):
  """Contains video processing debugging functionality.

  This class is accepts a comma separated string of flags, and contains a canvas
  for drawing debugging information. It imitates a boolean debug flag and
  evaluates to True if any debugging flag has been set.

  For each flag, a FlagDebugger instance can be accessed using the [] operator,
  which provides the same functionality as this class, however only evaluates
  to True if the specified flag has been set.
  """
  def __init__(self, flags_string=None, start_idx=None, stop_idx=None,
               debugger=None):
    self.flags = []
    self.canvas = Canvas()
    self.start_idx = None
    self.stop_idx = None
    if debugger:
      self.flags = debugger.flags
      self.canvas = debugger.canvas
      self.start_idx = debugger.start_idx
      self.stop_idx = debugger.stop_idx
    if start_idx:
      self.start_idx = int(start_idx)
    if stop_idx:
      self.stop_idx = int(stop_idx)
    if flags_string:
      self.flags = flags_string.split(",")

  def InitFrame(self, frame, test_area):
    """Fill the debug canvas with a background from the current frame."""
    if not self.flags:
      return
    if self.HasFlag("normalized"):
      self.canvas.Fill(frame.normalized)
    elif self.HasFlag("rectified"):
      self.canvas.Fill(frame.rectified)
    else:
      if self.HasFlag("diff"):
        self.canvas.Fill(0.5 + frame.delta, test_area.Unrectify)
      else:
        self.canvas.Fill(frame.original, test_area.Unrectify)
      self.canvas.DrawContour(Canvas.GREEN, test_area.shape)

  def Display(self, video):
    """Display the debug canvas of the current frame."""
    if not self.flags:
      return
    image = self.canvas.image
    if image.shape[0] < 500:
      image = self.canvas.Scaled(2)
    key = Viewer.VideoFrame(image)
    if key == ord('p'):
      video.EnterInteractive()

  def HasFlag(self, flag):
    return flag in self.flags or "all" in self.flags

  def __getitem__(self, key):
    return FlagDebugger(self, key)

  def __nonzero__(self):
    return len(self.flags)


class FlagDebugger(ProcessorDebugger):
  """Debugger for a specific flag only

  This class provides the same functionality as ProcessorDebugger, but only
  evaluates to True if the specified flag has been set.
  """
  def __init__(self, debugger, flag):
    ProcessorDebugger.__init__(self, debugger=debugger)
    self.flag = flag

  def __nonzero__(self):
    return self.flag in self.flags


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

  @contract(test_area=CameraCalibration)
  def __init__(self, test_area):
    self.test_area = test_area
    self.detectors = {}

  @contract(detector=Detector)
  def AddDetector(self, detector):
    self.detectors[detector.name] = detector

  def Initialize(self, video_reader, debug):
    # verify in the first frame that the test area is still valid
    first_frame = video_reader.FrameAt(0)
    self.test_area.VerifyFrame(first_frame, debug["verification"])

    # initialize all detectors
    video = Video(video_reader, self.test_area)
    for detector in self.detectors.itervalues():
      if not detector.Initialize(video, debug[detector.name]):
        raise VideoException("Processor %s failed to initialize"
                             % detector.name)

  def Preprocess(self, frame, debug):
    preprocessed_data = {}
    for detector in self.detectors.itervalues():
      data = detector.Preprocess(frame, debug[detector.name])
      preprocessed_data[detector.name] = data
    return (frame.index, preprocessed_data)

  def GenerateEvents(self, trace, i, preprocessed_data, debug):
    for detector in self.detectors.itervalues():
      data = preprocessed_data[detector.name]
      flag_debug = debug[detector.name]
      events = detector.GenerateEvents(data, i, flag_debug)
      if flag_debug and events:
        print events
      trace.AddAll(events)

  @contract(video=VideoReader)
  def ReadRelevantFrames(self, video, debug):
    """Yield frames from video while omitting unecesssary frames.

    This method omits frames that show no change to the previous frame, thus
    reducing the number of frames that need to be read.

    Yields tuples (i, image) with i being the frame index and image the
    image data as a numpy array.
    """
    stop = debug.stop_idx or video.num_frames
    start = debug.start_idx or 0
    if debug["interactive"]:
      for i, image in video.Frames(start=start, stop=stop):
        print "Reading frame %d/%d" % (i, stop)
        yield i, image
      return

    prev_image = None
    i = start
    dont_peek_before = None
    while i < stop:
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
          if peek_i >= stop:
            continue
          peek_image = video.FrameAt(peek_i)
          diff = np.abs(prev_image - peek_image)
          peek_max_diff = self.peek_frame_unchanged_max_diff
          if Filter.StableMax(diff) < peek_max_diff:
            # The peeked at frame shows little difference, jump ahead.
            if not debug:
              print ""
            print "skipped", peek_i - i, "frames"
            i = peek_i
            image = peek_image
            last_peek = peek_ahead
            break
        # Don't peek again for a while.
        dont_peek_before = i + min(self.peek_distances)

      # Yield next frame
      if debug:
        print "Reading frame %d/%d" % (i, stop)
      else:
        sys.stdout.write("\rReading frame %d/%d" % (i, stop))
        sys.stdout.flush()
      yield i, image
      prev_image = image
      i += 1
    if not debug:
      print ""

  def ProcessVideo(self, video, debug):
    """Process video and return a trace of all detected events."""
    trace = Trace()
    prev_image = None
    for i, image in self.ReadRelevantFrames(video, debug):
      frame = Frame(image, prev_image, self.test_area, i)
      debug.InitFrame(frame, self.test_area)

      i, preprocessed_data = self.Preprocess(frame, debug)
      self.GenerateEvents(trace, i, preprocessed_data, debug)

      debug.Display(video)
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
    debug = ProcessorDebugger(None)
    data_queue.put(generator.Preprocess(frame, debug))


class MultithreadedVideoProcessor(VideoProcessor):
  """Processes and accumulates events from video into a trace.

  This implementation uses multiple processes to do the most computational
  intensive operations in parallel.
  """
  @contract(test_area=CameraCalibration, num_processes=">=0|None")
  def __init__(self, test_area, num_processes=None):
    self.num_processes = num_processes or multiprocessing.cpu_count()
    VideoProcessor.__init__(self, test_area)

  def ProcessVideo(self, video, debug):
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
    for i, frame in self.ReadRelevantFrames(video, debug):
      num_frames += 1
      frame_queue.put((i, frame, prev_image))
      prev_image = frame

    # Terminate worker threads by passing None into the queue
    for i in range(self.num_processes):
      frame_queue.put((None, None, None))
    frame_queue.close()

    # Read pre-processing results and put them into a dict by frame index
    data_map = {}
    for i in range(num_frames):
      data_entry = data_queue.get()
      data_map[data_entry[0]] = data_entry[1]

    # Generate events from frames in order
    trace = Trace()
    for i in sorted(data_map.keys()):
      sys.stdout.write("\rProcessing frame %d/%d" % (i, video.num_frames))
      sys.stdout.flush()
      preprocessed_data = data_map[i]
      self.GenerateEvents(trace, i, preprocessed_data, debug)
    print ""
    return trace
