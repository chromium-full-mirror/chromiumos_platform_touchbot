# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from scipy.spatial import KDTree

class Filter:
    """ The main Filter container for the non-linearity compensation

    A filter is built out of all the data gathered from the touchpad and stored
    as Strokes.  All the errors calculated at all the (x, y, p) points are
    stored as one large point cloud and a KD tree is used to efficiently find
    nearest neighbors to estimate the error at points we have not explicity
    seen yet.

    To build a filter from a list of strokes and look up the estimated error at
    a given point you would do something like this:

        files = ['stroke1.p', 'stroke2.p', ..., 'stroke400.p']
        strokes = [Stroke.load_from_file(filename) for filename in files]
        filt = Filter(strokes)
        err_x, err_y = filt.getError((323, 242, 34))
    """

    def __init__(self, strokes):
        """Initialize the filter by supplying the stroke objects that
        will be used as the training set.
        """
        self._readings = {}
        for stroke in strokes:
            self._readings.update(stroke.compute_error())

        self.min_x = min([x for x, y, p in self._readings])
        self.max_x = max([x for x, y, p in self._readings])
        self.min_y = min([y for x, y, p in self._readings])
        self.max_y = max([y for x, y, p in self._readings])
        self.min_p = min([p for x, y, p in self._readings])
        self.max_p = max([p for x, y, p in self._readings])

        self._tree = KDTree(self._readings.keys())

    def getError(self, point, num_neighbors=5):
        """Find the error that the filter predicts the touchpad will have at
        a given point.
        """
        x, y, p = point
        # Find the closest sampled points
        nn_dists, nn_indices = self._tree.query(point, num_neighbors)
        error_x = error_y = total_weight = 0.0
        # Take a weighted average of them based on their distances
        for nn_distance, nn_index in zip(nn_dists, nn_indices):
            nn_errors = self._readings[tuple(self._tree.data[nn_index])]
            nn_error_x, nn_error_y = nn_errors
            # Note: The distance is smoothed slightly to prevent divide-by-zero
            weight = 1.0 / (nn_distance + 1)
            error_x += nn_error_x * weight
            error_y += nn_error_y * weight
            total_weight += weight
        return error_x / total_weight, error_y / total_weight

    def _adjustSingle(self, point):
        """Given a single reading from the touchpad, return the corresponding
        error-compensated point.
        """
        x, y, p = point
        error_x, error_y = self.getError((x, y, p))
        return (x - error_x, y - error_y, p)

    def adjust(self, stroke):
        """Given an entire stroke, adjust each of the points accordingly, to
        estimate where the stroke actually was.
        """
        # Strokes contain an additional timestamp with each event that must
        # be removed during processing and re-added so that this can still
        # return a legal "Stroke"
        return Stroke((t,) + [self._adjustSingle((x, y, p))
                      for t, x, y, p in stroke])
