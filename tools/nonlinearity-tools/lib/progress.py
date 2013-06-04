# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import time


class ProgressBar:
    """ A simple progress indicator class

    When you initialize a new ProgressBar, you give it the number of tasks you
    are going to do.  Then each time you complete one (or some) you use the
    progress() member function to update the display.

    If you want to further divide one of the tasks, you can use subtask() to
    subdivide the progress of the task currently being worked on.

    Example:
        bar = ProgressBar(len(work))
        for w in work:
            # Process w here
            bar.progress()
    """
    BAR_WIDTH = 50

    def __init__(self, num_items):
        self._start_time = time.time()
        self.num_items = []
        self.num_done = []
        self.subtask(num_items)
        self._print_progress()

    def progress(self, amount=1):
        self.num_done[-1] += amount
        self._print_progress()

        if self.num_done[-1] >= self.num_items[-1]:
            self.num_done.pop()
            self.num_items.pop()

            if not self.num_items:
                print "\n"

    def subtask(self, num_items):
        self.num_items.append(float(num_items))
        self.num_done.append(0)

    def _calculate_progress(self):
        perc = 0.0
        value = 1.0

        for i in range(len(self.num_done)):
            perc += (self.num_done[i] / self.num_items[i]) * value
            value *= (1 / self.num_items[i])
        return perc

    def _duration(self):
        time_taken = time.time() - self._start_time
        seconds = time_taken % 60
        minutes = int(time_taken / 60) % 60
        s = "%02d:%02d" % (minutes, seconds)

        hours = int(time_taken / (60 * 60))
        if hours > 0:
            s = "%02d:%s" % (hours, s)
        return s

    def _print_progress(self):
        percent = self._calculate_progress()
        if percent > 1.0: percent = 1.0

        sys.stdout.write("Progress [")
        for i in range(self.BAR_WIDTH):
            if i <= percent * self.BAR_WIDTH:
                sys.stdout.write("=")
            else:
                sys.stdout.write(" ")
        sys.stdout.write("] ~%.1f%% %s\r" % (percent * 100, self._duration()))
