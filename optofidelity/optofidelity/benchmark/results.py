# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of BenchmarkResults

Includes definition of MeasurementList, which is a list of Measurement
instances.
"""
from collections import defaultdict

from safetynet import Optional, TypecheckMeta
import numpy as np

from optofidelity.detection import Event


class Measurement(object):
  __metaclass__ = TypecheckMeta

  def __init__(self, pass_num, measurement_id, measurement_number,
               input_event, output_event):
    """A single measurement from an input event to an output event.

    :param int pass_num: Number of the measurement pass. (i.e. some
           benchmarks do a left to right, then right to left pass.)
    :param str measurement_id: Identifier of the type of measurement.
    :param int measurement_number: Each measurement has an incrementing number
           assigned to it to identify it.
    :param Event input_event: Input event at which the measurement starts.
    :param Event output_event: Output event at which the measurement ends.
    """
    self.pass_num = pass_num
    self.measurement_id = measurement_id
    self.measurement_number = measurement_number
    self.input_event = input_event
    self.output_event = output_event

  def __str__(self):
    args = (self.measurement_id, self.measurement_number, self.pass_num,
            self.input_event, self.output_event)
    return "(%s #%2d pass=%s, in=%s, out=%s)" % args

  def __repr__(self):
    return str(self)

class MeasurementList(list):
  """Collection to store a list of measurement.

  While being a standard python list of Measurement object, this list type
  allows measurements specific information to be extracted and provides
  helper methods to iterate over measurements grouped by certain fields.
  """
  @property
  def begin_time(self):
    """:returns int: time at which the first measurement starts."""
    return min([m.input_event.time for m in self])

  @property
  def end_time(self):
    """:returns int: time at which the last measurement ends."""
    return max([m.output_event.time for m in self])

  @property
  def latencies(self):
    """:returns np.ndarray: array of latencies between input and output"""
    return np.asarray([m.output_event.time - m.input_event.time
                       for m in self])

  @property
  def has_draw_start(self):
    """:returns bool: True if all output events have a draw start time."""
    return np.all([m.output_event.start_time is not None for m in self])

  @property
  def draw_start_latencies(self):
    """:returns np.ndarray: array of latencies between input and the draw start
                of output"""
    return np.asarray([m.output_event.start_time - m.input_event.time
                       for m in self])

  @property
  def mean(self):
    """:returns float: average latency"""
    return np.mean(self.latencies)

  @property
  def draw_start_mean(self):
    """:returns float: average latency when measured to the draw start time."""
    return np.mean(self.draw_start_latencies)

  @property
  def std(self):
    """:returns float: standard deviation of latency"""
    return np.std(self.latencies)

  @property
  def draw_start_std(self):
    """:returns float: standard deviation of latency when measured to the draw
                start time."""
    return np.std(self.draw_start_latencies)

  @property
  def event_types(self):
    """:returns List[type]: List of types of events that appear in
                the measurements."""
    types = []
    for measurement in self:
      types.append(type(measurement.input_event))
      types.append(type(measurement.output_event))
    return set(types)

  def IterByMeasurementID(self):
    """Iterate over measurements grouped by measurement id.

    Yields tuples of a measurement id and a MeasurementList containing the
    measurements with that id.

    :returns Iterable[Tuple[str, MeasurementList]]
    """
    return self._IterBy(lambda m: m.measurement_id)

  def ByMeasurementID(self):
    """Dict of measurements grouped by measurement id.

    :returns Dict[str, MeasurementList]
    """
    return dict(self.IterByMeasurementID())

  def IterByPass(self):
    """Iterate over measurements grouped by pass name.

    Yields tuples of a pass name and a MeasurementList containing the
    measurements in that pass.

    :returns Iterable[Tuple[int, MeasurementList]]
    """
    return self._IterBy(lambda m: m.pass_num)

  def _IterBy(self, key):
    res = defaultdict(MeasurementList)
    for measurement in self:
      res[key(measurement)].append(measurement)
    return res.iteritems()


class BenchmarkResults(object):
  """Results of a benchmark.

  The results include a MeasurementList of measurements made by the benchmark.
  An optional error string describing why the measurement might have failed and
  a list of calibration measurements.
  """
  def __init__(self, subject_name, benchmark_type, metadata):
    self.subject_name = subject_name
    self.benchmark_type = benchmark_type
    self.metadata = metadata
    self.measurement_list = MeasurementList()
    self.ms_per_frame = 1.0
    self.uid = ""
    self.report_url = ""
    self.error = ""
    self._counter = 0

  def InMS(self, frame_index):
    """:returns float: timestamp in milliseconds of the specified frame index.
    """
    return frame_index * self.ms_per_frame

  def AddMeasurement(self, measurement_id, input_event, output_event,
                     pass_num=0):
    """Add a measurement to the results.

    :param str measurement_id: identifier of the type of measurement.
    :param Event input_event: Event at which the measurement starts.
    :param Event output_event: Event at which the measurement ends.
    :param int pass_num: Measurements can be made in multiple passes,
           this field identifies which pass the measurement belongs to.
    """
    measurement_number = self._counter
    self._counter += 1
    measurement = Measurement(pass_num, measurement_id, measurement_number,
                              input_event, output_event)
    self.measurement_list.append(measurement)

  def AddCalibration(self, input_event, output_event, pass_num=0):
    """Add a calibration measurement to the results.

    :param Event input_event: Event at which the calibration measurement starts.
    :param Event output_event: Event at which the calibration measurement ends.
    :param int pass_num: Measurements can be made in multiple passes,
           this field identifies which pass the calibration belongs to.
    """

  def __setstate__(self, state):
    self.__init__(state.get("subject_name", ""),
                  state.get("benchmark_type", ""),
                  state.get("metadata", {}))
    self.__dict__.update(state)

  def __str__(self):
    lines = []
    def add_line(indent, fmt, *params):
      lines.append("  " * indent + (fmt % params))

    for pass_num, pass_measurements in self.measurement_list.IterByPass():
      add_line(1, "Pass %d:", pass_num)
      for id, measurements in pass_measurements.IterByMeasurementID():
        add_line(2, "%s: %s", id, str(measurements.latencies))
        if measurements.has_draw_start:
          start_latency_list = str(measurements.draw_start_latencies)
          add_line(2, "%s(start): %s", id, start_latency_list)
    return "\n".join(lines)


class AggregateResults(BenchmarkResults):
  def __init__(self, subject_name, benchmark_type, metadata):
    super(AggregateResults, self).__init__(subject_name, benchmark_type,
                                           metadata)
    self.repetitions = []

  def AddRepetition(self, results):
    self.repetitions.append(results)
    self.measurement_list = MeasurementList([m for rep in self.repetitions
                                               for m in rep.measurement_list])
