from __future__ import annotations

# Common
from common.extended_path import ExtendedPath

# Unaknown
# Unknown
from MyWaifuLovesMe.settings import BASE_DIR as _BASE_DIR

# Update the value to use ExtendedPath instead of a regular path
BASE_DIR = ExtendedPath(_BASE_DIR)

DOWNLOADED_FILES_DIR = BASE_DIR / "downloaded_files"
