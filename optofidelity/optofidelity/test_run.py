# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""" Classes pulling together all functionality to run and store tests.

Each TestRun will perfom multiple repetitions of a test, wheres each test
may do multiple passes (e.g. drawing left to right, then right to left).
All results are collected in the TestRunMeasurements class.

TestRuns can be saved and loaded from disk to allow debugging.
"""
from collections import OrderedDict, defaultdict
from contracts import contract
import cPickle as pickle
import numpy as np
import os
import shutil
import time

from optofidelity.system import TestApp, CameraCalibration
from optofidelity.detection import VideoProcessor, Frame
from optofidelity.videoproc import VideoWriter, FileVideoReader

class Measurement(object):
  def __init__(self, subject_name, class_name, repetition_name, pass_name,
               measurement_id, measurement_number, input_event, output_event,
               is_calibration):
    self.subject_name = subject_name
    self.class_name = class_name
    self.repetition_name = repetition_name
    self.pass_name = pass_name
    self.measurement_id = measurement_id
    self.measurement_number = measurement_number
    self.input_event = input_event
    self.output_event = output_event
    self.is_calibration = is_calibration


class MeasurementList(list):
  """Collection to store a list of measurement.

  While being a standard python list of Measurement object, this list type
  allows measurements specific information to be extracted and provides
  helper methods to iterate over measurements grouped by certain fields.
  """
  @property
  def begin_time(self):
    return min([m.input_event.time for m in self])

  @property
  def end_time(self):
    return max([m.output_event.time for m in self])

  @property
  def latencies(self):
    return np.asarray([m.output_event.time - m.input_event.time
                       for m in self if not m.is_calibration])

  @property
  def has_draw_start(self):
    return np.all([m.output_event.start_time is not None for m in self])

  @property
  def draw_start_latencies(self):
    return np.asarray([m.output_event.start_time - m.input_event.time
                       for m in self if not m.is_calibration])

  @property
  def mean(self):
    return np.mean(self.latencies)

  @property
  def draw_start_mean(self):
    return np.mean(self.draw_start_latencies)

  @property
  def std(self):
    return np.std(self.latencies)

  @property
  def draw_start_std(self):
    return np.std(self.draw_start_latencies)

  @property
  def is_calibration(self):
    return len([m for m in self if m.is_calibration]) > 0

  @property
  def event_types(self):
    types = []
    for measurement in self:
      types.append(type(measurement.input_event))
      types.append(type(measurement.output_event))
    return set(types)

  @property
  def calibration(self):
    calibrations = list([m for m in self if m.is_calibration])
    return calibrations[0] if calibrations else None

  def IterByID(self, include_calib=False):
    return self._IterBy(lambda m: m.measurement_id, include_calib)

  def IterByPass(self, include_calib=True):
    return self._IterBy(lambda m: m.pass_name, include_calib)

  def IterByRepetition(self, include_calib=True):
    return self._IterBy(lambda m: m.repetition_name, include_calib)

  def IterBySubject(self, include_calib=True):
    return self._IterBy(lambda m: m.subject_name, include_calib)

  def IterByClass(self, include_calib=True):
    return self._IterBy(lambda m: m.class_name, include_calib)

  def _IterBy(self, key, include_calib=True):
    res = defaultdict(MeasurementList)
    for measurement in self:
      if not measurement.is_calibration or include_calib:
        res[key(measurement)].append(measurement)
    return res.iteritems()

  def __str__(self):
    lines = []
    def add_line(indent, fmt, *params):
      lines.append("  " * indent + (fmt % params))

    for subject_name, subject_measurements in self.IterBySubject():
      add_line(0, "Subject %s:", subject_name)
      for pass_name, pass_measurements in subject_measurements.IterByPass():
        add_line(1, "Pass %s:", pass_name)
        for id, measurements in pass_measurements.IterByID():
          add_line(2, "%s: %s", id, str(measurements.latencies))
          if measurements.has_draw_start:
            start_latency_list = str(measurements.draw_start_latencies)
            add_line(2, "%s(start): %s", id, start_latency_list)
    return "\n".join(lines)


class MeasurementsCollector(object):
  """Helper class to collect measurements from TestClass implementations."""
  def __init__(self, class_name, subject_name, repetition_name):
    self.measurement_list = MeasurementList()
    self.class_name = class_name
    self.subject_name = subject_name
    self.repetition_name = repetition_name
    self.counter = 0

  def Add(self, measurement_id, input_event, output_event, pass_name=0,
          is_calibration=False):
    measurement_number = self.counter
    self.counter += 1
    measurement = Measurement(self.subject_name, self.class_name,
                              self.repetition_name, pass_name, measurement_id,
                              measurement_number, input_event, output_event,
                              is_calibration)
    self.measurement_list.append(measurement)

  def AddCalibration(self, input_event, output_event, pass_name=0):
    self.Add("Calibration", input_event, output_event, pass_name, True)


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

  def ProcessTrace(self, trace, measurements, debug):
    """Process the trace and put measurements into the results object

    The trace is being generated from the video returned by ExecuteTest. This
    method calculates the measurements from the trace and passes them into
    the measurements.Add()
    """
    raise NotImplementedError()


class TestRepetition(object):
  """Holds data for a single test repetition."""
  def __init__(self, test_run, name):
    self.test_run = test_run
    self.name = name
    self.test_video = None
    self.test_trace = None
    self.error = None
    self.framerate = None

  @property
  def test_video_file(self):
    assert self.test_run.path, "Save TestRun first"
    filename = "%s.avi" % self.name
    return os.path.join(self.test_run.path, filename)

  def RecordTestVideo(self, system):
    """Instruct the robot and record this test's video."""
    dut = system[self.test_run.dut_name]
    app = dut[self.test_run.app_name]
    camera = system.camera
    self.framerate = camera.fps
    self.test_video = self.test_run.test_class.ExecuteTest(app, dut, camera)
    return self.test_video

  def ProcessTestVideo(self, debug):
    """Process the recorded video into a trace."""
    assert self.test_video, "No test video"
    assert self.test_run.calibration, "No calibrated test area"

    if debug["perf"]:
      start_t = time.time()
      self.test_video.perf_enabled = True

    processor = VideoProcessor(self.test_run.calibration, debug)
    self.test_run.test_class.InitializeProcessor(processor)
    processor.Initialize(self.test_video, debug=debug)
    self.test_trace = processor.ProcessVideo(self.test_video, debug=debug)

    if debug["perf"]:
      transfer_time = np.mean(self.test_video.transfer_times)
      delta_t = (time.time() - start_t)
      delta_t_per_frame = delta_t / self.test_video.num_frames
      print "PERF: Processing: %f s" % delta_t
      print "PERF:             %f ms / frame" % (delta_t_per_frame * 1000)
      print "PERF: Transfer: %f ms / frame" % (transfer_time * 1000)

    return self.test_trace

  def ProcessTestTrace(self, debug):
    """Process the trace into latency measurements."""
    assert self.test_trace, "No test trace"
    start_t = time.time()
    if debug["trace"]:
      print self.test_trace
    test_class = self.test_run.test_class
    collector = MeasurementsCollector(self.test_run.test_class.name,
                                      self.test_run.subject_name, self.name)
    test_class.ProcessTrace(self.test_trace, collector, debug["trace"])
    if debug["perf"]:
      print "PERF: Trace processing: %f s" % (time.time() - start_t)
    return collector.measurement_list

  def GetFrame(self, frame_num):
    raw = self.test_video.FrameAt(frame_num)
    return Frame(raw, None, self.test_run.calibration, frame_num)

  def LoadTestVideo(self):
    """Load video from file if present."""
    if os.path.exists(self.test_video_file):
      self.test_video = FileVideoReader(self.test_video_file)
    return self

  def SaveTestVideo(self):
    """Download the video from the camera to the disk."""
    assert self.test_video, "No test video"
    print "Saving test video"
    self.test_video = self.test_run._SaveVideo(self.test_video,
                                               self.test_video_file)
    return self.test_video

  def __getstate__(self):
    return (
        self.test_run,
        self.name,
        self.test_trace,
        self.framerate
    )

  def __setstate__(self, state):
    (
        self.test_run,
        self.name,
        self.test_trace,
        self.framerate
    ) = state
    self.test_video = None

  def __str__(self):
    return "%s/%s" % (self.test_run.path, self.name)


