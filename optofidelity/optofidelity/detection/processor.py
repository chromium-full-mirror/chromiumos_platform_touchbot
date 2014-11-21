# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides classes that generate traces from video files."""
from contracts import contract
import ctypes
import gc
import multiprocessing
import numpy as np
import os
import signal
import sys
import time

from optofidelity.detection.detector import Frame, Video, Detector
from optofidelity.detection.trace import Trace
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

  def Print(self, msg, *args):
    if self:
      print "DEBUG:", msg % args

  def InitFrame(self, frame, test_area):
    """Fill the debug canvas with a background from the current frame."""
    tform = test_area.Unrectify if test_area else None
    if not self.HasFlag("video"):
      return
    if self.HasFlag("normalized"):
      self.canvas.Fill(frame.normalized)
    elif self.HasFlag("rectified"):
      self.canvas.Fill(frame.rectified)
    else:
      if self.HasFlag("diff"):
        self.canvas.Fill(0.5 + frame.delta, tform)
      else:
        self.canvas.Fill(frame.original, tform)
      if test_area:
        self.canvas.DrawContour(Canvas.GREEN, test_area.shape)

  def Display(self, video):
    """Display the debug canvas of the current frame."""
    if not self.HasFlag("video"):
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

  def Print(self, msg, *args):
    if self:
      print "DEBUG(%s):" % self.flag, msg % args

def VideoProcessor(test_area, debug):
  if debug["video"]:
    return SinglethreadedVideoProcessor(test_area)
  else:
    return MultithreadedVideoProcessor(test_area)

class SinglethreadedVideoProcessor(object):
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

  def __init__(self, test_area):
    self.test_area = test_area
    self.detectors = {}

  @contract(detector=Detector)
  def AddDetector(self, detector):
    self.detectors[detector.name] = detector

  def Initialize(self, video_reader, debug):
    # verify in the first frame that the test area is still valid
    first_frame = video_reader.FrameAt(0)
    if self.test_area:
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
    with video.PrefetchEnabled():
      stop = debug.stop_idx or video.num_frames
      start = debug.start_idx or 0
      if debug["interactive"]:
        for i, image in video.Frames(start=start, stop=stop):
          yield i, image
        return

      prev_image = None
      i = start
      dont_peek_before = None
      while i < stop:
        # Read frame and calculate inter-frame difference
        if i + 1 < stop:
          video.Prefetch(i + 1)
        image = video.FrameAt(i)

        diff = image
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
              i = peek_i
              image = peek_image
              last_peek = peek_ahead
              break
          # Don't peek again for a while.
          dont_peek_before = i + min(self.peek_distances)

        # Yield next frame
        yield i, image
        prev_image = image
        i += 1

  def ProcessVideo(self, video, debug):
    """Process video and return a trace of all detected events."""
    trace = Trace()
    prev_image = None
    for i, image in self.ReadRelevantFrames(video, debug):
      print "Processing frame %d/%d" % (i, video.num_frames)

      frame = Frame(image, prev_image, self.test_area, i)
      debug.InitFrame(frame, self.test_area)

      i, preprocessed_data = self.Preprocess(frame, debug)
      self.GenerateEvents(trace, i, preprocessed_data, debug)

      debug.Display(video)
      prev_image = image
    return trace

class Buffer(object):
  """A buffer stores a video frame to be processed.

  The image data is stored in a shared memory array to reduce inter-process
  communication. Each buffer has an Event-type flag that denotes whether the
  processing is done.
  """
  def __init__(self, image_shape):
    size = image_shape[0] * image_shape[1]
    self.image_shape = image_shape
    self.buffer = multiprocessing.Array(ctypes.c_double, size)
    self.done = multiprocessing.Event()
    self.done.set()

  @property
  def image(self):
    """Access shared memory as a numpy array. This does not copy data."""
    np_buffer = np.frombuffer(self.buffer.get_obj())
    return np_buffer.reshape(self.image_shape)

