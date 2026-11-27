# This file is part of REANA.
# Copyright (C) 2021, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Contains common functions shared by reana-benchmark modules."""

import logging
import os
from datetime import datetime

from reana_client.auth import oidc

from reana.reana_benchmark.config import DATETIME_FORMAT

logger = logging.getLogger("reana-benchmark")
logger.setLevel(logging.INFO)


def validate_date(date_text: str) -> None:
    """Validate datetime string against common reana-benchmark datetime format."""
    try:
        datetime.strptime(date_text, DATETIME_FORMAT)
    except ValueError:
        raise ValueError(
            f'"{date_text}" has incorrect datetime format, correct format is "{DATETIME_FORMAT}".'
        )


def get_utc_now_timestamp() -> str:  # noqa: D103
    return datetime.utcnow().strftime(DATETIME_FORMAT)


def build_extended_workflow_name(workflow: str, run_number: int) -> str:  # noqa: D103
    return f"{workflow}-{run_number}"


def get_access_token() -> str:
    """Return the access token to use for the REANA server.

    Use the saved ``reana-client login`` credentials, refreshed as needed, so
    that long benchmarks outlive a single access token. ``REANA_ACCESS_TOKEN``
    overrides them, as it does for ``reana-client``.
    """
    return os.getenv("REANA_ACCESS_TOKEN") or oidc.get_access_token()
