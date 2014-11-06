# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract
import cPickle as pickle
import numpy as np
import os
import shutil
import time

from optofidelity.system import TestApp, CameraCalibration
from optofidelity.detection import (VideoProcessor,
                                    MultithreadedVideoProcessor)
from optofidelity.videoproc import VideoException, VideoWriter, FileVideoReader


class TestClass(object):
  """Base class for test cases.

  A test case has to perform two actions:
  1. It has to execute the test on the robot, instructing camera and robot
     to perform and record the test.
  2. It has to process the resulting trace, returning the test results.
  """
  name = "Unnamed"
  repetitions = 1

  def InitializeProcessor(self, processor):
    """Configure and add detectors to the processor."""
    pass

  def ExecuteTest(self, app, dut, camera):
    """Execute test on the robot.

    This method has to instruct the camera and robot to perform and record the
    test, then return the recorded video as a VideoReader.
    """
    raise NotImplementedError()

  def ProcessTrace(self, trace):
    """Process the trace and return a dictionary of results.

    The trace is being generated from the video returned by ExecuteTest. This
    method calculates the test results from the trace and should return a
    dictionary describing the test results, such as:
    { "begin_latency": 32, "end_latency": 55 }.
    """
    raise NotImplementedError()


class TestRun(object):
  """Represents a single test execution.

  This class manages all data related to a single test run, and allows each
  step of the latency calculation process to be invoked.
  """
  metadata_filename = "metadata.pickle"

  @contract(test_class=TestClass, app=TestApp, calibration=CameraCalibration,
            path="str|None")
  def __init__(self, test_class, app, calibration, path=None):
    self.path = path
    self.test_class = test_class
    self.dut_name = app.dut.name
    self.app_name = app.name
    self.error = None

    self.calibration = calibration
    self.calibration_video = calibration.video

    self.test_video = None
    self.test_trace = None
    self.test_results = None

    if not os.path.exists(path):
      os.makedirs(path)

  @property
  def metadata_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, self.metadata_filename)

  @property
  def calibration_video_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, "calibration.mov")

  @property
  def calibration_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, "calibration.hpf5")

  @property
  def test_video_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, "test.mov")

  def ProcessCalibrationVideo(self, debug):
    self.calibration.Process(debug["calibration"], self.calibration_video)

  def SaveCalibrationVideo(self):
    assert self.calibration_video, "No calibration video"
    print "Saving calibration video"
    self.calibration_video = self._SaveVideo(self.calibration_video,
                                             self.calibration_video_file)

  def RecordTestVideo(self, system):
    """Instruct the robot and record this test's video."""
    dut = system[self.dut_name]
    app = dut[self.app_name]
    camera = system.camera
    self.test_video = self.test_class.ExecuteTest(app, dut, camera)
    return self.test_video

  def SaveTestVideo(self):
    """Download the video from the camera to the disk."""
    assert self.test_video, "No test video"
    print "Saving test video"
    self.test_video = self._SaveVideo(self.test_video,
                                      self.test_video_file)
    return self.test_video

  def ProcessTestVideo(self, debug):
    """Process the recorded video into a trace."""
    assert self.test_video, "No test video"
    assert self.calibration, "No calibrated test area"

    if debug["perf"]:
      start_t = time.time()
      self.test_video.perf_enabled = True

    if debug["video"]:
      processor = VideoProcessor(self.calibration)
    else:
      processor = MultithreadedVideoProcessor(self.calibration)
    self.test_class.InitializeProcessor(processor)
    processor.Initialize(self.test_video, debug=debug)
    self.test_trace = processor.ProcessVideo(self.test_video, debug=debug)

    if debug["perf"]:
      transfer_time = np.mean(self.test_video.transfer_times)
      print "PERF: Processing: %f s" % (time.time() - start_t)
      print "PERF: Transfer: %f ms / frame" % (transfer_time * 1000)

    return self.test_trace

  def ProcessTestTrace(self, debug):
    """Process the trace into latency results."""
    assert self.test_trace, "No test trace"
    start_t = time.time()
    self.test_results = self.test_class.ProcessTrace(self.test_trace,
                                                     debug["trace"])
    if debug["perf"]:
      print "PERF: Trace processing: %f s" % (time.time() - start_t)

  @classmethod
  def Load(cls, path):
    """Load a TestRun from disk as previously stored with Save."""
    metadata_file = os.path.join(path, cls.metadata_filename)
    if not os.path.exists(metadata_file):
      raise ValueError("No test run data at %s" % path)
    return pickle.load(open(metadata_file))

  def Save(self, save_as=None):
    """Stores all local data from this test run into a folder."""
    if save_as:
      self.path = save_as
      if not os.path.exists(self.path):
        os.makedirs(self.path)
    pickle.dump(self, open(self.metadata_file, "w"))

  def SaveAll(self, save_as=None):
    """Stores all local data as well as videos from the camera."""
    self.Save(save_as)
    if self.calibration_video:
      self.SaveCalibrationVideo()
    if self.test_video:
      self.SaveTestVideo()

  def __getstate__(self):
    self.calibration.Save(self.calibration_file)
    return (
        self.path,
        self.test_class,
        self.dut_name,
        self.app_name,
        self.error,
        self.test_trace,
        self.test_results
    )

  def __setstate__(self, state):
    (
        self.path,
        self.test_class,
        self.dut_name,
        self.app_name,
        self.error,
        self.test_trace,
        self.test_results
    ) = state
    self.calibration = None
    self.calibration_video = None
    self.test_video = None

    if os.path.exists(self.calibration_file):
      self.calibration = CameraCalibration.Load(self.calibration_file)
    if os.path.exists(self.calibration_video_file):
      self.calibration_video = FileVideoReader(self.calibration_video_file)
    if os.path.exists(self.test_video_file):
      self.test_video = FileVideoReader(self.test_video_file)

  def _SaveVideo(self, video_reader, filename):
    if hasattr(video_reader, "filename"):
      shutil.copy(video_reader.filename, filename)
    else:
      writer = VideoWriter(filename)
      writer.Write(video_reader)
    return FileVideoReader(filename)
