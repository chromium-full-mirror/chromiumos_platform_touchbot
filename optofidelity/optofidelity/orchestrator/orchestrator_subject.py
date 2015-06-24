# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from optofidelity.system import BenchmarkSubject

BenchmarkDefinition = namedtuple("BenchmarkDefinition",
                                 ["name", "benchmark_type", "activity",
                                  "params"])

class OrchestratorSubject(BenchmarkSubject):
  def __init__(self, name, dut_backend, camera):
    super(OrchestratorSubject, self).__init__(name, dut_backend, camera)
    self.benchmark_defs = {}

  @classmethod
  def FromBenchmarkSubject(cls, other):
    self = cls(other.name, other._dut_backend, other.camera)
    self.__dict__.update(other.__dict__)
    return self

  def DefineBenchmark(self, name, benchmark_type, activity, params):
    self.benchmark_defs[name] = BenchmarkDefinition(name, benchmark_type,
                                                    activity, params)
