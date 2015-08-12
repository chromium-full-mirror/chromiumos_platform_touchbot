# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os.path

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import webapp2

REPORTS_BASE_URL = "/gs/touchbot/optofidelity/benchmark_results/"

class ReportHandler(blobstore_handlers.BlobstoreDownloadHandler):
  """Handler to serve report files stored in REPORTS_BASE_URL.

  This handler only serves to authenticated users.
  """

  def get(self, path):
    # Make sure we have a signed-in user. App engine configuration limits these
    # users to Googlers only.
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return

    # Generate blobstore path to file to be served. Make sure no one is trying
    # anything nasty to access files outside of REPORTS_BASE_URL
    blob_path = os.path.normpath(os.path.join(REPORTS_BASE_URL, path))
    if not blob_path.startswith(REPORTS_BASE_URL):
      self.error(404)
      return

    # Serve file
    blob_key = blobstore.create_gs_key(blob_path)
    self.send_blob(blob_key, save_as=False)

app = webapp2.WSGIApplication([('/reports/(.*)', ReportHandler)])
