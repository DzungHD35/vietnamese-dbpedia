"""Đường dẫn dùng chung của API."""

import os

from vidbpedia.common import ROOT

WEB_DIST = os.path.join(ROOT, "ui", "web", "dist")
WEB_INDEX = os.path.join(WEB_DIST, "index.html")
