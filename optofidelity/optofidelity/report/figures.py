# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from optofidelity.detection import (FingerEvent, LineDrawEvent, ScreenDrawEvent,
                                    LEDEvent)
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
import numpy as np


class Figure(object):
  dpi = 64.0

  left_padding = 48.0
  right_padding = 16.0
  top_padding = 12.0
  bottom_padding = 32.0

  axis_color = "#444444"

  color_rotation = [
    "#FF9800",
    "#9C27B0",
    "#2196F3",
    "#4CAF50",
  ]

  def __init__(self, width=0, height=0):
    self.figure = plt.figure()
    self.Resize(width, height)
    self.axes_list = []

  def Resize(self, width, height):
    self.width = float(width)
    self.height = float(height)
    if self.width and self.height:
      self.figure.set_size_inches(self.width / self.dpi, self.height / self.dpi)

  def ApplyAxesStyle(self, axes):
    for axis in ['top','bottom','left','right']:
      axes.spines[axis].set_color(self.axis_color)
    axes.tick_params(colors=self.axis_color)
    axes.xaxis.label.set_color(self.axis_color)
    axes.yaxis.label.set_color(self.axis_color)

  def CreateSingleAxes(self, x_label, y_label):
    left = self.left_padding / self.width
    bottom = self.bottom_padding / self.height
    width = 1.0 - left - (self.right_padding / self.width)
    height = 1.0 - bottom - (self.top_padding / self.height)
    axes = self.figure.add_axes([left, bottom, width, height])
    if x_label:
      axes.set_xlabel(x_label, labelpad=1)
    if y_label:
      axes.set_ylabel(y_label, labelpad=1)
    self.ApplyAxesStyle(axes)
    self.axes_list.append(axes)
    return axes

  def CreatePrimarySecondaryAxes(self, x_label, prim_label, second_label,
                                 second_ratio=0.25):
    left = self.left_padding / self.width
    width = 1.0 - left - (self.right_padding / self.width)
    bottom = self.bottom_padding / self.height
    height = 1.0 - bottom - (self.top_padding / self.height)

    # Add secondary axes at the bottom
    second_height = second_ratio * height

    second_axes = self.figure.add_axes([left, bottom, width, second_height])
    if x_label:
      second_axes.set_xlabel(x_label, labelpad=4)
    if second_label:
      second_axes.set_ylabel(second_label, labelpad=8)

    # Add primary axes abovve
    prim_bottom = bottom + second_ratio * height
    prim_height = height * (1 - second_ratio)

    prim_axes = self.figure.add_axes([left, prim_bottom, width, prim_height])
    if prim_label:
      prim_axes.set_ylabel(prim_label, labelpad=8)
    prim_axes.tick_params(axis="x", labelbottom="off")

    self.ApplyAxesStyle(prim_axes)
    self.ApplyAxesStyle(second_axes)
    self.axes_list.append(prim_axes)
    self.axes_list.append(second_axes)
    return prim_axes, second_axes

  def Save(self, filename):
    self.figure.savefig(filename + ".png", dpi=self.dpi)
    for axes in self.axes_list:
      axes.legend()
    self.figure.savefig(filename + "_legend.png", dpi=self.dpi)


