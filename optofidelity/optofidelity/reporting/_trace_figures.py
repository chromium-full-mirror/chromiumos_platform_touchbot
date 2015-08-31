# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
import itertools

from safetynet import Any, Dict, Optional
import numpy as np

from optofidelity.benchmark import (DrawEventLatencySeries,
                                    DrawEventStartLatencySeries,
                                    DroppedFramesSeries,
                                    TimeValueMeasurementSeries)
from optofidelity.detection import LEDEvent, ScreenDrawEvent, Trace

from . import _styles
from ._figures import PrimarySecondaryAxesFigure, TimeSeriesAxes


class LatencyAxes(TimeSeriesAxes):
  """Time series axes showing latency measurement results."""

  def AddLatencyPlot(self, latencies, label, color, style):
    """Plot latency measurements.

    :type latencies: np.ndarray
    :type label: str
    :type color: str
    """
    style = style or _styles.DISCRETE_LATENCY_STYLE
    times = self._InMS([t for t, l in latencies])
    latencies = self._InMS([l for t, l in latencies])
    self.mpl_axes.step(times, latencies, label=label, color=color, where="post",
                       **style)

  def UpdateAxes(self):
    """Update axes format.

    These axes have a fixes y-axis scale to make latency plots comparable.
    """
    super(LatencyAxes, self).UpdateAxes()
    self.mpl_axes.set_ylim([_styles.MIN_LATENCY, _styles.MAX_LATENCY])


class MeasurementsAxes(TimeSeriesAxes):
  """Abstract base class for axes that allow measurements to be plotted."""

  def PlotMeasurements(self, measurement_pairs, label, color):
    """Plot measurement pairs.

    The measurements pair are provided as a list of input and output event
    coordinates: ((input_time, input_y), (output_time, output_y))
    Times are integers and provides in camera frames, and y coordinate refers
    to directly to the y axis of these axes.

    :type list measurement_list: list
    :type label: str
    :type color: str
    """
    main_plot = []
    helper_plot = []
    for (in_x, in_y), (out_x, out_y) in measurement_pairs:
      in_x = self._InMS(in_x)
      out_x = self._InMS(out_x)
      main_plot += [(in_x, out_y), (out_x, out_y), (np.nan, np.nan)]
      helper_plot += [(in_x, in_y), (in_x, out_y), (np.nan, np.nan)]

    self.mpl_axes.plot([x for x, y in helper_plot], [y for x, y in helper_plot],
                       color=color, label=label,
                       **_styles.MEASUREMENT_HELPER_STYLE)
    self.mpl_axes.plot([x for x, y in main_plot], [y for x, y in main_plot],
                       color=color, **_styles.MEASUREMENT_STYLE)


class LocationAxes(MeasurementsAxes):
  """Axes visualizing a location trace"""

  def AddLocationPlot(self, locations, style):
    """Plot location time series.

    :type locations: np.ndarray
    :type style: Dict[str, Any]
    """
    if np.all(np.isnan(locations)):
      return
    timestamps = self._InMS(np.arange(len(locations)))
    self.mpl_axes.step(timestamps, locations, where="post", **style)


class EventsAxes(MeasurementsAxes):
  def AddEventsPlot(self, values, offset, style):
    """Plot events time series.

    Since event plots mostly switch between 0 and 1, we add a little offset to
    them for easier visualization.

    :type values: np.ndarray
    :type offset: float
    :type style: Dict[str, Any]
    """
    timestamps = self._InMS(np.arange(len(values)))
    self.mpl_axes.step(timestamps, values + offset, where="post", **style)

  def UpdateAxes(self):
    """Update axes format."""
    super(EventsAxes, self).UpdateAxes()
    self._UpdateEventAxesTicks()

  def _UpdateEventAxesTicks(self):
    """Update y-axis ticks.

    Usually we only observe a single LED, which results in time series plots
    between 0 and 1. However should there be multiple LEDs in this time series
    we might have multiple LEDs on at the same time, i.e. values higher than 1.

    This methods updates ticks and labels to show how many LEDs are on.
    """
    (_, max_value) = self._GetMinMaxValue()

    tick_labels = []
    tick_labels.append((0, "White\nOff"))
    tick_labels.append((1, "Black\n1 On"))
    for i in range(2, int(max_value + 1)):
      tick_labels.append((i, "%d On" % i))

    self.mpl_axes.set_yticks([t for t, l in tick_labels])
    self.mpl_axes.set_yticklabels([l for t, l in tick_labels])


