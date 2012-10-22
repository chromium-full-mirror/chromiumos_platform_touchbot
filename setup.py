# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from distutils.core import setup
setup(
    name='touchbot',
    version='1.0',
    description='Touch robot controls',
    package_data={'roibot': ['devices/*.pp']},
    packages=['roibot', 'gestures'],
)
