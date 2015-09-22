# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of Benchmark."""

import cPickle as pickle
import logging
import os
import time

from safetynet import Any, Dict, List, Optional, TypecheckMeta

from optofidelity.detection import (LEDEvent, ScreenCalibration, Trace,
                                    VideoProcessor)
from optofidelity.system import BenchmarkSubject
from optofidelity.util import GSFile, GSFolder, GSOpenFile, GSPathExists
from optofidelity.videoproc import FileVideoReader, SaveImage

from ._delegate import BenchmarkDelegate
from .results import BenchmarkMeasurements, BenchmarkResults

_log = logging.getLogger("benchmark")
_perf_log = logging.getLogger("perf")


class Benchmark(object):
  """Represents a single benchmark that can be executed and serialized.

  A benchmark integrates the robot and video processing and allows benchmarks to
  be executed and saved to disk.

  The overall process is divided into 3 stages that have to be executed in the
  right order: ExecuteOnSubject, ProcessVideo and ProcessTrace.
  """

  __metaclass__ = TypecheckMeta

  def __init__(self, name, delegate, metadata, screen_calibration):
    """Provide information on new benchmark.

    :param str name: Name of the subject this benchmark is going to be
           executed on.
    :param BenchmarkDelegate delegate: Delegate used for executing benchmark.
    :param Dict[str, Any] metadata: Metainformation to be stored along with the
           benchmark.
    """
    self._delegate = delegate
    self.name = name
    self.led_calib_delays = (0.0, 0.0)

    self.screen_calibration = screen_calibration
    self.framerate = None
    self.results = BenchmarkResults(name, metadata)
    self.trace = None
    self.video = None

    self.log = ""

  def ExecuteOnSubject(self, subject):
    """Instruct the robot to execute the benchmark.

    :type subject: BenchmarkSubject
    """
    self.results.metadata["subject_name"] = subject.name
    subject.navigator.OpenActivity(self._delegate.activity)
    self.video = self._delegate.ExecuteOnSubject(subject)
    subject.navigator.CloseActivity()
    self.framerate = self.video.framerate
    self.trace = None
    self.results.measurements = None
    return self.video

  def ProcessVideo(self, video_processor, debug_flags):
    """Process the recorded video into a trace.

    This step requires that ExecuteOnSubject and CalibrateScreen (or
    UseExistingCalibration) have been called before.

    :param List[str] debug_flags: list of debug flags for the VideoProcessor.
    :param bool multithreaded: Use all cores of the system to do processing.
    :rtype Trace
    """
    assert self.video, "No test video"

    self._delegate.InitializeProcessor(video_processor, self.video,
                                       self.screen_calibration)

    start_t = time.time()
    self.trace = video_processor.ProcessVideo(self.video,
                                              self.screen_calibration,
                                              debug_flags)
    self.trace.ApplyLEDCalib(*self.led_calib_delays)

    self.results.measurements = None

    delta_t = (time.time() - start_t)
    delta_t_per_frame = delta_t / self.video.num_frames
    _perf_log.info("Processing: %f s", delta_t)
    _perf_log.info("            %f ms / frame", (delta_t_per_frame * 1000))

    return self.trace

  def ProcessTrace(self):
    """Process the calculated trace into latency measurements.

    :rtype BenchmarkResults
    """
    assert self.trace is not None, "No test trace"

    start_t = time.time()
    self.results.measurements = BenchmarkMeasurements(self.trace.ms_per_frame)
    self._delegate.ProcessTrace(self.trace, self.results.measurements)
    self.results.measurements.SanityCheck()

    _perf_log.info("Trace processing: %f s", (time.time() - start_t))
    return self.results

  def Save(self, url, debug_info=False, video=False):
    """Serialize benchmark to a folder on disk.

    The benchmark is saved into multiple files in the folder specified in path.

    :param str path: path to folder.
    :param bool debug_info: Extract human readable debug information
    :param bool video: Save video too, this allows you to call ProcessVideo
           after serialization.
    """
    with GSFolder(url) as path:
      if not os.path.exists(path):
        os.makedirs(path)

      with open(self._GetPickleFileName(path), "wb") as pickle_file:
        pickle.dump(self, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)
      if debug_info:
        self._SaveDebugInfo(path)
      if video and self.video:
        self.video.Save(self._GetVideoFileName(path))

  def _SaveDebugInfo(self, path):
    """Save human readable debug information into benchmark folder.

    :param str path: path to folder.
    """
    calib = self.screen_calibration
    if calib:
      SaveImage(os.path.join(path, "calibration_black.png"), calib.black_frame)
      SaveImage(os.path.join(path, "calibration_white.png"), calib.white_frame)
    if self.trace:
      with open(os.path.join(path, "trace.pickle"), "wb") as pickle_file:
        pickle.dump(self.trace, pickle_file)

    def DumpProperty(variable_name):
      data = getattr(self, variable_name)
      with open(os.path.join(path, "%s.txt" % variable_name), "wb") as file:
        file.write(str(data) if data is not None else "")
    DumpProperty("trace")
    DumpProperty("results")
    DumpProperty("log")

  @classmethod
  def Load(cls, url):
    """Load benchmark from folder or cloud storage

    :param str url: local folder or gs:// url
    """
    with GSOpenFile(cls._GetPickleFileName(url), "rb") as pickle_file:
      self = pickle.load(pickle_file)

    video_url = cls._GetVideoFileName(url)
    if GSPathExists(video_url):
      with GSFile(video_url, download=True, upload=False) as video_file:
        self.video = FileVideoReader(video_file, self.framerate)
    return self

  @classmethod
  def _GetPickleFileName(cls, path):
    return os.path.join(path, "benchmark.pickle")

  @classmethod
  def _GetVideoFileName(cls, path):
    return os.path.join(path, "video.avi")

  def __getstate__(self):
    state = dict(self.__dict__)
    del state["video"]
    return state

  def __setstate__(self, state):
    name = state.get("name")
    screen_calibration = state["screen_calibration"]
    delegate = state["_delegate"]
    self.__init__(name, delegate, {}, screen_calibration)
    self.__dict__.update(state)
