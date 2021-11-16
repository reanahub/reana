# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Responsible for collecting and cleaning results of benchmark run."""

import json
import subprocess
from pathlib import Path
from typing import Optional, List

import pandas as pd

from reana.reana_benchmark.start import (
    build_started_results_path,
    create_empty_dataframe_for_started_results,
)
from reana.reana_benchmark.utils import logger, get_utc_now_timestamp


def _get_workflows(workflow_prefix: str) -> pd.DataFrame:
    # TODO: in case of big number of workflows, this function can take a long time
    #  maybe, consider pagination and page size
    cmd = _build_reana_client_list_command(workflow_prefix)
    return pd.DataFrame(json.loads(subprocess.check_output(cmd).decode("ascii")))


def build_collected_results_path(workflow: str) -> Path:  # noqa: D103
    return Path(f"{workflow}_collected_results.csv")


def _build_reana_command(command_type: str, workflow_name: str) -> List[str]:
    return ["reana-client", command_type, "-w", workflow_name]


def _build_reana_client_list_command(
    workflow: str, page: Optional[int] = None, size: Optional[int] = None
) -> List[str]:
    base_cmd = ["reana-client", "list", "--json", "--filter", f"name={workflow}"]

    if page:
        base_cmd.append("--page")
        base_cmd.append(str(page))
    if size:
        base_cmd.append("--size")
        base_cmd.append(str(size))
    return base_cmd


def _workflows_finished(df: pd.DataFrame) -> bool:
    return df["status"].isin(["failed", "finished"]).all()


def _clean_results(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Cleaning results...")

    # fix "-" values for created status
    df.loc[df["status"] == "created", "started"] = None
    df.loc[df["status"] == "created", "ended"] = None
    df["asked_to_start_date"] = df.apply(
        lambda row: None
        if pd.isna(row["asked_to_start_date"])
        else row["asked_to_start_date"],
        axis=1,
    )

    # fix "-" values for running, pending, queued statuses
    df.loc[df["status"] == "running", "ended"] = None

    df.loc[df["status"] == "pending", "started"] = None
    df.loc[df["status"] == "pending", "ended"] = None

    df.loc[df["status"] == "queued", "started"] = None
    df.loc[df["status"] == "queued", "ended"] = None
    return df


def _merge_workflows_and_started_results(
    workflows: pd.DataFrame, started_results: pd.DataFrame
) -> pd.DataFrame:
    """Merge workflows status results and recorded started results.

    Required columns: name (workflow_name)
    """
    logger.info("Merging workflows and started results...")
    return workflows.merge(started_results, on=["name"], how="left")


def _save_collected_results(workflow: str, df: pd.DataFrame):
    logger.info("Saving collected results...")
    results_path = build_collected_results_path(workflow)
    df.to_csv(results_path, index=False)


def collect(workflow_prefix: str, force: bool) -> None:  # noqa: D103
    results_path = build_started_results_path(workflow_prefix)

    if results_path.exists():
        started_results = pd.read_csv(results_path)
    else:
        logger.warning("Started results are not found.")
        started_results = create_empty_dataframe_for_started_results()

    workflows = _get_workflows(workflow_prefix)
    if _workflows_finished(workflows) or force:
        results = _merge_workflows_and_started_results(workflows, started_results)
        results = _clean_results(results)

        collect_datetime = get_utc_now_timestamp()
        results["collected_date"] = [collect_datetime] * len(results)

        _save_collected_results(workflow_prefix, results)
        logger.info(f"Collected {len(results)} workflows. Finished.")
    else:
        logger.info(
            "Not collecting. Workflows are still running. Use -f option to force collect."
        )