class AbstractTraceFigure(PrimarySecondaryAxesFigure):
  """Abstract base class for all trace figures.

  This class works with an instance of LocationAxes, EventsAxes and LatencyAxes.
  Each figure can only show two of them, so they have to be assigned by the
  implementing classes. Per default, they are all None.
  """

  PLOT_OFFSETS = defaultdict(lambda: 0.0, {
    LEDEvent: -0.05,
    ScreenDrawEvent: +0.05
  })
  """Y-axis offsets for easier visualization of event plots."""

  def __init__(self, width, prim_height, second_height, prim_label,
               second_label):
    """
    :param int width: Width of image in pixels.
    :param int prim_height: Height of primary axes in pixels.
    :param int second_height: Height of secondary axes in pixels.
    :param Optional[str] prim_label: Label of primary y-axis
    :param Optional[str] second_label: Label of secondary y-axis
    """
    super(AbstractTraceFigure, self).__init__(width, prim_height, second_height,
        "Time [ms]", prim_label, second_label)
    self._location_axes = None
    self._events_axes = None
    self._latency_axes = None

  def PlotTrace(self, trace):
    """Plot trace to location and events axes if available.

    :param Trace trace: Trace to plot.
    """
    if self._location_axes:
      self.PlotLocation(trace.line_draw_start, _styles.LINE_DRAW_START_STYLE)
      self.PlotLocation(trace.line_draw_end, _styles.LINE_DRAW_END_STYLE)
      self.PlotLocation(trace.uncalib_finger, _styles.FINGER_STYLE)
      self.PlotLocation(trace.finger, _styles.CALIB_FINGER_STYLE)

    if self._events_axes:
      led_offset = self.PLOT_OFFSETS[LEDEvent]
      self.PlotEvents(trace.uncalib_led, led_offset, _styles.LED_STYLE)
      self.PlotEvents(trace.led, led_offset, _styles.CALIB_LED_STYLE)
      screen_draw_offset = self.PLOT_OFFSETS[ScreenDrawEvent]
      self.PlotEvents(trace.screen_draw_start, screen_draw_offset,
                      _styles.SCREEN_DRAW_START_STYLE)
      self.PlotEvents(trace.screen_draw_end, screen_draw_offset,
                      _styles.SCREEN_DRAW_END_STYLE)
    self.UpdateAxes()

  def PlotMeasurements(self, series_list):
    """Plot measurement and latencies into all available axes.


    """
    color_iter = iter(itertools.cycle(_styles.COLOR_ROTATION))

    for series in series_list:
      location_pairs = []
      events_pairs = []
      latencies = []
      latencies_style = _styles.DISCRETE_LATENCY_STYLE

      if isinstance(series, DrawEventLatencySeries):
        for measurement in series:
          in_ev = measurement.input_event
          out_ev = measurement.output_event
          out_ev_time = out_ev.time
          if isinstance(series, DrawEventStartLatencySeries):
            out_ev_time = out_ev.start_time
          if in_ev.location is not None:
            in_coords = (in_ev.time, in_ev.location)
            out_coords = (out_ev_time, out_ev.location)
            location_pairs += [(in_coords, out_coords)]
          elif in_ev.state is not None:
            events_pairs += [((in_ev.time, 0.5), (out_ev_time, 0.5))]
          latencies += [(out_ev_time, out_ev_time - in_ev.time)]
      elif isinstance(series, DroppedFramesSeries):
        for dropped_time in series.dropped_times:
          latencies += [(dropped_time, 30), (np.nan, np.nan)]
      elif isinstance(series, TimeValueMeasurementSeries):
        for time, value in series:
          latencies += [(time, value)]
        latencies_style = _styles.LATENCY_STYLE
      label = "%s Measurement" % series.series_name
      color = color_iter.next()
      self.PlotLatencies(np.asarray(latencies), label, color, latencies_style)
      self.PlotEventsMeasurements(events_pairs, label, color)
      self.PlotLocationMeasurements(location_pairs, label, color)
      self.UpdateAxes()

  def SetLimits(self, begin_frame, end_frame):
    """Specify start and end time of all axes.

    :param int begin_frame: begin time in camera frames.
    :param int end_frame: end time in camera frames.
    """
    for axes in (self._location_axes, self._events_axes, self._latency_axes):
      if axes:
        axes.SetLimits(begin_frame, end_frame)
        axes.UpdateAxes()

  def UpdateAxes(self):
    """Update axes format.

    This method is to be called after all plotting and setting of limits is
    done.
    """
    for axes in (self._location_axes, self._events_axes, self._latency_axes):
      if axes:
        axes.UpdateAxes()

  def PlotLocation(self, locations, style):
    """Plot location time series.

    :type locations: np.ndarray
    :type style: Dict[str, Any]
    """
    if self._location_axes:
      self._location_axes.AddLocationPlot(locations, style)

  def PlotEvents(self, values, offset, style):
    """Plot events time series.

    :type values: np.ndarray
    :type offset: float
    :type style: Dict[str, Any]
    """
    if self._events_axes:
      self._events_axes.AddEventsPlot(values, offset, style)

  def PlotLatencies(self, latencies, label, color, style=None):
    """Plot latency measurements.

    :type latencies: np.ndarray
    :type label: str
    :type color: str
    """
    if self._latency_axes:
      self._latency_axes.AddLatencyPlot(latencies, label, color, style)

  def PlotEventsMeasurements(self, measurement_pairs, label, color):
    """Plot measurement pairs into events axes.

    :type list measurement_list: list
    :type label: str
    :type color: str
    """
    if self._events_axes:
      self._events_axes.PlotMeasurements(measurement_pairs, label, color)

  def PlotLocationMeasurements(self, measurement_pairs, label, color):
    """Plot measurement pairs into location axes.

    :type list measurement_list: list
    :type label: str
    :type color: str
    """
    if self._location_axes:
      self._location_axes.PlotMeasurements(measurement_pairs, label, color)


