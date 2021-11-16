# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Responsible for creating and uploading workflows."""

import os
import concurrent.futures
from functools import lru_cache
from typing import Optional, Dict

from click import format_filename

from reana_client.api.client import (
    create_workflow,
    upload_to_server,
)
from reana_client.utils import load_reana_spec

from reana.reana_benchmark.utils import (
    logger,
    build_extended_workflow_name,
)
from reana.reana_benchmark.config import REANA_ACCESS_TOKEN, WORKERS_DEFAULT_COUNT


CURRENT_WORKING_DIRECTORY = os.getcwd()


@lru_cache(maxsize=None)
def _load_reana_specification(reana_file_path: str) -> Dict:
    return load_reana_spec(
        format_filename(reana_file_path),
        access_token=REANA_ACCESS_TOKEN,
        skip_validation=True,
    )


def _create_workflow(workflow: str, file: str) -> None:
    reana_specification = _load_reana_specification(file)
    create_workflow(reana_specification, workflow, REANA_ACCESS_TOKEN)


def _upload_workflow(workflow: str, file: str) -> None:
    reana_specification = _load_reana_specification(file)

    filenames = []

    if "inputs" in reana_specification:
        filenames += [
            os.path.join(CURRENT_WORKING_DIRECTORY, f)
            for f in reana_specification["inputs"].get("files") or []
        ]
        filenames += [
            os.path.join(CURRENT_WORKING_DIRECTORY, d)
            for d in reana_specification["inputs"].get("directories") or []
        ]

    for filename in filenames:
        upload_to_server(workflow, filename, REANA_ACCESS_TOKEN)


def _create_and_upload_single_workflow(workflow_name: str, reana_file: str) -> None:
    absolute_file_path = f"{CURRENT_WORKING_DIRECTORY}/{reana_file}"
    _create_workflow(workflow_name, absolute_file_path)
    _upload_workflow(workflow_name, absolute_file_path)


def _create_and_upload_workflows(
    workflow: str,
    workflow_range: (int, int),
    file: Optional[str] = None,
    workers: int = WORKERS_DEFAULT_COUNT,
) -> None:
    logger.info(f"Creating and uploading {workflow_range} workflows...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _create_and_upload_single_workflow,
                build_extended_workflow_name(workflow, i),
                file,
            )
            for i in range(workflow_range[0], workflow_range[1] + 1)
        ]
        for future in concurrent.futures.as_completed(futures):
            # collect results, in case of exception, it will be raised here
            future.result()


def submit(
    workflow_prefix: str, workflow_range: (int, int), file: str, workers: int
) -> None:
    """Submit multiple workflows, do not start them."""
    _create_and_upload_workflows(workflow_prefix, workflow_range, file, workers)
    logger.info("Finished creating and uploading workflows.")
