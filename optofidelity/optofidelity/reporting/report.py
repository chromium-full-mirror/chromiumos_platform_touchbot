# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Report class implementation."""
from contextlib import contextmanager
import os
import shutil

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from safetynet import Optional, Tuple, TypecheckMeta
import numpy as np
import skimage.color

from optofidelity.benchmark import (AggregateResults, BenchmarkResults,
                                    DrawEventLatencySeries)
from optofidelity.detection import (Event, LEDEvent, ScreenCalibration,
                                    ScreenDrawEvent, Trace)
from optofidelity.videoproc import Canvas, SaveImage, VideoReader
import matplotlib.pyplot as plt

from ._figures import Figure
from ._hist_figure import HistogramFigure, LatencyHistogramFigure
from ._trace_figures import (EventsMeasurementsFigure,
                             LocationMeasurementsFigure, TraceOverviewFigure)

_script_dir = os.path.dirname(os.path.realpath(__file__))
_res_dir = os.path.join(_script_dir, "res")


class Report(object):
  """Generates HTML reports

  These reports include histograms of all measured latency numbers as well
  as a visualization of the generated trace and measurements made.
  The last section shows screenshots of every measured event to assist
  verification of the results.
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, path, xkcd=False, skip_images=False):
    """
    :param str path: Path to folder in which to store report
    :param bool xkcd: Give report more authority
    """
    self.path = path
    self.data_path = os.path.join(self.path, "report_data")
    if not os.path.exists(self.data_path):
      os.makedirs(self.data_path)
    self.html_filename = os.path.join(self.path, "report.html")
    self._xkcd = xkcd
    self._skip_images = skip_images

  def _RenderTemplate(self, filename, variables, results):
    """Generate target html file from template.

    :type filename: str
    :type variables: dict
    :type results: BenchmarkResults
    """
    def FormatTime(frame_index):
      return "%.2f ms" % (frame_index * results.measurements.ms_per_frame)

    env = Environment(loader=FileSystemLoader(_res_dir),
                      undefined=StrictUndefined)
    env.filters['FormatTime'] = FormatTime
    env.filters['mean'] = np.mean
    env.filters['std'] = np.std
    template = env.get_template(filename)

    common_variables = {
      "benchmark_name": results.benchmark_name,
      "metadata": results.metadata,
      "error": results.error,
      "data_dir": "report_data",
      "xkcd": self._xkcd
    }
    common_variables.update(variables)

    html = template.render(**common_variables)
    with open(self.html_filename, "w") as file:
      file.write(html)

  def _SaveFigure(self, figure, filename):
    """Save figure with and without legend.

    :type figure: Figure
    :type filename: str
    """
    path = os.path.join(self.data_path, filename)
    if self._skip_images:
      open(path + ".png", "w").close()
      open(path + "_legend.png", "w").close()
      return

    figure.Save(path + ".png", False)
    figure.Save(path + "_legend.png", True)

  def _CopyResources(self):
    """Copy required resource files to target folder."""
    def _PrepareDir(path):
      if not os.path.exists(path):
        os.makedirs(path)
    _PrepareDir(os.path.join(self.data_path, "css"))
    _PrepareDir(os.path.join(self.data_path, "js"))

    def _CopyResource(local_name, target_name):
      local_file = os.path.join(_res_dir, local_name)
      target_file = os.path.join(self.data_path, target_name)
      if os.path.isdir(local_file):
        if os.path.exists(target_file):
          shutil.rmtree(target_file)
        shutil.copytree(local_file, target_file)
      else:
        shutil.copy(local_file, target_file)
    _CopyResource("style.css", "css/style.css")
    _CopyResource("materialize/css/materialize.min.css",
                 "css/materialize.min.css")
    _CopyResource("materialize/js/materialize.min.js",
                 "js/materialize.min.js")
    _CopyResource("materialize/font", "font")

  @contextmanager
  def _XKCDMode(self):
    if self._xkcd:
      with plt.xkcd():
        yield
    else:
      yield

class BenchmarkReport(Report):
  """Generates Benchmark HTML reports

  These reports include histograms of all measured latency numbers as well
  as a visualization of the generated trace and measurements made.
  The last section shows screenshots of every measured event to assist
  verification of the results.
  """

  REFERENCE_LINE_COLOR = (76.0/255.0, 175.0/255.0, 80.0/255.0, 1.0)
  """Color of the reference line in screenshots in a BGRA tuple"""

  def GenerateReport(self, results, trace, screen_calibration, video,
                     additional_links=[]):
    """ Generates a full HTML report.

    If a video is not specified this method will skip the screenshot generation.

    :type results: BenchmarkResults
    :type trace: Trace
    :type screen_calibration: Optional[ScreenCalibration]
    :type video: Optional[VideoReader]
    """
    link_list = [
      ("Log", "log.txt"),
      ("Raw Results", "results.txt"),
      ("Trace", "trace.txt"),
      ("Video", "video.avi"),
    ]
    link_list.extend(additional_links)

    variables = {
      "measurements": results.measurements,
      "link_list": link_list
    }
    self._RenderTemplate('benchmark.html', variables, results)

    with self._XKCDMode():
      self._GenerateHistograms(results)
      self._GenerateTraceFigures(trace, results)
    if video:
      self._GenerateSnapshots(results, screen_calibration, video)
    self._CopyResources()

  def _GenerateHistograms(self, results):
    """Generate a histogram figure for each measurement ID.

    :type results: BenchmarkResults
    """
    msrmnts = results.measurements
    for series_name, series_info in msrmnts.series_infos.iteritems():
      pass_values = dict((pass_num, pass_msrmnts[series_name].values)
                         for pass_num, pass_msrmnts in msrmnts.iteritems())
      if series_info.units == "ms":
        figure = LatencyHistogramFigure(460, 460)
        figure.PlotOverviewHistogram(pass_values, "Pass")
      elif series_info.units == "%":
        figure = HistogramFigure(460, 460, "%", 0, 1)
        figure.PlotOverviewHistogram(pass_values, "Pass")
      else:
        raise ValueError("Unknown series unit '%s'" % series_info.units)
      self._SaveFigure(figure, "%s_histogram" % series_name)

      for pass_num, pass_msrmnts in msrmnts.iteritems():
        series = pass_msrmnts[series_name]
        figure = LatencyHistogramFigure(460, 460)
        figure.PlotPassHistogram(series.pass_num, series.values)
        filename = "pass_%d_%s_histogram" % (pass_num, series_name)
        self._SaveFigure(figure, filename)

  def _GenerateTraceFigures(self, trace, results):
    """Generate trace figures.

    One overview trace figure and one showing details on measurements for each
    pass.
    :type results: BenchmarkResults
    :type trace: Trace
    """
    ms_per_frame = results.measurements.ms_per_frame
    overview_figure = TraceOverviewFigure(980, 320, 140, ms_per_frame)
    overview_figure.PlotTrace(trace)

    msrmnts = results.measurements
    for pass_num, pass_msrmnts in msrmnts.iteritems():
      begin_time, end_time = pass_msrmnts.begin_time, pass_msrmnts.end_time
      overview_figure.AddRangeMarker("Pass %d" % pass_num, begin_time, end_time)

      if trace.HasEventTypes(LEDEvent) or trace.HasEventTypes(ScreenDrawEvent):
        figure = EventsMeasurementsFigure(980, 140, 140, ms_per_frame)
      else:
        figure = LocationMeasurementsFigure(980, 320, 140, ms_per_frame)

      figure.PlotTrace(trace)
      figure.PlotMeasurements(pass_msrmnts.values())
      figure.SetLimits(begin_time, end_time)
      self._SaveFigure(figure, "pass_%d_trace" % pass_num)
    self._SaveFigure(overview_figure, "trace_overview")

  def _GenerateSnapshots(self, results, screen_calibration, video):
    """Pull video snapshots for each measurement event.

    For all events, except LEDEvents the video frame will be transformed into
    a normalized, screen space image for better visualization of results.
    All location based events will also show a marker where the measurement
    was made.
    For each snapshot the previous frame is also stored.

    :type results: BenchmarkResults
    :type screen_calibration: Optional[ScreenCalibration]
    :type video: VideoReader
    """
    msrmnts = results.measurements
    all_series = (series for pass_msrmnts in msrmnts.values()
                         for series in pass_msrmnts.values())
    for series in all_series:
      if not isinstance(series, DrawEventLatencySeries):
        continue
      for i, msrmnt in enumerate(series):
        def SaveFrames(basename, event, time):
          path = os.path.join(self.data_path, basename)
          self._SaveFrame(path + "_prev.png", time - 1, event, screen_calibration,
                          video)
          self._SaveFrame(path + ".png", time, event, screen_calibration, video)

        basename = "%s_%d_%d" % (series.series_name, series.pass_num, i)
        SaveFrames("%s_input" % basename, msrmnt.input_event,
                   msrmnt.input_event.uncalib_time)
        SaveFrames("%s_output_start" % basename, msrmnt.output_event,
                   msrmnt.output_event.start_time)
        SaveFrames("%s_output" % basename, msrmnt.output_event,
                   msrmnt.output_event.time)

  def _SaveFrame(self, filename, time, event, screen_calibration, video):
    """Loads frame from video and saves it after processing.

    :type filename: str
    :type time: int
    :type event: Event
    :type screen_calibration: Optional[ScreenCalibration]
    :type video: VideoReader
    """
    if self._skip_images:
      open(filename, "w").close()
      return

    frame = video.FrameAt(time)
    frame = self._ProcessFrame(frame, event, screen_calibration)
    SaveImage(filename, frame)

  def _ProcessFrame(self, frame, event, screen_calibration):
    """Transforms frames into screen space and adds location marker.

    :param np.ndarray frame: Input grayscale image.
    :type event: Event
    :type screen_calibration: Optional[ScreenCalibration]
    :returns np.ndarray: The processed RGBA image.
    """
    if isinstance(event, LEDEvent) or screen_calibration is None:
      result = skimage.color.gray2rgb(frame)
    else:
      screen_space = screen_calibration.CameraToScreenSpace(frame)
      screen_space = screen_calibration.NormalizeFrame(screen_space)

      canvas = Canvas.FromShape(screen_space.shape)
      if event.location is not None:
        canvas.DrawVLine(self.REFERENCE_LINE_COLOR, int(event.location))
      result = canvas.BlendWithImage(skimage.color.gray2rgb(screen_space))
    return skimage.transform.resize(result, (240, 420))

class AggregateReport(Report):
  def GenerateReport(self, aggregate_results):
    """ Generates a report of aggregated results.

    The report provides an overview of multiple repetitions of a benchmark,
    showing the aggregated histograms as well as histograms for each repetition.

    :type aggregate_results: AggregateResults
    """
    variables = {
      "measurements": aggregate_results.measurements,
      "repetitions": aggregate_results.repetitions,
    }
    self._RenderTemplate('aggregate.html', variables, aggregate_results)
    with self._XKCDMode():
      self._GenerateHistograms(aggregate_results)
    self._CopyResources()

  def _GenerateHistograms(self, aggregate_results):
    """Generate a histogram figure for each measurement ID and repetition

    :type aggregate_results: AggregateResults
    """
    msrmnts = aggregate_results.measurements
    for series_name, series_info in msrmnts.series_infos.iteritems():

      for rep_num, rep_msrmnts in msrmnts.iteritems():
        if series_info.units == "ms":
          figure = LatencyHistogramFigure(460, 460)
        elif series_info.units == "%":
          figure = HistogramFigure(460, 460, "%", 0, 1)
        else:
          raise ValueError("Unknown series unit '%s'" % series_info.units)

        primary_plot = np.asarray(rep_msrmnts.SummarizeValues(series_name))
        figure.PlotPrimary(primary_plot, "Repetition #%02d" % rep_num,
                           figure.GetRotationColor(rep_num))
        self._SaveFigure(figure, "rep%02d_%s_histogram" % (rep_num, series_name))

      rep_values = dict((rep_num, rep_msrmnts.SummarizeValues(series_name))
                        for rep_num, rep_msrmnts in msrmnts.iteritems())

      figure = LatencyHistogramFigure(460, 460)
      figure.PlotOverviewHistogram(rep_values, "Repetition")
      self._SaveFigure(figure, "%s_histogram" % series_name)