class TestRun(object):
  """Represents a test execution consisting of multiple repetitions.

  This class manages all data related to a single test run, and allows each
  step of the latency calculation process to be invoked.
  """
  metadata_filename = "metadata.pickle"

  @contract(test_class=TestClass, app=TestApp,
            path="str|None")
  def __init__(self, test_class, app, path=None):
    self.path = path
    self.test_class = test_class
    self.dut_name = app.dut.name
    self.app_name = app.name
    self.subject_name = "%s (%s)" % (self.dut_name, self.app_name)
    self.error = None

    self.calibration = app.calibration
    self.calibration_video = app.calibration.video
    self.led_calibration = None

    self.repetitions = OrderedDict()

    if not os.path.exists(path):
      os.makedirs(path)

  @property
  def metadata_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, self.metadata_filename)

  @property
  def calibration_video_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, "calibration.avi")

  @property
  def calibration_file(self):
    assert self.path, "Save TestRun first"
    return os.path.join(self.path, "calibration.hpf5")

  def AddRepetition(self, name):
    repetition = TestRepetition(self, name)
    self.repetitions[name] = repetition
    return repetition

  def ProcessCalibrationVideo(self, debug):
    self.calibration.Process(debug["calibration"], self.calibration_video)

  def SaveCalibrationVideo(self):
    assert self.calibration_video, "No calibration video"
    print "Saving calibration video"
    self.calibration_video = self._SaveVideo(self.calibration_video,
                                             self.calibration_video_file)

  @classmethod
  def Load(cls, path):
    """Load a TestRun from disk as previously stored with Save."""
    metadata_file = os.path.join(path, cls.metadata_filename)
    if not os.path.exists(metadata_file):
      raise ValueError("No test run data at %s" % path)
    self = pickle.load(open(metadata_file))
    self.path = path
    if os.path.exists(self.calibration_file):
      self.calibration = CameraCalibration.Load(self.calibration_file)
    if os.path.exists(self.calibration_video_file):
      self.calibration_video = FileVideoReader(self.calibration_video_file)
    for repetition in self.repetitions.values():
      repetition.LoadTestVideo()
    return self

  def Save(self, save_as=None):
    """Stores all local data from this test run into a folder."""
    if save_as:
      self.path = save_as
      if not os.path.exists(self.path):
        os.makedirs(self.path)
    pickle.dump(self, open(self.metadata_file, "w"))

  def __getstate__(self):
    self.calibration.Save(self.calibration_file)
    return (
        self.path,
        self.test_class,
        self.dut_name,
        self.app_name,
        self.subject_name,
        self.error,
        self.repetitions,
        self.led_calibration
    )

  def __setstate__(self, state):
    (
        self.path,
        self.test_class,
        self.dut_name,
        self.app_name,
        self.subject_name,
        self.error,
        self.repetitions,
        self.led_calibration
    ) = state
    self.calibration = None
    self.calibration_video = None
    self.test_video = None

  def _SaveVideo(self, video_reader, filename):
    if hasattr(video_reader, "filename"):
      shutil.copy(video_reader.filename, filename)
    else:
      writer = VideoWriter(filename)
      writer.Write(video_reader)
    return FileVideoReader(filename)