class PreprocessWorker(multiprocessing.Process):
  """A worker process that runs VideoProcessor.Preprocess on video frames.

  It receives (frame_index, buffer_index, prev_buffer_index) via the
  input_queue and processes posts the results of VideoProcessor.Preprocess
  into the output_queue.
  frame_index: is the index of the current frame in the video
  buffer_index: Points to the index in buffer_list where this frame is stored.
  prev_buffer_index: Points the index of the previous frame.
  """
  def __init__(self, processor, buffer_list, input_queue, output_queue):
    multiprocessing.Process.__init__(self)
    self.buffer_list = buffer_list
    self.input_queue = input_queue
    self.output_queue = output_queue
    self.processor = processor

  def run(self):
    # Ignore keyboard interrupts. The parent process is killing all subprocess.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    debugger = ProcessorDebugger(None)

    while True:
      i, index, prev_index = self.input_queue.get()
      if index is None:
        break

      # Read current and previous image from shared memory buffer
      image = self.buffer_list[index].image
      prev_image = None
      if prev_index is not None:
        prev_image = self.buffer_list[prev_index].image
      frame = Frame(image, prev_image, self.processor.test_area, i)

      # Pre-process
      result = self.processor.Preprocess(frame, debugger)
      self.output_queue.put(result)

      # Notify processing of this buffer is done.
      self.buffer_list[index].done.set()

      gc.collect()

class MultithreadedVideoProcessor(SinglethreadedVideoProcessor):
  """Processes and accumulates events from video into a trace.

  This implementation uses multiple processes to do the most computational
  intensive operations in parallel.
  """
  @contract(num_processes=">=0|None")
  def __init__(self, test_area, num_processes=None):
    self.num_processes = num_processes or multiprocessing.cpu_count()
    SinglethreadedVideoProcessor.__init__(self, test_area)

  def ProcessVideo(self, video, debug):
    video.perf = True

    # Create shared memory buffer. This is a ring buffer.
    buffer_list = []
    image_shape = video.frame_shape
    for i in range(self.num_processes + 2):
      buffer_list.append(Buffer(image_shape))

    # Start pre-processing processes
    frame_queue = multiprocessing.Queue()
    data_queue = multiprocessing.Queue()
    processes = []

    try:
      for i in range(self.num_processes):
        process = PreprocessWorker(self, buffer_list, frame_queue, data_queue)
        process.start()
        processes.append(process)

      # Read frames into shared memory buffer and create jobs to process them.
      num_frames = 0
      current_idx = 0
      prev_idx = None

      for i, frame in self.ReadRelevantFrames(video, debug):
        def visualize(waiting_on=""):
          sys.stdout.write("\r")
          for b in buffer_list:
            sys.stdout.write("*" if b.done.is_set() else "-")
          sys.stdout.write(" %d / %d" % (i, video.num_frames))
          if debug["perf"] and waiting_on:
            sys.stdout.write(" (waiting on %s)" % waiting_on)
          sys.stdout.flush()
        visualize()

        # Wait for all operations accessing the current buffer to be done.
        # We are waiting for next_idx too since it will use the current_idx
        # as a prev_image.
        next_idx = (current_idx + 1) % len(buffer_list)
        while not buffer_list[current_idx].done.wait():
          visualize("current buffer")
        while not buffer_list[next_idx].done.wait():
          visualize("next buffer")

        # Write into current buffer and create a job to process it.
        visualize("queue")
        buffer_list[current_idx].image[:] = frame[:]
        buffer_list[current_idx].done.clear()
        frame_queue.put((i, current_idx, prev_idx))

        # Update counters.
        prev_idx = current_idx
        current_idx = next_idx
        num_frames += 1
        visualize("phantom")
      print

      # Terminate worker threads by passing None into the queue
      for i in range(self.num_processes):
        frame_queue.put((None, None, None))
      frame_queue.close()

    except:
      # Make sure all processes are killed in case of errors
      print
      print "Killing child processes"
      for process in processes:
        if process.pid:
          os.kill(process.pid, signal.SIGKILL)
      raise


    # Read pre-processing results and put them into a dict by frame index
    data_map = {}
    for i in range(num_frames):
      data_entry = data_queue.get()
      data_map[data_entry[0]] = data_entry[1]

    # Generate events from frames in order
    trace = Trace()
    for i in sorted(data_map.keys()):
      sys.stdout.write("\rGenerating events %d/%d" % (i, video.num_frames))
      sys.stdout.flush()
      preprocessed_data = data_map[i]
      self.GenerateEvents(trace, i, preprocessed_data, debug)
    print
    return trace