class HistogramFigure(Figure):
  histogram_style = {
    "color": "#CFD8DC",
    "edgecolor": "#90A4AE",
    "label": "Latency Histogram"
  }
  primary_pdf_color = "#546E7A"

  main_pdf_style = {
    "linewidth": 3,
    "label": "Latency PDF"
  }
  secondary_pdf_style = {
    "linewidth": 2,
    "linestyle": ":",
    "label": "Latency PDF (start)"
  }

  pass_pdf_style = {
    "linewidth": 2,
    "linestyle": "-"
  }

  min_latency = 0
  max_latency = 200


  def __init__(self, width, height, ms_per_frame):
    super(HistogramFigure, self).__init__(width, height)
    self.ms_per_frame = ms_per_frame
    self.axes = self.CreateSingleAxes("Latency [ms]", "Relative Frequency")

  def PlotHistograms(self, measurements, color=None):
    if color is None:
      color = self.primary_pdf_color
    else:
      color = self.color_rotation[(color + 2) % 4]

    def PlotNormalPDF(values, **style):
      xs = np.linspace(self.min_latency, self.max_latency, 240)
      mu = np.mean(values)
      sigma = np.std(values)
      ys = mlab.normpdf(xs, mu, sigma)
      self.axes.plot(xs, ys, **style)

    # Format figure
    self.axes.set_xlim(self.min_latency, self.max_latency)
    self.axes.set_ylim(0, 0.3)
    bins = range(self.min_latency, self.max_latency, 10)

    # Draw histogram bars
    values = measurements.latencies * self.ms_per_frame
    self.axes.hist(values, normed=1, bins=bins, **self.histogram_style)

    # Draw a PDF for each pass
    if len(list(measurements.IterByPass())) > 1:
      for i, (pass_id, pass_measurements) in enumerate(measurements.IterByPass()):
        values = pass_measurements.latencies * self.ms_per_frame
        style = dict(self.pass_pdf_style)
        style["color"] = self.color_rotation[(i + 2) % 4]
        style["label"] = "Pass %s PDF" % pass_id
        PlotNormalPDF(values, **style)

    # Draw overall PDFs
    values = measurements.latencies * self.ms_per_frame
    PlotNormalPDF(values, color=color, **self.main_pdf_style)
    if measurements.has_draw_start:
      values = measurements.draw_start_latencies * self.ms_per_frame
      PlotNormalPDF(values, color=color, **self.secondary_pdf_style)


