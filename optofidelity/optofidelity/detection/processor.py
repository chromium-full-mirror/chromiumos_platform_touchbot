# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides classes that generate traces from video files."""
import multiprocessing
import sys

from optofidelity.detection.detector import Frame, Video
from optofidelity.detection.trace import Trace
from optofidelity.videoproc import Viewer, Canvas, VideoException


class VideoProcessor(object):
  """Processes and accumulates events from video into a trace."""
  def __init__(self, test_area):
    self.test_area = test_area
    self.detectors = {}

  def AddDetector(self, detector):
    self.detectors[detector.name] = detector

  def Initialize(self, video_reader, debug=[]):
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
      if "reflectance" in debug:
        return Canvas(frame.reflectance)
      elif "rectified" in debug:
        return Canvas(frame.rectified)
      elif "delta" in debug:
        return Canvas(frame.delta, self.test_area.Unrectify)
      else:
        return Canvas(frame.original, self.test_area.Unrectify)
    return None

  def DisplayDebugCanvas(self, debug_canvas, video):
    if debug_canvas:
      key = Viewer.VideoFrame(debug_canvas.image)
      if key == ord('p'):
        video.EnterInteractive()

  def ProcessVideo(self, video, step=1, debug=[]):
    """Process video and return a trace of all detected events."""
    trace = Trace()
    prev_im = None
    for i, im in video.Frames(step=step):
      sys.stdout.write("\rProcessing frame %d/%d" % (i, video.num_frames))
      sys.stdout.flush()

      frame = Frame(im, prev_im, self.test_area, i)
      i, preprocessed_data = self.Preprocess(frame, debug)

      debug_canvas = self.MakeDebugCanvas(debug, frame)
      self.GenerateEvents(trace, i, preprocessed_data, debug, debug_canvas)
      self.DisplayDebugCanvas(debug_canvas, video)
      prev_im = im
    print ""
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
  def __init__(self, screen, num_processes=None):
    self.num_processes = num_processes or multiprocessing.cpu_count()
    VideoProcessor.__init__(self, screen)

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
    for i, frame in video.Frames(step=step):
      sys.stdout.write("\rPreprocessing frame %d/%d" % (i, video.num_frames))
      sys.stdout.flush()
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

    if not debug:
      # Process frames in order
      for i in sorted(data_map.keys()):
        ProcessFrame(i)
    else:
      # Load frames from video again for debugging view
      prev_image = None
      for i, image in video.Frames(step=step):
        frame = Frame(image, prev_image, self.test_area, i)
        debug_canvas = self.MakeDebugCanvas(debug, frame)
        ProcessFrame(i, debug, debug_canvas)
        self.DisplayDebugCanvas(debug_canvas, video)

    return trace
