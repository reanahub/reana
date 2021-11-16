# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Responsible for starting workflows that were submitted before."""

import concurrent.futures
from pathlib import Path

import pandas as pd

from reana.reana_benchmark.config import REANA_ACCESS_TOKEN, WORKERS_DEFAULT_COUNT
from reana.reana_benchmark.utils import (
    logger,
    build_extended_workflow_name,
    get_utc_now_timestamp,
)
from reana_client.api.client import start_workflow


def build_started_results_path(workflow: str) -> Path:  # noqa: D103
    return Path(f"{workflow}_started_results.csv")


def create_empty_dataframe_for_started_results() -> pd.DataFrame:  # noqa: D103
    return pd.DataFrame(columns=["name", "asked_to_start_date"])


def _start_single_workflow(workflow_name: str) -> (str, str):
    try:
        start_workflow(workflow_name, REANA_ACCESS_TOKEN, {})
    except Exception as e:
        raise Exception(
            f"Workflow {workflow_name} failed during the start. Details: {e}"
        )

    asked_to_start_datetime = get_utc_now_timestamp()
    return workflow_name, asked_to_start_datetime


def _start_workflows_and_record_start_time(
    workflow_name: str, workflow_range: (int, int), workers: int = WORKERS_DEFAULT_COUNT
) -> pd.DataFrame:
    logger.info(f"Starting {workflow_range} workflows...")
    df = create_empty_dataframe_for_started_results()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _start_single_workflow, build_extended_workflow_name(workflow_name, i)
            )
            for i in range(workflow_range[0], workflow_range[1] + 1)
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                workflow_name, asked_to_start_datetime = future.result()
                df = df.append(
                    {
                        "name": workflow_name,
                        "asked_to_start_date": asked_to_start_datetime,
                    },
                    ignore_index=True,
                )
            except Exception as e:
                logger.error(e)
    return df


def _append_to_existing_started_results(
    workflow_name: str, new_results: pd.DataFrame
) -> pd.DataFrame:
    """Append new started results to existing started results and return them."""
    results_path = build_started_results_path(workflow_name)

    existing_results = pd.DataFrame()

    if results_path.exists():
        logger.info("Loading existing started results. Appending...")
        existing_results = pd.read_csv(results_path)

    return existing_results.append(new_results, ignore_index=True)


def _save_started_results(workflow_name: str, df: pd.DataFrame) -> None:
    logger.info("Saving started results...")
    results_path = build_started_results_path(workflow_name)
    df.to_csv(results_path, index=False)


def start(workflow_name: str, workflow_range: (int, int), workers: int) -> None:
    """Start already submitted workflows."""
    started_results = _start_workflows_and_record_start_time(
        workflow_name, workflow_range, workers
    )

    started_results = _append_to_existing_started_results(
        workflow_name, started_results
    )

    _save_started_results(workflow_name, started_results)
    logger.info("Finished starting workflows.")
