# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tempfile import NamedTemporaryFile

from .system import BenchmarkSystem


_fake_config = """\
<optofidelity>
  <dut name="fake_dut">
    <subject name="fake_subject" icon="dummy.shp" />
  </dut>
</optofidelity>
"""

def TemporaryFileWithData(data):
  tempfile = NamedTemporaryFile()
  tempfile.write(data)
  tempfile.flush()
  return tempfile

class FakeBenchmarkSystem(BenchmarkSystem):
  def __init__(self):
    config_file = TemporaryFileWithData(_fake_config)
    super(FakeBenchmarkSystem, self).__init__(config_file.name, True)
