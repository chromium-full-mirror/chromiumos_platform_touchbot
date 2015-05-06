# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import ctypes
import gc
import logging
import multiprocessing
import os
import signal
import sys

from safetynet import Any, Dict, List, Optional, Tuple, TypecheckMeta
import numpy as np

from ._calibrated_frame import CalibratedFrame
from ._detector import DetectorDebugger
from .screen_calibration import ScreenCalibration
from .st_processor import SinglethreadedVideoProcessor
from .trace import Trace

_log = logging.getLogger(__name__)


class Buffer(object):
  """A buffer stores a video frame to be processed.

  The image data is stored in a shared memory array to reduce inter-process
  communication. Each buffer has an Event-type flag that denotes whether the
  processing is done.
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, image_shape):
    """
    :param Tuple[int, int] image_shape
    """
    size = image_shape[0] * image_shape[1]
    self.image_shape = image_shape
    self.buffer = multiprocessing.Array(ctypes.c_double, size)
    self.done = multiprocessing.Event()
    self.done.set()

  @property
  def image(self):
    """Access shared memory as a numpy array. This does not copy data.

    :returns np.ndarray
    """
    np_buffer = np.frombuffer(self.buffer.get_obj())
    return np_buffer.reshape(self.image_shape)


class PreprocessWorker(multiprocessing.Process):
  """A worker process that runs VideoProcessor.Preprocess on video frames."""

  def __init__(self, processor, buffer_list, input_queue, output_queue):
    """
    :param MultithreadedVideoProcessor processor
    :param List[Buffer] buffer_list
    :param Queue input_queue: Input queue receiving the tuple (frame_index,
           buffer_index, prev_buffer_index). The buffer indices point to an
           entry in buffer_list that is supposed to be pre-processed.
    :param Queue output_queue: Output queue sending the a dictionary of
                               preprocessing results of each detector.
    """
    multiprocessing.Process.__init__(self)
    self.buffer_list = buffer_list
    self.input_queue = input_queue
    self.output_queue = output_queue
    self.processor = processor

  def run(self):
    # Ignore keyboard interrupts. The parent process is killing all subprocess.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    while True:
      i, index, prev_index = self.input_queue.get()
      if index is None:
        break
      _log.debug("PreProcessing frame %d" % i)

      # Read current and previous image from shared memory buffer
      image = self.buffer_list[index].image
      prev_image = None
      if prev_index is not None:
        prev_image = self.buffer_list[prev_index].image

      # Run preprocessing
      calib_frame = CalibratedFrame(image, prev_image,
                                    self.processor.screen_calibration, i)
      result = self.processor._Preprocess(calib_frame)
      self.output_queue.put(result)

      # Notify processing of this buffer is done.
      self.buffer_list[index].done.set()

      gc.collect()


class MultithreadedVideoProcessor(SinglethreadedVideoProcessor):
  """Processes video using detectors and accumulates generated events.

  This implementation uses multiple processes to do the most computational
  intensive operations in parallel.
  """

  def __init__(self):
    SinglethreadedVideoProcessor.__init__(self)
    self.num_processes = multiprocessing.cpu_count()

  def ProcessVideo(self, video_reader, screen_calibration, debug_flags):
    self._InitDetectors()
    self.screen_calibration = screen_calibration

    if not self._detectors:
      return Trace([])

    # Create shared memory buffer. This is a ring buffer.
    buffer_list = []
    image_shape = video_reader.frame_shape
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

      for i, frame in video_reader.Frames():
        def visualize():
          sys.stdout.write("\r")
          for b in buffer_list:
            sys.stdout.write("*" if b.done.is_set() else "-")
          sys.stdout.write(" %d / %d" % (i + 1, video_reader.num_frames))
          sys.stdout.flush()
        visualize()

        for process in processes:
          if not process.is_alive():
            raise Exception("PreprocessWorker died")

        # Wait for all operations accessing the current buffer to be done.
        # We are waiting for next_idx too since it will use the current_idx
        # as a prev_image.
        next_idx = (current_idx + 1) % len(buffer_list)
        while not buffer_list[current_idx].done.wait():
          visualize()
        while not buffer_list[next_idx].done.wait():
          visualize()

        # Write into current buffer and create a job to process it.
        buffer_list[current_idx].image[:] = frame[:]
        buffer_list[current_idx].done.clear()
        frame_queue.put((i, current_idx, prev_idx))

        # Update counters.
        prev_idx = current_idx
        current_idx = next_idx
        num_frames += 1
        visualize()
      print

      # Terminate worker threads by passing None into the queue
      for i in range(self.num_processes):
        frame_queue.put((None, None, None))
      frame_queue.close()

    except:
      # Make sure all processes are killed in case of errors
      print
      _log.exception("Killing child processes due to exception")
      for process in processes:
        if process.pid  and process.is_alive():
          os.kill(process.pid, signal.SIGKILL)
      raise


    # Read pre-processing results and put them into a dict by frame index
    data_map = {}
    for i in range(num_frames):
      data_entry = data_queue.get()
      data_map[data_entry[0]] = data_entry[1]

    # Generate events from frames in order
    events = []
    for i in sorted(data_map.keys()):
      msg = "Generating events %d/%d" % (i + 1, video_reader.num_frames)
      _log.debug(msg)
      sys.stdout.write("\r" + msg)
      sys.stdout.flush()

      preprocessed_data = data_map[i]
      events.extend(self._GenerateEvents(i, preprocessed_data, None))
    print
    return Trace(events)

  def _Preprocess(self, calib_frame):
    """Preprocess a single calibrated frame.

    :param CalibratedFrame calib_frame
    :returns Tuple[int, Dict[str, Any]]
    """
    preprocessed_data_map = {}
    for detector in self._detectors:
      preprocessed_data = detector.Preprocess(calib_frame, None)
      preprocessed_data_map[detector.NAME] = preprocessed_data
    return (calib_frame.frame_index, preprocessed_data_map)

  def _GenerateEvents(self, frame_index, preprocessed_data_map, debugger):
    """ Generate events from a single frame.

    :param int frame_index
    :param Dict[str, Any] preprocessed_data_map
    :param Optional[DetectorDebugger] debugger
    """
    all_events = []
    for detector in self._detectors:
      preprocessed_data = preprocessed_data_map[detector.NAME]
      events = detector.GenerateEvents(preprocessed_data, frame_index, None)
      all_events.extend(events)
    return all_events