class TraceOverviewFigure(AbstractTraceFigure):
  """Trace overview figure showing the location axes above events axes."""

  def __init__(self, width, location_height, events_height, ms_per_frame):
    """
    :param int width: Width of image in pixels.
    :param int location_height: Height of location axes in pixels.
    :param int events_height: Height of events axes in pixels.
    :param float ms_per_frame: milliseconds per high speed camera frame.
    """
    super(TraceOverviewFigure, self).__init__(width, location_height,
        events_height, "Y Location [px]", None)
    self._location_axes = LocationAxes(self.prim_axes, ms_per_frame)
    self._events_axes = EventsAxes(self.second_axes, ms_per_frame)

  def AddRangeMarker(self, range_name, begin_frame, end_frame):
    """Add named marker of a time range.
    """
    self._location_axes.AddVerticalLine(begin_frame, _styles.PASS_MARKER_STYLE)
    self._location_axes.AddVerticalLine(end_frame, _styles.PASS_MARKER_STYLE)
    self._events_axes.AddVerticalLine(begin_frame, _styles.PASS_MARKER_STYLE)
    self._events_axes.AddVerticalLine(end_frame, _styles.PASS_MARKER_STYLE)
    self._location_axes.AddText(begin_frame + (end_frame - begin_frame) / 2,
                               0.0, range_name, _styles.MESSAGE_STYLE)


class EventsMeasurementsFigure(AbstractTraceFigure):
  """Events measurements figure showing events axes above latency axes."""

  def __init__(self, width, events_height, latencies_height, ms_per_frame):
    """
    :param int width: Width of image in pixels.
    :param int events_height: Height of events axes in pixels.
    :param int latencies_height: Height of latencies axes in pixels.
    :param float ms_per_frame: milliseconds per high speed camera frame.
    """
    super(EventsMeasurementsFigure, self).__init__(width, events_height,
        latencies_height, None, "Latency [ms]")
    self._events_axes = EventsAxes(self.prim_axes, ms_per_frame)
    self._latency_axes = LatencyAxes(self.second_axes, ms_per_frame)


class LocationMeasurementsFigure(AbstractTraceFigure):
  """Location measurements figure showing location axes above latency axes."""

  def __init__(self, width, location_height, measurements_height, ms_per_frame):
    """
    :param int width: Width of image in pixels.
    :param int location_height: Height of location axes in pixels.
    :param int latencies_height: Height of latencies axes in pixels.
    :param float ms_per_frame: milliseconds per high speed camera frame.
    """
    super(LocationMeasurementsFigure, self).__init__(width, location_height,
        measurements_height, "Y Location [px]", "Latency [ms]")
    self._location_axes = LocationAxes(self.prim_axes, ms_per_frame)
    self._latency_axes = LatencyAxes(self.second_axes, ms_per_frame)
