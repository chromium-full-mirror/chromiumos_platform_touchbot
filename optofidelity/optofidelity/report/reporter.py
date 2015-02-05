# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract
from jinja2 import Environment, FileSystemLoader
import cv2

from optofidelity.detection import LEDEvent
from optofidelity.report.figures import TraceFigure, HistogramFigure
from optofidelity.videoproc import Canvas

import numpy as np
import os
import shutil
import skimage.transform as transform


script_dir = os.path.dirname(os.path.realpath(__file__))
res_dir = os.path.join(script_dir, "res")


class Reporter(object):
  location_color = (76.0/255.0, 175.0/255.0, 80.0/255.0)
  ref_location_color = (243.0/255.0, 150.0/255.0, 33.0/255.0)

  def __init__(self, path, led_calib_latency):
    self.path = path

  def GenerateEventImages(self, event, ref_location, repetition, file_basename):
    def GenerateImage(image, location, filename):
      if location is not None:
        canvas = Canvas(image)
        canvas.DrawHLine(self.location_color, location, 0)
        canvas.DrawHLine(self.ref_location_color, ref_location, 0)
        image = canvas.image
      image = transform.resize(image, (240, 426))
      image = (image * 255).astype(np.uint8)
      cv2.imwrite(filename, image)

    def GenerateFrame(time, location, filename, normalizes):
      if normalized:
        prev_image = repetition.GetFrame(time - 1).normalized
        image = repetition.GetFrame(time).normalized
      else:
        prev_image = repetition.GetFrame(time - 1).original
        image = repetition.GetFrame(time).original

      GenerateImage(prev_image, location, filename + "_prev.png")
      GenerateImage(image, location, filename + ".png")

    normalized = not isinstance(event, LEDEvent)
    if event.start_time is not None:
      GenerateFrame(event.start_time, event.location, file_basename + "_start",
                    normalized)
    GenerateFrame(event.time, event.location, file_basename,
                  normalized)

  def GenerateRepetitionReport(self, repetition, measurements):
    data_path = os.path.join(self.path, "report_data", repetition.name)
    if not os.path.exists(data_path):
      os.makedirs(data_path)

    trace = repetition.test_trace
    ms_per_frame = 1000.0 / float(repetition.framerate)

    figure = TraceFigure(trace, 980, 460, ms_per_frame, 0.3)
    figure.PlotTraceOverview(measurements)
    figure.Save(os.path.join(data_path, "trace_overview"))

    for mid, id_measurements in measurements.IterByID():
      figure = HistogramFigure(460, 460, ms_per_frame)
      figure.PlotHistograms(id_measurements)
      figure.Save(os.path.join(data_path, "%s_histogram" % mid))

    for i, (pass_name, pass_measurements) in enumerate(
        measurements.IterByPass()):
      figure = TraceFigure(trace, 980, 460, ms_per_frame, 0.3)
      figure.PlotPassMeasurements(pass_measurements)
      figure.Save(os.path.join(data_path, "pass_%s_trace" % pass_name))

      for mid, id_measurements in pass_measurements.IterByID():
        figure = HistogramFigure(460, 460, ms_per_frame)
        figure.PlotHistograms(id_measurements, color=i)
        filename = "pass_%s_%s_histogram" % (pass_name, mid)
        figure.Save(os.path.join(data_path, filename))

      for measurement in pass_measurements:
        basename = "pass_%s_%s_%d" % (pass_name, measurement.measurement_id,
                                      measurement.measurement_number)
        basename = os.path.join(data_path, basename)

        ref_location = measurement.output_event.location
        self.GenerateEventImages(measurement.input_event, ref_location,
                                 repetition, basename + "_input")
        self.GenerateEventImages(measurement.output_event, ref_location,
                                 repetition, basename + "_output")

    env = Environment(loader=FileSystemLoader(res_dir))
    env.filters['as_ms'] = lambda n: "%.2f ms" % (float(n) * ms_per_frame)
    template = env.get_template('repetition.html')

    variables = {}
    variables["data_dir"] = "report_data/%s" % repetition.name
    variables["test_run"] = repetition.test_run
    variables["repetition"] = repetition
    variables["passes"] = [n for n, m in measurements.IterByPass()]
    variables["measurements"] = measurements

    html = template.render(**variables)
    filename = os.path.join(self.path, repetition.name)
    open(filename + ".html", "w").write(html)

  def CopyResources(self):
    data_path = os.path.join(self.path, "report_data")
    def PrepareDir(path):
      if not os.path.exists(path):
        os.makedirs(path)
    PrepareDir(data_path)
    PrepareDir(os.path.join(data_path, "css"))
    PrepareDir(os.path.join(data_path, "js"))

    def CopyResource(local_name, target_name):
      local_file = os.path.join(res_dir, local_name)
      target_file = os.path.join(data_path, target_name)
      if os.path.isdir(local_file):
        if os.path.exists(target_file):
          shutil.rmtree(target_file)
        shutil.copytree(local_file, target_file)
      else:
        shutil.copy(local_file, target_file)
    CopyResource("style.css", "css/style.css")
    CopyResource("materialize/css/materialize.min.css", "css/materialize.min.css")
    CopyResource("materialize/js/materialize.min.js", "js/materialize.min.js")
    CopyResource("materialize/font", "font")


  def PrintSummary(self, measurement_list):
    """Print summary of measurements."""
    for class_name, class_measurements in measurement_list.IterByClass():
      print "Test Case %s:" % class_name

      for m_id, id_measurements in class_measurements.IterByID():
        print "  Measurement %s:" % m_id
        for subject_name, measurements in id_measurements.IterBySubject():
          draw_start_text = ""
          if measurements.has_draw_start:
            draw_start_text = "draw_start=%.2fms," % measurements.draw_start_mean

          format = "    %s: %.2fms \t (%s std=%.2fms, N=%d)"
          print format % (subject_name, measurements.mean, draw_start_text,
                          measurements.std, len(measurements))
