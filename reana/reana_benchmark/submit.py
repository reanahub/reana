# This file is part of REANA.
# Copyright (C) 2021, 2022, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Responsible for creating and uploading workflows."""

import os
import concurrent.futures
from functools import lru_cache
from typing import Optional, Tuple

from reana_client.api.client import (
    create_workflow_from_bundle,
    upload_to_server,
)
from reana_commons.specification_paths import gather_validation_members

from reana.reana_benchmark.utils import (
    logger,
    build_extended_workflow_name,
    get_access_token,
)
from reana.reana_benchmark.config import WORKERS_DEFAULT_COUNT

CURRENT_WORKING_DIRECTORY = os.getcwd()


@lru_cache(maxsize=None)
def _get_runtime_input_paths(reana_file_path: str) -> Tuple[str, ...]:
    """Return the declared inputs that the creation bundle does not carry.

    The server seeds the workspace with the files of the specification bundle
    (the specification and the declared workflow sources), so only the
    remaining runtime inputs have to be uploaded afterwards.
    """
    members, reana_specification, _ = gather_validation_members(reana_file_path)
    base_directory = os.path.dirname(reana_file_path)
    inputs = reana_specification.get("inputs") or {}

    paths = {os.path.normpath(f) for f in inputs.get("files") or []}
    for directory in inputs.get("directories") or []:
        for root, _, filenames in os.walk(os.path.join(base_directory, directory)):
            paths.update(
                os.path.relpath(os.path.join(root, filename), base_directory)
                for filename in filenames
            )

    return tuple(
        os.path.join(base_directory, path)
        for path in sorted(paths)
        if path.replace(os.sep, "/") not in members
    )


def _create_workflow(workflow: str, file: str) -> None:
    create_workflow_from_bundle(file, workflow, get_access_token())


def _upload_workflow(workflow: str, file: str) -> None:
    for filename in _get_runtime_input_paths(file):
        upload_to_server(workflow, filename, get_access_token())


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
