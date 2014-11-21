# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
from contracts import contract
import math
import numpy as np
import skimage.measure as measure
import skimage.morphology as morphology

from optofidelity.videoproc.util import Viewer, VideoException
from optofidelity.videoproc.filter import Filter

class Shape(object):
  """Describes a segmented shape in an image.

  The shape is represented by a binary image aka mask, in which pixels
  that are part of the shape are True, all others are False.
  """
  @contract(mask="binary_image")
  def __init__(self, mask, props=None):
    if props is None:
      # Use the mask as a label image, since we only have one region,
      # with label=1.
      all_props = measure.regionprops(mask)
      if len(all_props) != 1:
        raise ValueError("Mask must have a unique region")
      props = all_props[0]

    self.mask = mask
    self.props = props
    self._contour = None

  def WithMargin(self, row_margin, col_margin):
    """Return a shape inflated with an margin.

    This method will increase the horizontal or vertical size of the shape by
    the specified margin. If the margin is negative, the size will be decreased
    """
    def MorphFn(margin):
      return (morphology.binary_dilation if margin > 0
              else morphology.binary_erosion)

    row_kernel = morphology.rectangle(math.fabs(row_margin), 1)
    col_kernel = morphology.rectangle(1, math.fabs(col_margin))

    mask = self.mask
    if row_margin != 0:
      mask = MorphFn(row_margin)(mask, row_kernel)
    if col_margin != 0:
      mask = MorphFn(col_margin)(mask, col_kernel)
    return Shape(mask.astype(np.bool))

  def RemoveBackground(self, image, fill=None):
    """Blend out everything that does not belong to this shape."""
    if fill is None:
      fill = np.mean(image[self.mask])
    copy = image.copy()
    copy[~self.mask] = fill
    return copy

  def Cropped(self, image):
    """Return a view to the image 'image' that is cropped to this shape."""
    return image[self.top:self.bottom, self.left:self.right]

  def FindExtreme(self, direction):
    """Find extreme this shape in any direction.

    Direction can be top, bottom, left or right. This method will return
    the coordinates of the (top, bottom, left, right)-most pixel of the shape.
    If the extreme consists of multiple pixels, the middle pixel will be picked.
    """
    if direction == "top":
      extreme_axis = 0
      extreme_func = min
    elif direction == "bottom":
      extreme_axis = 0
      extreme_func = max
    elif direction == "left":
      extreme_axis = 1
      extreme_func = min
    elif direction == "right":
      extreme_axis = 1
      extreme_func = max
    else:
      raise ValueError("direction has to be top, bottom, left or right.")

    avg_axis = (extreme_axis + 1) % 2

    coords = self.coords
    extreme_value = extreme_func(coords[:, extreme_axis])
    avg_axis_coords = coords[coords[:, extreme_axis] == extreme_value, :]
    avg_value = avg_axis_coords[:, avg_axis].mean()

    res = [0, 0]
    res[extreme_axis] = extreme_value
    res[avg_axis] = avg_value
    return res

  def ApproximatePolygon(self, num_verticies):
    """Return polygon approximation with num_verticies verticies.

    The approximated polygon is assumed to be as regular as possible, meaning
    that all inner angles in the polygon are approximately the same (i.e. we are
    looking for a rectangle, not a trapezoid, etc).
    This method returns the coordinates of each vertex in clockwise order,
    starting with he top-left-most vertex.
    """
    contour = measure.find_contours(self.mask, 0)[0]

    # First pass of approximation, this will calculate a simplified polygon
    # with an undefined number of verticies.
    verticies = measure.approximate_polygon(contour, tolerance=10)

    # The last coordinate is often a duplicate of the first.
    if (np.abs(np.linalg.norm(verticies[0, :] - verticies[-1, :]))
        < Filter.epsilon):
      verticies = verticies[:-1]

    # Assuming all angles are the same, how big should they be?
    inner_angle_sum = ((num_verticies) - 2) * np.pi / 2
    target_angle = inner_angle_sum / num_verticies

    # Calculate the angle at each vertex.
    angle_index_diffs = []
    for i in range(verticies.shape[0]):
      # Calculate normalized vector to previous vertex.
      prev_i = i - 1
      prev_delta = verticies[prev_i, :] - verticies[i, :]
      prev_delta = prev_delta / np.linalg.norm(prev_delta)

      # Calculate normalized vector to next vertex.
      next_i = (i + 1) % verticies.shape[0]
      next_delta = verticies[next_i, :] - verticies[i, :]
      next_delta = next_delta / np.linalg.norm(next_delta)

      # Calculate deviation from target angle.
      angle = np.arccos(np.dot(prev_delta, next_delta))
      angle_index_diffs.append((i, np.abs(angle - target_angle)))

    # Sort by angle differences and pick right number of verticies
    angle_index_diffs.sort(key=lambda a: a[1])
    angle_index_diffs = angle_index_diffs[:num_verticies]
    angle_index_diffs.sort(key=lambda a: a[0])

    # Return coordinates of picked verticies
    verticies = verticies[[i for i, d in angle_index_diffs], :]

    # Find top left most vertex
    dists_from_zero = [np.linalg.norm(coords) for coords in verticies]
    top_left_idx = np.argmin(dists_from_zero)

    # Reorder to have top left most vertex at index 0
    res = np.zeros(verticies.shape)
    res[0:-top_left_idx] = verticies[top_left_idx:]
    res[-top_left_idx:] = verticies[:top_left_idx]
    return res

  @property
  def cropped_shape(self):
    return Shape(self.Cropped(self.mask))

  @property
  def area(self):
    return self.props.area

  @property
  def bbox(self):
    return self.props.bbox

  @property
  def top(self):
    return self.bbox[0]

  @property
  def left(self):
    return self.bbox[1]

  @property
  def bottom(self):
    return self.bbox[2]

  @property
  def right(self):
    return self.bbox[3]

  @property
  def center_x(self):
    return (self.right - self.left) / 2

  @property
  def center_y(self):
    return (self.bottom - self.top) / 2

  @property
  def width(self):
    return self.right - self.left

  @property
  def height(self):
    return self.bottom - self.top

  @property
  def coords(self):
    return self.props.coords

  @property
  def contour(self):
    """The inner contour of this shape.

    The contour is a binary image in which only the outer pixels
    surrounding the shape are True.
    """
    if self._contour is None:
      self._contour = morphology.binary_erosion(self.mask, morphology.disk(1))
      self._contour = self.mask & (~self._contour)
      self._contour = self._contour.astype(np.bool)
    return self._contour

  @property
  def horizontal_edges(self):
    """The horizontal component of the inner contour."""
    # Dilate with structure element:
    # 1 0 1
    # 1 0 1
    # 1 0 1
    elem = np.ones((3, 3), np.bool)
    elem[:, 1] = 0
    neigh1 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # Dilate with structure element:
    # 1 0 0 0 1
    # 1 0 0 0 1
    # 1 0 0 0 1
    elem = np.ones((3, 5), np.bool)
    elem[:, 1:4] = 0
    neigh2 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # combine all 3. This will result in a binary image that only contains
    # pixels which have neighbours 1-2 pixels to the left and right that deviate
    # vertically by 1 pixel at max.
    return neigh1 & neigh2 & self.contour

  @property
  def vertical_edges(self):
    """The vertical component of the inner contour."""
    # Dilate with structure element:
    # 1 1 1
    # 0 0 0
    # 1 1 1
    elem = np.ones((3, 3), np.bool)
    elem[1, :] = 0
    neigh1 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # Dilate with structure element:
    # 1 1 1
    # 0 0 0
    # 0 0 0
    # 0 0 0
    # 1 1 1
    elem = np.ones((5, 3), np.bool)
    elem[1:4, :] = 0
    neigh2 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # combine all 3. This will result in a binary image that only contains
    # pixels which have neighbours 1-2 pixels to the top and bottom that deviate
    # horizontally by 1 pixel at max.
    return neigh1 & neigh2 & self.contour

  @staticmethod
  def Shapes(binary_im):
    labels = measure.label(binary_im)
    # hack: the region 0 is ignored by regionprops, but it's a valid region
    labels[labels == 0] = np.max(labels) + 1

    # find all region props that match_fn returns True for
    for props in measure.regionprops(labels, binary_im):
      if props.max_intensity < 1.0:
        continue
      yield Shape(labels == props.label, props)
