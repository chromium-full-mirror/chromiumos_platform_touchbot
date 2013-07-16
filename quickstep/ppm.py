# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from numpy import linspace
from collections import namedtuple

Color = namedtuple('Color', ['r', 'g', 'b'])
WHITE = Color(255, 255, 255)
BLACK = Color(0, 0, 0)
RED = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
BLUE = Color(0, 0, 255)
MAGENTA = Color(255, 0, 255)
CYAN = Color(0, 255, 255)
YELLOW = Color(128, 128, 0)

PPM_MAGIC_NUMBER = 'P3'
BIT_DEPTH = 255

LINE_NUM_STEPS = 1000

class Image:
    """ A simple PPM image manipulation class
    A ppm image is a simple, ascii human readable image format.  This class
    allows you to create an image, draw simple shapes on it or access the
    idividual pixels and save the resulting picture to the hard drive.

    http://en.wikipedia.org/wiki/Netpbm_format
    """
    def __init__(self, width, height):
        self.width = int(width)
        self.height = int(height)
        self.pixels = [[WHITE] * self.height for i in range(self.width)]

    def Save(self, filename):
        with open(filename, 'w') as fo:
            fo.write('%s\n' % PPM_MAGIC_NUMBER)
            fo.write('%d %d\n' % (self.width, self.height))
            fo.write('%d\n' % BIT_DEPTH)

            for y in range(self.height):
                for x in range(self.width):
                    fo.write('%d %d %d ' % self[x, y])
                fo.write('\n')

    def Circle(self, coords, color, radius=4):
        x, y = coords
        x = int(x)
        y = int(y)
        r_sq = radius ** 2

        for x1 in range(x - radius, x + radius):
            for y1 in range(y - radius, y + radius):
                d_sq = (x - x1) ** 2 +  (y - y1) ** 2
                if d_sq <= r_sq:
                    self[(x1, y1)] = color

    def Line(self, coord1, coord2, color):
        """ Use Bresenham's line algorithm to connect coord1 and coord2 """
        x1, y1 = coord1
        x1 = int(x1)
        y1 = int(y1)
        x2, y2 = coord2
        x2 = int(x2)
        y2 = int(y2)

        is_steep = abs(y2-y1) > abs(x2-x1)
        if is_steep:
            x1, y1 = y1, x1
            x2, y2 = y2, x2

        if x1 > x2:
            x1, x2 = x2, x1
            y1, y2 = y2, y1

        dx = x2 - x1
        dy = abs(y2 - y1)
        ystep = 1 if y1 < y2 else -1
        error = int(dx / 2)

        y = y1
        for x in range(x1, x2 + 1):
            self[(x, y) if not is_steep else (y, x)] = color
            error -= dy
            if error < 0:
                y += ystep
                error += dx

    def __getitem__(self, coords):
        x, y = coords
        if x >= 0 and x < self.width and y >= 0 and y < self.height:
            return self.pixels[int(x)][int(y)]
        else:
            return None

    def __setitem__(self, coords, color):
        x, y = coords
        if x >= 0 and x < self.width and y >= 0 and y < self.height:
            self.pixels[int(x)][int(y)] = color
