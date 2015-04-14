# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Report class implementation."""
import os
import shutil

from jinja2 import Environment, FileSystemLoader
from safetynet import Optional, TypecheckMeta
import numpy as np
import skimage.color
import skimage.io

from optofidelity.detection import (Event, LEDEvent, ScreenCalibration,
                                    ScreenDrawEvent, Trace)
from optofidelity.videoproc import Canvas, VideoReader

from ._figures import Figure
from ._hist_figure import HistogramFigure
from ._trace_figures import (EventsMeasurementsFigure,
                             LocationMeasurementsFigure, TraceOverviewFigure)
from .results import BenchmarkResults

_script_dir = os.path.dirname(os.path.realpath(__file__))
_res_dir = os.path.join(_script_dir, "res")


class Report(object):
  """Generates HTML reports of benchmarks.

  These reports include histograms of all measured latency numbers as well
  as a visualization of the generated trace and measurements made.
  The last section shows screenshots of every measured event to assist
  verification of the results.
  """
  __metaclass__ = TypecheckMeta

  REFERENCE_LINE_COLOR = (76.0/255.0, 175.0/255.0, 80.0/255.0, 1.0)
  """Color of the reference line in screenshots in a BGRA tuple"""

  def __init__(self, path, filename, ms_per_frame):
    """
    :param str path: Path to folder in which to store report
    :param str filename: Filename of report html file
    :type ms_per_frame: float
    """
    self.path = path
    self.data_path = os.path.join(self.path, "report_data")
    if not os.path.exists(self.data_path):
      os.makedirs(self.data_path)
    self.html_filename = os.path.join(self.path, filename)
    self.ms_per_frame = ms_per_frame

  def GenerateReport(self, results, trace, screen_calibration, video):
    """ Generates a full HTML report.

    If a video is not specified this method will skip the screenshot generation.

    :type results: BenchmarkResults
    :type trace: Trace
    :type screen_calibration: Optional[ScreenCalibration]
    :type video: Optional[VideoReader]
    """
    self._GenerateHTMLReport(results)
    self._GenerateHistograms(results)
    self._GenerateTraceFigures(trace, results)
    if video:
      self._GenerateSnapshots(results, screen_calibration, video)
    self._CopyResources()

  def _GenerateHistograms(self, results):
    """Generate a histogram figure for each measurement ID.

    :type results: BenchmarkResults
    """
    msrmnt_list = results.measurement_list
    for mid, id_measurements in msrmnt_list.IterByMeasurementID():
      figure = HistogramFigure(460, 460, self.ms_per_frame)
      figure.PlotOverviewHistogram(id_measurements)
      self._SaveFigure(figure, "%s_histogram" % mid)

  def _GenerateTraceFigures(self, trace, results):
    """Generate trace figures.

    One overview trace figure and one showing details on measurements for each
    pass.
    :type results: BenchmarkResults
    :type trace: Trace
    """
    overview_figure = TraceOverviewFigure(980, 320, 140, self.ms_per_frame)
    overview_figure.PlotTrace(trace, 0.0, 0.0)

    for pass_num, pass_measurements in results.measurement_list.IterByPass():
      overview_figure.AddRangeMarker("Pass %d" % pass_num,
                                     pass_measurements.begin_time,
                                     pass_measurements.end_time)
      event_types = pass_measurements.event_types
      if LEDEvent in event_types or ScreenDrawEvent in event_types:
        figure = EventsMeasurementsFigure(980, 140, 140, self.ms_per_frame)
      else:
        figure = LocationMeasurementsFigure(980, 320, 140, self.ms_per_frame)
      figure.PlotTrace(trace, 0.0, 0.0)
      figure.PlotMeasurements(pass_measurements)
      figure.SetLimits(pass_measurements.begin_time, pass_measurements.end_time)
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
    for msrmnt in results.measurement_list:
      def SaveFrames(basename, event, time):
        path = os.path.join(self.data_path, basename)
        self._SaveFrame(path + "_prev.png", time - 1, event, screen_calibration,
                        video)
        self._SaveFrame(path + ".png", time, event, screen_calibration, video)

      basename = "%d" % msrmnt.measurement_number
      SaveFrames("%s_input" % basename, msrmnt.input_event,
                msrmnt.input_event.time)
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
    frame = video.FrameAt(time - 1)
    frame = self._ProcessFrame(frame, event, screen_calibration)
    skimage.io.imsave(filename, frame)

  def _ProcessFrame(self, frame, event, screen_calibration):
    """Transforms frames into screen space and adds location marker.

    :param np.ndarray frame: Input grayscale image.
    :type event: Event
    :type screen_calibration: Optional[ScreenCalibration]
    :returns np.ndarray: The processed RGBA image.
    """
    if isinstance(event, LEDEvent) or screen_calibration is None:
      return skimage.color.gray2rgb(frame)

    screen_space = screen_calibration.CameraToScreenSpace(frame)
    screen_space = screen_calibration.NormalizeFrame(screen_space)

    canvas = Canvas.FromShape(screen_space.shape)
    if event.location is not None:
      canvas.DrawVLine(self.REFERENCE_LINE_COLOR, event.location)
    return canvas.BlendWithImage(skimage.color.gray2rgb(screen_space))

  def _SaveFigure(self, figure, filename):
    """Save figure with and without legend.

    :type figure: Figure
    :type filename: str
    """
    path = os.path.join(self.data_path, filename)
    figure.Save(path + ".png", False)
    figure.Save(path + "_legend.png", True)

  def _GenerateHTMLReport(self, results):
    """Generate HTML report file from template.

    :type results: BenchmarkResults
    """
    def FormatTime(frame_time):
      return "%.2f ms" % (float(frame_time) * self.ms_per_frame)

    env = Environment(loader=FileSystemLoader(_res_dir))
    env.filters['FormatTime'] = FormatTime
    template = env.get_template('report.html')

    variables = {
      "subject_name": results.subject_name,
      "benchmark_type": results.benchmark_type,
      "metadata": results.metadata, "data_dir": "report_data",
      "measurement_list": results.measurement_list,
      "passes": [p for p, m in results.measurement_list.IterByPass()]
    }

    html = template.render(**variables)
    with open(self.html_filename, "w") as file:
      file.write(html)

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
