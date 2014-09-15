# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides classes that generate traces from video files."""
import multiprocessing

from detection import Frame, Line, Finger
from trace import Trace
from videoproc import Viewer, Canvas


class TraceGenerator(object):
  """Processes and accumulates events from video into a trace."""
  def __init__(self, screen):
    self.screen = screen
    self.finger = None
    self.line = None

  def Init(self, video, debug=False):
    self.finger = Finger(self.screen)
    self.line = Line()
    for i, im in video.Frames(start=-1, stop=-100, step=-10):
      frame = Frame(im, None, self.screen)
      if self.line.DetectTargetLine(frame, debug=debug):
        return True
    return False

  def Preprocess(self, frame, debug=False):
    screen_data = self.screen.Preprocess(frame, debug)
    line_data = self.line.Preprocess(frame, debug)
    finger_data = self.finger.Preprocess(frame, debug)
    return (frame.index, screen_data, line_data, finger_data)

  def GenerateEvents(self, trace, i, screen_data, line_data, finger_data,
                     debug):
    trace.AddAll(self.screen.GenerateEvents(screen_data, i), debug)
    trace.AddAll(self.finger.GenerateEvents(finger_data, i), debug)
    trace.AddAll(self.line.GenerateEvents(line_data, i), debug)

  def DebugView(self, im, debug):
    if debug == "all":
      canvas = Canvas(im, self.screen.shape)
      canvas.DrawContour([0, 0, 1], self.screen.shape, no_crop=True)
      if self.finger.found:
        canvas.DrawContour([1, 0, 0], self.finger.finger_shape)
        canvas.DrawLine([1, 0, 0], x=self.finger.location)

      if self.line.found:
        canvas.DrawContour([0, 0.5, 0], self.line.target_shape)
      for segment in self.line.segments:
        canvas.DrawLine([0, 0.5, 0], x=segment.end)
      return Viewer.VideoFrame(canvas.image)
    elif debug == "screen":
      return Viewer.VideoFrame(self.screen)
    elif debug == "line":
      return Viewer.VideoFrame(self.line.debug_canvas.Scaled(2))
    elif debug == "finger":
      return Viewer.VideoFrame(self.finger.debug_canvas.image)

  def ProcessVideo(self, video, debug=False):
    """Process video and return a trace of all detected events."""
    self.Init(video, debug is not None)

    trace = Trace()
    prev_im = None
    for i, im in video.Frames():
      print i, "/", video.num_frames
      frame = Frame(im, prev_im, self.screen, i)
      pre_process_data = self.Preprocess(frame, debug)
      self.GenerateEvents(trace, *pre_process_data, debug=debug)
      if debug:
        key = self.DebugView(im, debug)
        if key == ord('p'):
          video.EnterInteractive()
      prev_im = im

    return trace


def PreProcessProcess(generator, frame_queue, data_queue):
  """Method to be called by subprocesses to run the pre-process step.

  This method reads images from the frame_queue, runs the pre-processing
  step of the Finger and Line detection code on them and outputs
  the results into the data_queue.

  See MultithreadedTraceGenerator.ProcessVideo().
  """
  while True:
    i, image, prev_image = frame_queue.get()
    if image is None:
      data_queue.put(None)
      break
    data_queue.put(generator.Preprocess(i, image, prev_image))


class MultithreadedTraceGenerator(TraceGenerator):
  """Processes and accumulates events from video into a trace.

  This implementation uses multiple processes to do the most computational
  intensive operations in parallel.
  """
  def __init__(self, screen, num_processes=None):
    self.num_processes = num_processes or multiprocessing.cpu_count()
    TraceGenerator.__init__(self, screen)

  def ProcessVideo(self, video, debug=None):
    self.Init(video, debug)

    # Start pre-processing processes
    frame_queue = multiprocessing.Queue()
    data_queue = multiprocessing.Queue()
    for i in range(self.num_processes):
      process_args = (self, frame_queue, data_queue,)
      process = multiprocessing.Process(target=PreProcessProcess,
                                        args=process_args)
      process.start()

    # Read frames and put them into the processing queue
    prev_image = None
    for i, frame in video.Frames():
      print i, "/", video.num_frames
      frame_queue.put((i, frame, prev_image))
      prev_image = frame
    for i in range(self.num_processes):
      # Terminate worker threads by passing None into the queue
      frame_queue.put((None, None, None))
    frame_queue.close()

    # Read pre-processing results and order them by frame index
    ordered_data = []
    while True:
      data_entry = data_queue.get()
      if not data_entry:
        break
      ordered_data.append(data_entry)
    ordered_data.sort(key=lambda e: e[0])

    # Generate events from pre-processing results
    trace = Trace()
    for data in ordered_data:
      self.GenerateEvents(trace, *data, debug=debug)
      if debug is not None:
        image = video.FrameAt(data[0])
        self.DebugView(image, debug)
    return trace