class TraceFigure(Figure):
  x_axis_padding = 10
  y_axis_padding = 10

  location_plot_height = 0.7
  event_plot_height = 0.3
  latencies_plot_height = 0.3

  min_latency = 0
  max_latency = 200

  finger_style = {
    "color": "#4CAF50",
    "linewidth": 1,
    "linestyle" : "dotted",
    "label": "Finger"
  }
  calib_finger_style = {
    "color": "#4CAF50",
    "linewidth": 2,
    "linestyle" : "solid",
    "label": "Finger (calibrated)"
  }
  line_draw_start_style = {
    "color": "#2196F3",
    "linewidth": 1,
    "linestyle" : "dotted",
    "label": "Line Draw Start"
  }
  line_draw_end_style = {
    "color": "#2196F3",
    "linewidth": 2,
    "linestyle" : "solid",
    "label": "Line Draw End"
  }
  led_style = {
    "color": "#4CAF50",
    "linewidth": 1,
    "linestyle" : "dotted",
    "label": "LEDs"
  }
  calib_led_style = {
    "color": "#4CAF50",
    "linewidth": 2,
    "linestyle" : "solid",
    "label": "LEDs (calibrated)"
  }
  screen_draw_start_style = {
    "color": "#2196F3",
    "linewidth": 1,
    "linestyle" : "dotted",
    "label": "Screen Draw Start"
  }
  screen_draw_end_style = {
    "color": "#2196F3",
    "linewidth": 2,
    "linestyle" : "solid",
    "label": "Screen Draw End"
  }
  measurement_style = {
    "linewidth": 2,
    "linestyle" : "solid",
    "marker": "o",
  }
  measurement_helper_style = {
    "linewidth": 1,
    "linestyle" : "solid",
  }
  pass_style = {
    "linewidth": 2,
    "linestyle" : "dashed",
    "color": "#ff9800"
  }

  def __init__(self, trace, width, height, ms_per_frame, led_calib_latency=0):
    super(TraceFigure, self).__init__(width, height)
    self.overall_height = height
    self.trace = trace

    self.ms_per_frame = ms_per_frame
    self.times = np.asarray(range(trace.end_time + 1)) * ms_per_frame

    # Primary axes plots
    self.finger_plot = trace.finger
    self.line_draw_start_plot = trace.line_draw_start
    self.line_draw_end_plot = trace.line_draw_end

    # Secondary axes plots
    self.led_plot = trace.led - 0.05
    self.calib_led_plot = np.roll(trace.led, int(led_calib_latency)) - 0.05
    self.screen_draw_start_plot = trace.screen_draw_start + 0.05
    self.screen_draw_end_plot = trace.screen_draw_end + 0.05

  def PlotLocationTrace(self, axes, begin_time=None, end_time=None,
                        calib_offset=0):
    if axes is None:
      return

    all_values = []
    def plot(values, style):
      if begin_time is not None and end_time is not None:
        trimmed = values[begin_time:end_time]
        all_values.extend(trimmed[~np.isnan(trimmed)])
      axes.plot(self.times, values, **style)

    if not np.all(np.isnan(self.finger_plot)):
      plot(self.finger_plot, self.finger_style)
      calib_finger_plot = self.finger_plot + calib_offset
      plot(calib_finger_plot, self.calib_finger_style)
    if not np.all(np.isnan(self.line_draw_start_plot)):
      plot(self.line_draw_start_plot, self.line_draw_start_style)
      plot(self.line_draw_end_plot, self.line_draw_end_style)

    if begin_time is not None and end_time is not None:
      axes.set_xlim(begin_time * self.ms_per_frame,
                    end_time * self.ms_per_frame)
      if len(all_values) > 0:
        axes.set_ylim(np.min(all_values) - self.y_axis_padding,
                      np.max(all_values) + self.y_axis_padding)
    else:
      axes.set_xlim(0, self.times[-1])

  def PlotEventsTrace(self, axes, begin_time=None, end_time=None):
    if axes is None:
      return

    # Adjust labeling and Y range of the plot depending on the height of the
    # LED plot.
    max_led_count = max(int(np.max(self.trace.led)), 1)
    ticks = [1, 0]
    labels = ["Black\n1 On", "White\nOff"]
    for i in range(1, max_led_count):
      ticks.append(i + 1)
      labels.append("%d On" % (i + 1))
    axes.set_yticks(ticks)
    axes.set_yticklabels(labels)
    axes.set_ylim(-0.2, (max_led_count + 0.2))

    # Plot LED and screen draw traces
    if not np.all(self.screen_draw_start_plot == 0):
      axes.plot(self.times, self.screen_draw_start_plot,
                **self.screen_draw_start_style)
      axes.plot(self.times, self.screen_draw_end_plot,
                **self.screen_draw_end_style)
    if not np.all(self.led_plot == 0):
      axes.plot(self.times, self.led_plot, **self.led_style)
      axes.plot(self.times, self.calib_led_plot, **self.calib_led_style)

    if begin_time is not None and end_time is not None:
      axes.set_xlim(begin_time * self.ms_per_frame,
                    end_time * self.ms_per_frame)
    else:
      axes.set_xlim(0, self.times[-1])

  def CreateTraceAxes(self, primary, secondary):
    def GetHeightAndLabel(plot_type):
      if plot_type == "latency":
        return self.latencies_plot_height, "Latency [ms]"
      elif plot_type == "location":
        return self.location_plot_height, "Y Location [px]"
      elif plot_type == "event":
        return self.event_plot_height, None

    primary_height, primary_label = GetHeightAndLabel(primary)
    secondary_height, secondary_label = GetHeightAndLabel(secondary)

    height_factor = primary_height + secondary_height
    self.Resize(self.width, self.overall_height * height_factor)

    ratio = secondary_height / height_factor
    return self.CreatePrimarySecondaryAxes("Time [ms]", primary_label,
                                           secondary_label, ratio)

  def PlotTraceOverview(self, measurements):
    location_axes, event_axes = self.CreateTraceAxes("location", "event")
    self.PlotLocationTrace(location_axes)
    self.PlotEventsTrace(event_axes)

    for pass_name, pass_measurements in measurements.IterByPass():
      begin_time = pass_measurements.begin_time * self.ms_per_frame
      end_time = pass_measurements.end_time * self.ms_per_frame
      location_axes.axvline(begin_time, **self.pass_style)
      location_axes.axvline(end_time, **self.pass_style)
      event_axes.axvline(begin_time, **self.pass_style)
      event_axes.axvline(end_time, **self.pass_style)
      location_axes.text(begin_time + (end_time - begin_time) / 2, 0,
                         "Pass %s" % pass_name, ha="center", va="bottom",
                         color=self.axis_color)

  def PlotPassMeasurements(self, measurements):
    location_plot = (FingerEvent in measurements.event_types or
                     LineDrawEvent in measurements.event_types)
    events_plot = (LEDEvent in measurements.event_types or
                   ScreenDrawEvent in measurements.event_types)
    begin_time = measurements.begin_time - self.x_axis_padding
    end_time = measurements.end_time + self.x_axis_padding

    if location_plot and not events_plot:
      plot_axes, latency_axes = self.CreateTraceAxes("location", "latency")
      calib_offset = 0
      if measurements.calibration:
        calib_offset = (measurements.calibration.output_event.location -
                        measurements.calibration.input_event.location)
      self.PlotLocationTrace(plot_axes, begin_time, end_time, calib_offset)
    elif events_plot and not location_plot:
      plot_axes, latency_axes = self.CreateTraceAxes("event", "latency")
      self.PlotEventsTrace(plot_axes, begin_time, end_time)
    else:
      raise ValueError("No measurements to plot")

    def get_coords(event):
      if isinstance(event, FingerEvent):
        return event.time * self.ms_per_frame, event.location
      if isinstance(event, LineDrawEvent):
        return event.time * self.ms_per_frame, event.location
      if isinstance(event, LEDEvent):
        return event.time * self.ms_per_frame, self.calib_led_plot[event.time]
      if isinstance(event, ScreenDrawEvent):
        return (event.time * self.ms_per_frame,
                self.screen_draw_end_plot[event.time])

    # Draw all measurements into the axes.
    for i, (mid, id_measurements) in enumerate(
        measurements.IterByID(include_calib=True)):
      measurements_x = []
      measurements_y = []
      helper_x = []
      helper_y = []
      latencies_x = []
      latencies_y = []
      for measurement in id_measurements:
        in_x, in_y = get_coords(measurement.input_event)
        out_x, out_y = get_coords(measurement.output_event)

        if measurement.is_calibration:
          # Draw only vertical line, since a calibration measures difference
          # in location.
          measurements_x.extend([in_x, in_x, np.nan])
          measurements_y.extend([out_y, in_y, np.nan])

        else:
          # Draw horizontal line connecting both events.
          measurements_x.extend([in_x, out_x, np.nan])
          measurements_y.extend([out_y, out_y, np.nan])

          # Draw vertical helper line from the horizontal line to the actual
          # event y-height.
          helper_x.extend([in_x, in_x, np.nan])
          helper_y.extend([in_y, out_y, np.nan])

          latencies_x.append(out_x)
          latencies_y.append(out_x - in_x)

          latency_axes.text(out_x, out_x - in_x + 4,
                            "#%d" % measurement.measurement_number,
                            va="bottom", ha="center",
                            color=self.axis_color)

      color = self.color_rotation[i % 4]
      if helper_x and helper_y:
        plot_axes.plot(helper_x, helper_y, color=color,
                       **self.measurement_helper_style)
      if measurements_x and measurements_y:
        plot_axes.plot(measurements_x, measurements_y, color=color,
                       label="%s Measurement" % mid, **self.measurement_style)

      if latencies_x and latencies_y:
        latency_axes.plot(latencies_x, latencies_y, ":o", color=color,
                          label="%s Latency" % mid)
      latency_axes.set_xlim(begin_time * self.ms_per_frame,
                            end_time * self.ms_per_frame)
      latency_axes.set_ylim(self.min_latency, self.max_latency)
