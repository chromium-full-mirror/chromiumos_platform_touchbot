# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of BenchmarkResults

Includes definition of MeasurementList, which is a list of Measurement
instances.
"""
from abc import abstractmethod, abstractproperty
from collections import defaultdict, namedtuple
import itertools

from safetynet import Optional, TypecheckMeta, List
import numpy as np

from optofidelity.detection import Event


MeasurementSeriesInfo = namedtuple("MeasurementSeriesInfo",
    ("series_name", "series_type", "units", "min_num_samples"))

class MeasurementSeries(list):
  """A series of measurements made in a single pass.

  This is an abstract class which leaves it to the subclass to define the
  type of items in this list. However the subclass has to define the values
  property to return floating point values as results.
  """
  DEFAULT_UNITS = "ms"
  DEFAULT_MIN_NUM_SAMPLES = 100

  __metaclass__ = TypecheckMeta

  def __init__(self, series_name, pass_num, ms_per_frame):
    self.series_name = series_name
    self.pass_num = pass_num
    self.type_name = type(self).__name__
    self.ms_per_frame = ms_per_frame

  def __str__(self):
    return "%s (Pass #%d): %s" % (self.series_name, self.pass_num, self.values)

  @abstractproperty
  def begin_time(self):
    """:returns int: time at which the first measurement starts."""

  @abstractproperty
  def end_time(self):
    """:returns int: time at which the last measurement ends."""

  @abstractproperty
  def values(self):
    """:returns List[float]: values of this series of measurements"""

DrawEventLatencyMeasurement = namedtuple("DrawEventLatencyMeasurement",
                                         ("input_event", "output_event"))

class DrawEventLatencySeries(MeasurementSeries):
  """A series that measures the latency between an input and a draw event."""

  def AddMeasurement(self, input_event, output_event):
    """
    :type input_event: Event
    :type outout_event: Event
    """
    self.append(DrawEventLatencyMeasurement(input_event, output_event))

  @property
  def begin_time(self):
    return min(m.input_event.time for m in self)

  @property
  def end_time(self):
    return max(m.output_event.time for m in self)

  @property
  def values(self):
    return [float(m.output_event.time - m.input_event.time)  * self.ms_per_frame
            for m in self]

class DroppedFramesSeries(MeasurementSeries):
  """Measures the percent of dropped frames assuming a 60Hz refresh rate."""
  DEFAULT_UNITS = "%"
  DEFAULT_MIN_NUM_SAMPLES = 0

  def AddMeasurement(self, draw_event):
    """
    :type draw_event: Event
    """
    self.append(draw_event)

  @property
  def begin_time(self):
    return min(e.time for e in self)

  @property
  def end_time(self):
    return max(e.time for e in self)

  @property
  def dropped_times(self):
    dropped_times = []
    last_time = None
    for event in self:
      if last_time is None:
        last_time = event.time
        continue

      expected_frame = last_time + 5
      while expected_frame < event.time - 1:
        dropped_times.append(expected_frame)
        expected_frame += 5
      last_time = event.time
    return dropped_times

  @property
  def values(self):
    if len(self):
      return [float(len(self.dropped_times)) / float(len(self)) * 100.0]
    return [100.0]


class PassMeasurements(dict):
  """A dictionary of MeasurementSeries made in a single pass.

  This dictionary maps the series name to the instance of that series.
  """

  @property
  def begin_time(self):
    """:returns int: time at which the first measurement starts."""
    return min([s.begin_time for s in self.itervalues()])

  @property
  def end_time(self):
    """:returns int: time at which the last measurement ends."""
    return max([s.end_time for s in self.itervalues()])


class BenchmarkMeasurements(defaultdict):
  """A dictionary of all MeasurementSeries made in one benchmark.

  The dictionary maps a pass number to a PassMeasurements instance, which
  contains the MeasurementSeries made in the benchmark.
  """
  __metaclass__ = TypecheckMeta

  DEFAULT_MIN_NUM_SAMPLES = 100

  def __new__(cls, ms_per_frame=None):
    """
    """
    self = super(BenchmarkMeasurements, cls).__new__(cls)
    self.series_infos = dict()
    self.ms_per_frame = ms_per_frame or 3.33
    return self

  def __init__(self, *args, **kwargs):
    super(BenchmarkMeasurements, self).__init__(PassMeasurements)

  def AddSeriesInfo(self, series_name, series_type, units=None,
                    min_num_samples=None):
    """Register a new type of MeasurementSeries.

    This method has to be called before calling AddSeries with that series_name.

    :param str series_name: Name of the measurement series
    :param type series_type: Type of the series (subclass of MeasurementSeries)
    :param Optional[str] unit: Optional unit for display purposes.
    :param int min_num_samples: Minimum number of samples to collect.
    """
    if units is None:
      units = series_type.DEFAULT_UNITS
    min_num_samples = min_num_samples or series_type.DEFAULT_MIN_NUM_SAMPLES
    self.series_infos[series_name] = MeasurementSeriesInfo(series_name,
        series_type, units, min_num_samples)

  def AddSeries(self, series_name, pass_num=0):
    """Add an empty new series to include measurements.

    :param str series_name: Name of the measurement series as previously
           registered with AddSeriesInfo
    :param Optional[int]: Pass number for this series.
    :returns MeasurementSeries: An instance of series_type for this series_name.
    """
    series_info = self.series_infos[series_name]
    series = series_info.series_type(series_name, pass_num, self.ms_per_frame)
    self[pass_num][series_name] = series
    return series

  def SummarizeValues(self, series_name):
    """Collects all MeasurementSeries.values for the specified series_name.

    This summarizes the values from multiple passes.

    :param str series_name: Name of the measurement series.
    :returns List[float]: List of values.
    """
    series_list = (pass_msrmnts.get(series_name)
                   for pass_msrmnts in self.values()
                   if series_name in pass_msrmnts)
    return [value for series in series_list
                  for value in series.values]

  def __str__(self):
    lines = []
    def add_line(indent, fmt, *params):
      lines.append("  " * indent + (fmt % params))
    add_line(1, "Benchmark Measurements:")
    for pass_num, pass_msrmnts in self.iteritems():
      add_line(2, "Pass %d:", pass_num)
      for series in pass_msrmnts.itervalues():
        add_line(3, "%s: %s", series.series_name, str(series.values))
    return "\n".join(lines)

class AggregateMeasurements(defaultdict):
  """A dictionary of measurements from multiple benchmarks"""
  __metaclass__ = TypecheckMeta

  def __init__(self, type=None):
    """
    :param child_type: ignored. Necessary since during unpickling the
           defaultdict child type is provided as a parameter.
    """
    super(AggregateMeasurements, self).__init__(BenchmarkMeasurements)

  @property
  def series_infos(self):
    """Aggregated series_infos from all BenchmarkMeasurements."""
    return dict((k, v) for benchmark_msrmnts in self.itervalues()
                       for k, v in benchmark_msrmnts.series_infos.iteritems())

  def SummarizeValues(self, series_name):
    """Collects all MeasurementSeries.values for the specified series_name.

    This summarizes the values from multiple benchmarks and passes.

    :param str series_name: Name of the measurement series.
    :returns List[float]: List of values.
    """
    return [value for benchmark_msrmnts in self.itervalues()
                  for value in benchmark_msrmnts.SummarizeValues(series_name)]

  def __str__(self):
    lines = []
    def add_line(indent, fmt, *params):
      lines.append("  " * indent + (fmt % params))
    add_line(1, "Aggregate Measurements:")
    for series_name in self.series_infos:
      add_line(2, "%s: %s", series_name, self.SummarizeValues(series_name))
    return "\n".join(lines)

class Measurement(object):
  """For backwards compability to older pickle files."""

class MeasurementList(list):
  """For backwards compability to older pickle files."""


class BenchmarkResults(object):
  """Results of a benchmark.

  The results include a MeasurementList of measurements made by the benchmark.
  An optional error string describing why the measurement might have failed and
  a list of calibration measurements.
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, subject_name, benchmark_type, metadata):
    self.subject_name = subject_name
    self.benchmark_type = benchmark_type
    self.metadata = metadata

    self.uid = ""
    self.report_url = ""
    self.error = ""
    self._counter = 0
    self.measurements = None

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
    old_list = state.get("measurement_list", None)
    if old_list:
      self.measurements = BenchmarkMeasurements(state.get("ms_per_frame"))
      for item in old_list:
        series_name = item.measurement_id
        pass_num = item.pass_num

        if series_name not in self.measurements.series_infos:
          self.measurements.AddSeriesInfo(series_name,
                                          DrawEventLatencySeries)

        if series_name not in self.measurements[pass_num]:
          self.measurements.AddSeries(series_name, pass_num)

        series = self.measurements[pass_num][series_name]
        series.AddMeasurement(item.input_event, item.output_event)
    self.__dict__.update(state)

  def __str__(self):
    lines = []
    def add_line(indent, fmt, *params):
      lines.append("  " * indent + (fmt % params))
    def add_field(field_name):
      add_line(1, "%s: %s", field_name, str(getattr(self, field_name)))

    add_line(0, "%s/%s Benchmark Results", self.subject_name,
             self.benchmark_type)

    add_line(1, "metadata:")
    for key, value in self.metadata.iteritems():
      add_line(2, "%s: %s", key, value)

    add_field("uid")
    add_field("report_url")
    add_field("error")

    if self.measurements:
      lines.append(str(self.measurements))
    return "\n".join(lines)


class AggregateResults(BenchmarkResults):
  def __init__(self, subject_name, benchmark_type, metadata):
    super(AggregateResults, self).__init__(subject_name, benchmark_type,
                                           metadata)
    self.repetitions = []
    self.measurements = AggregateMeasurements()

  def AddRepetition(self, results):
    self.repetitions.append(results)
    self.measurements[len(self.repetitions) - 1] = results.measurements
