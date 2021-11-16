# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Defines values shared between reana-benchmark modules."""

import os

REANA_ACCESS_TOKEN = os.getenv("REANA_ACCESS_TOKEN")

# 2 or more workers could hit reana-server API rate limit sometimes
WORKERS_DEFAULT_COUNT = 1

# common datetime format
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
