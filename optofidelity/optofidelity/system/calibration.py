# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import h5py
import numpy as np
import skimage.morphology as morphology
import skimage.transform as transform
import tempfile


from optofidelity.videoproc import (Canvas, FileVideoReader, Filter, Shape,
                                    VideoException, VideoWriter, Viewer)

class CameraCalibration(object):
  """Detects the test area on a device.

  This class can detect the flashing test area and can rectify images
  to show only this area.
  """

  rect_scaling = 1.2
  """Factor by which the rectified image will be enlarged to make sure we are
     not losing any information due to interpolation."""

  test_area_min_area = 10000
  """Minimum area of a test area in square pixels."""

  test_area_min_solidity = 0.9
  """Minimum solidity of the test_area."""

  test_area_closing_kernel = morphology.disk(2)
  """Size of the disk shaped kernel used for the closing operation to close
     any holes in the detected shapes that might be caused by noise."""

  test_area_margin = 4
  """The test area is reduced in size by this margin to account for potential
     camera shake."""

  diff_threshold = 0.5
  """Threshold used on the difference between the on and off image to find
     the test area."""

  out_of_view_edge_pixels = 10
  """How many pixels of the test_area have to be at the edge of the screen
     to consider it being out of view?"""

  brightness_error_margin = 0.1
  """If the normalized brightness exceeds this threshold above 1 or below 0,
     the brightness is considered to be out of range and will cause an error."""

  max_edge_deviation = 0.5
  """When the bezel enters the test_area, the brightness along this edge will
     deviate from others. This threshold describes by how much it can deviate
     before causing an error."""

  diff_unchanged_max_mid_range = 0.01
  """If the mid-range value of a diff image exceeds this value it is considered
     to show no change."""

  reference_min_num_frames = 6
  """Minimum number of frames to use for building a reference frame."""

  min_dynamic_range = 0.5
  """Minimum range between black and white."""

  def __init__(self):
    self.shape = None
    self.rect_transform = None
    self.on_image = None
    self.on_profile = None
    self.off_image = None
    self.off_profile = None

    self.video = None
    self.video_cache_file = None

  def Save(self, filename):
    with h5py.File(filename, "w") as hdf5:
      hdf5.create_dataset("shape", data=self.shape.mask)
      hdf5.create_dataset("on_image", data=self.on_image)
      hdf5.create_dataset("on_profile", data=self.on_profile)
      hdf5.create_dataset("off_image", data=self.off_image)
      hdf5.create_dataset("off_profile", data=self.off_profile)

  @classmethod
  def Load(self, filename):
    with h5py.File(filename, "r") as hdf5:
      test_area = CameraCalibration()
      test_area.shape = Shape(mask=hdf5["shape"][()])
      test_area.on_image = hdf5["on_image"][()]
      test_area.on_profile = hdf5["on_profile"][()]
      test_area.off_image = hdf5["off_image"][()]
      test_area.off_profile = hdf5["off_profile"][()]
    test_area.rect_transform = test_area.EstimateRectTransform()
    return test_area

  def Calibrate(self, app, camera, debug):
    self.RecordVideo(app, camera)
    self.Process(debug)

  def CacheVideo(self):
    """Download video from the camera to a temporary file."""
    self.video_cache_file = tempfile.NamedTemporaryFile()
    print "Downloading calibration video"
    writer = VideoWriter(self.video_cache_file.name)
    writer.Write(self.video)
    self.video = FileVideoReader(self.video_cache_file.name)

  def RecordVideo(self, app, camera):
    """Record calibration video on the app using the specified camera."""
    camera.PrepareRecording(60)
    app.EnterPage(app.PAGE_FLASH)
    app.dut.ClearScreen()
    camera.Trigger()
    camera.WaitUntilReady()
    app.ExitPage()
    self.video = camera.GetVideoReader()

  def EstimateRectTransform(self):
    """Estimates transformation from rectified device screen to video frame.

    Since transform.warp is doing inverse transformations, this matrix
    transform object can be used to rectify the screen in the video frame.
    """
    # Approximate rectangle from screen shape.
    dest_coords = self.shape.ApproximatePolygon(4)
    # Coords for transforms are x/y, when indexing y/x. So we have to switch.
    dest_coords = dest_coords[:, ::-1]

    # Coordinates in target image. Slightly inflates size so we are not losing
    # any information during warping.
    height = int(self.shape.height * self.rect_scaling)
    width = int(self.shape.width * self.rect_scaling)
    source_coords = np.array((
        (0, 0),
        (width, 0),
        (width, height),
        (0, height)
    ))
    tform = transform.ProjectiveTransform()
    tform.estimate(source_coords, dest_coords)
    return tform

  def Rectify(self, image):
    """Rectify the device screen from a video frame.

    The resulting image will show only the screen, warped to be rectangular.
    """
    height = int(self.shape.height * self.rect_scaling)
    width = int(self.shape.width * self.rect_scaling)
    res = transform.warp(image, self.rect_transform,
                         output_shape=(height, width))
    return res.astype(image.dtype)

  def Unrectify(self, image=None, coords=None):
    """Reverse rectification from device screen image into a video frame.

    The resulting image will show only the screen, warped to be rectangular.
    """
    if image is not None:
      res = transform.warp(image, self.rect_transform.inverse,
                           output_shape=self.shape.mask.shape)
      return res.astype(image.dtype)
    if coords is not None:
      res = self.rect_transform(coords)
      return res[0, 0], res[0, 1]

  def FindReferenceFrames(self, video_reader, debug=False):
    """Find black and white reference frames in a video of the flashing screen.

    This method averages multiple frames of the video showing the black and
    white screen, returning a black and white reference frame.

    Args:
      video_reader: A VideoReader instance.
      debug: A ProcessorDebugger instance.
    """
    ref_images = []
    with video_reader.PrefetchEnabled():
      frames = video_reader.Frames()

      # Accumulator to calculate mean images.
      i, prev_frame = frames.next()
      mean_accum = np.zeros(prev_frame.shape)
      mean_accum_num = 0

      for i, frame in frames:
        # Calculate the mid-range value of the inter-frame difference.
        # This reliably describes the general direction of change.
        diff = frame - prev_frame
        midrange = Filter.StableMidRange(diff)

        if np.abs(midrange) < self.diff_unchanged_max_mid_range:
          # Add frame to accumulator
          mean_accum += frame
          mean_accum_num += 1
        else:
          # The screen is in the process of switching colors.
          if mean_accum_num > self.reference_min_num_frames:
            # We collected enough samples for a solid reference image.
            ref_images.append(mean_accum / mean_accum_num)
            if len(ref_images) >= 2:
              break
          # Reset mean accumulator
          mean_accum_num = 0
          mean_accum = np.zeros(prev_frame.shape)

        if debug:
          print i, midrange, mean_accum_num
          Viewer.VideoFrame(0.5 + diff)
        prev_frame = frame

    # Add the last accumulation in case we don't have enough reference images
    if mean_accum_num > self.reference_min_num_frames and len(ref_images) < 2:
      ref_images.append(mean_accum / mean_accum_num)

    if len(ref_images) < 2:
      raise VideoException("Cannot find flashing screen")

    # Return (white_ref, black_ref)
    if np.mean(ref_images[0]) > np.mean(ref_images[1]):
      return ref_images[0], ref_images[1]
    else:
      return ref_images[1], ref_images[0]

  def Process(self, debug, video=None):
    """Process calibration video recorded by RecordVideo."""
    video = video or self.video
    assert video, "No calibration video"

    # Extract information from video frames. We need the following information:
    # Image of the screen off (min average grayscale)
    # Image of the screen on (max average grayscale)
    # And the accumulative difference between frames to find the area that
    # is changing the most.
    on_frame, off_frame = self.FindReferenceFrames(video, debug=debug)
    delta = Filter.Truncate(on_frame - off_frame)

    # Find screen shape
    def is_screen(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.solidity
      return (region.area > self.test_area_min_area and
              region.solidity > self.test_area_min_solidity)
    binary = delta > self.diff_threshold

    margin_kernel = morphology.disk(self.test_area_margin)
    binary = morphology.binary_closing(binary, self.test_area_closing_kernel)
    binary = morphology.binary_erosion(binary, margin_kernel)
    self.shape = Shape.Find(binary, is_screen, required=True, debug=debug)

    # create a 1px rectangle mask along the edge of the video frame
    # if the screen mask overlaps in too many pixels with this rectangle,
    # the screen is probably outside the viewport of the camera.
    width, height = self.shape.mask.shape
    frame_border = np.zeros((width, height), dtype=np.bool)
    frame_border[:, 0] = True
    frame_border[:, height - 1] = True
    frame_border[0, :] = True
    frame_border[width - 1, :] = True
    border_overlap = np.sum(frame_border * self.shape.mask)

    if border_overlap > self.out_of_view_edge_pixels:
      raise VideoException("Screen out of camera view")

    # Estimate rectification transformation
    self.rect_transform = self.EstimateRectTransform()

    # Calculate profile for screen on and off in cropped space
    self.on_image = self.Rectify(on_frame)
    self.off_image = self.Rectify(off_frame)
    self.on_profile = Filter.ExtractProfile(self.on_image)
    self.off_profile = Filter.ExtractProfile(self.off_image)

    # Check dynamic range. We need enough resolution to distinguish shades
    # between black and white during later processing.
    dynamic_range = np.mean(self.on_image - self.off_image)
    if dynamic_range <  self.min_dynamic_range:
      raise VideoException("Not enough dynamic range.")

    if debug:
      res = Canvas(on_frame)
      res.DrawContour(Canvas.BLUE, self.shape)
      Viewer.DebugView(delta=delta,
                       shape=res.image,
                       rectified_on=self.on_image,
                       rectified_off=self.off_image)
    return True

  def NormalizeFrame(self, rectified_frame):
    return (rectified_frame - self.off_image) / (self.on_image - self.off_image)

  def NormalizedBrightness(self, rectified_frame, slice_or_mask=None):
    """Returns normalized average brightness of frame.

    The brightness is normalized to 0 being the average brightness of the
    screen being black and 1 the average brightness of a fully white screen.
    """
    if slice_or_mask is not None:
      mean = np.mean(rectified_frame[slice_or_mask])
      on_mean = np.mean(self.on_image[slice_or_mask])
      off_mean = np.mean(self.off_image[slice_or_mask])
    else:
      mean = np.mean(rectified_frame[:])
      on_mean = np.mean(self.on_image[:])
      off_mean = np.mean(self.off_image[:])
    return (mean - off_mean) / (on_mean - off_mean)

  def VerifyFrame(self, frame, debug=False):
    """Check frame for camera shifts or lighting changes."""
    rectified = self.Rectify(frame)
    width, height = rectified.shape

    # calculate overall mean and mean along screen edges
    mean = self.NormalizedBrightness(rectified)
    top_mean = self.NormalizedBrightness(rectified, np.s_[:, 0])
    left_mean = self.NormalizedBrightness(rectified, np.s_[0, :])
    bottom_mean = self.NormalizedBrightness(rectified, np.s_[:, height - 1])
    right_mean = self.NormalizedBrightness(rectified, np.s_[width - 1, :])
    edge_means = [top_mean, left_mean, bottom_mean, right_mean]

    if debug:
      print "Overall mean:", mean
      print "Edge means:", edge_means

    # The brightness is normalized to the black screen being 0 and the white
    # screen being 1. If the lighting changed, the normalized brightness will
    # be outside the [0, 1] range.
    error_margin = self.brightness_error_margin
    if mean > 1 + error_margin or mean < -error_margin:
      raise VideoException("Lighting changed.")

    # If the bezel shifted into the screen the deviation of the edge means
    # from the overall mean will be strong.
    deviations = np.abs(edge_means - mean)
    if np.any(deviations > self.max_edge_deviation):
      raise VideoException("Camera shifted.")
