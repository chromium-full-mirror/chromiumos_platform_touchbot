# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

script_dir = os.path.dirname(os.path.realpath(__file__))
config_file = os.path.join(script_dir, "optofidelity.xml")
state_file = os.path.join(script_dir, "optofidelity.state")
results_url = "gs://touchbot/optofidelity/benchmark_results"
dashboard_endpoint = "https://chromeperf.appspot.com/add_point"

try:
  from private_config import results_db_url
except ImportError:
  results_db_url = "sqlite:////%s/results.db" % script_dir