# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""reana_bench script - benchmark script for REANA cluster"""

import json
import logging
import os
import subprocess
import time
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Optional, List, NoReturn
import urllib3

import click
import matplotlib.pyplot as plt
import pandas as pd

from reana_client.api.client import start_workflow, create_workflow
from reana_client.utils import load_reana_spec

urllib3.disable_warnings()

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

REANA_ACCESS_TOKEN = os.getenv("REANA_ACCESS_TOKEN")

# 2 or more workers could hit reana-server API rate limit sometimes
WORKERS_DEFAULT_COUNT = 1


@click.group()
def cli():
    """reana_bench script - runs single workflow multiple times, collects results, analyzes them.

    Prerequisites:

        - set REANA_ACCESS_TOKEN and REANA_SERVER_URL

    How to launch 50 concurrent workflows and collect results:

        .. code-block:: console

        \b
        $ cd reana-demo-root6-roofit  # find an example of REANA workflow
        $ reana_bench.py launch -w roofit50yadage -n 50 -f reana-yadage.yaml  # starts 50 workflows
        $ reana_bench.py collect -w roofit50yadage  # collect results
        $ reana_bench.py analyze -w roofit50yadage  # analyzes results that were saved locally
    """
    pass


def _build_command(command_type: str, workflow_name: str) -> List[str]:
    return ["reana-client", command_type, "-w", workflow_name]


def _create_workflow(workflow: str, file: str) -> NoReturn:
    reana_specification = load_reana_spec(
        click.format_filename(file),
        access_token=REANA_ACCESS_TOKEN,
        skip_validation=True,
    )
    create_workflow(reana_specification, workflow, REANA_ACCESS_TOKEN)


def _upload_workflow(workflow: str) -> NoReturn:
    upload_cmd = _build_command("upload", workflow)
    subprocess.run(upload_cmd, stdout=subprocess.DEVNULL)


def _create_and_upload_single_workflow(workflow_name: str, file: str):
    _create_workflow(workflow_name, file)
    _upload_workflow(workflow_name)


def _build_extended_workflow_name(workflow: str, run_number: int) -> str:
    return f"{workflow}-{run_number}"


def _create_and_upload_workflows(
    workflow: str,
    n: int,
    file: Optional[str] = None,
    workers: int = WORKERS_DEFAULT_COUNT,
) -> NoReturn:
    logging.info(f"Creating and uploading {n} workflows...")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _create_and_upload_single_workflow,
                _build_extended_workflow_name(workflow, i),
                file,
            )
            for i in range(0, n)
        ]
        for future in concurrent.futures.as_completed(futures):
            # collect results, in case of exception, it will be raised here
            future.result()


def _get_utc_now_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _start_single_workflow(workflow_name: str) -> (str, str):
    # TODO: maybe we can add "after" - "before" start_workflow to compensate for API latency
    start_workflow(workflow_name, REANA_ACCESS_TOKEN, {})
    submit_datetime = _get_utc_now_timestamp()
    return workflow_name, submit_datetime


def _start_workflows_and_record_submit_dates(
    workflow_name: str, n: int, workers: int = WORKERS_DEFAULT_COUNT
) -> pd.DataFrame:
    logging.info(f"Starting {n} workflows...")
    df = pd.DataFrame(columns=["name", "submit_date", "submit_number"])
    submit_number = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _start_single_workflow, _build_extended_workflow_name(workflow_name, i)
            )
            for i in range(0, n)
        ]
        for future in concurrent.futures.as_completed(futures):
            workflow_name, submit_datetime = future.result()
            df = df.append(
                {
                    "name": workflow_name,
                    "submit_date": submit_datetime,
                    "submit_number": submit_number,
                },
                ignore_index=True,
            )
            submit_number += 1
    df["submit_number"] = df["submit_number"].astype(int)
    return df


def _get_workflows(workflow: str) -> pd.DataFrame:
    cmd = _build_reana_client_list_command(workflow)
    return pd.DataFrame(json.loads(subprocess.check_output(cmd).decode("ascii")))


def _workflow_already_exists(workflow: str) -> bool:
    """Retrieve as little data as possible and check if workflow exists."""
    cmd = _build_reana_client_list_command(workflow, page=1, size=1)
    workflows = json.loads(subprocess.check_output(cmd).decode("ascii"))
    return len(workflows) != 0


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


def _convert_str_date_to_epoch(series: pd.Series) -> pd.Series:
    return series.apply(
        lambda x: int(time.mktime(datetime.fromisoformat(x).timetuple()))
    )


def _clean_results(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Cleaning results...")

    df["run_number"] = df["run_number"].astype(int)
    df["submit_number"] = df["submit_number"].astype(int)

    # fix "-" values for created status
    df.loc[df["status"] == "created", "started"] = df[df["status"] == "created"][
        "created"
    ]
    df.loc[df["status"] == "created", "ended"] = df[df["status"] == "created"][
        "created"
    ]

    # fix "-" values for running, pending, queued statuses
    utc_now = _get_utc_now_timestamp()

    df.loc[df["status"] == "running", "ended"] = utc_now

    df.loc[df["status"] == "pending", "started"] = utc_now
    df.loc[df["status"] == "pending", "ended"] = utc_now

    df.loc[df["status"] == "queued", "started"] = utc_now
    df.loc[df["status"] == "queued", "ended"] = utc_now
    return df


def _pre_process_results(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Pre-processing results...")

    df["started"] = _convert_str_date_to_epoch(df["started"])
    df["ended"] = _convert_str_date_to_epoch(df["ended"])
    df["created"] = _convert_str_date_to_epoch(df["created"])
    df["submit_date"] = _convert_str_date_to_epoch(df["submit_date"])
    return df


def _derive_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = _pre_process_results(df)

    logging.info("Deriving metrics...")

    df["pending_time"] = df["started"] - df["submit_date"]
    df["pending_time"] = df["pending_time"].astype(int)

    df["runtime"] = df["ended"] - df["started"]
    df["runtime"] = df["runtime"].astype(int)
    return df


def _max_min_mean_median(series: pd.Series) -> (int, int, int, int):
    max_value = series.max()
    min_value = series.min()
    mean_value = series.mean()
    median_value = series.median()
    return int(max_value), int(min_value), int(mean_value), int(median_value)


def _execution_progress_plot(folder_path: Path, df: pd.DataFrame) -> NoReturn:
    plt.clf()

    sorted_df = df.sort_values(["submit_date", "submit_number"])

    submit_offset = sorted_df["submit_date"] - sorted_df["submit_date"].iloc[0]

    # dummy x axis
    numbers = [int(i) for i in range(0, len(sorted_df))]

    plt.bar(
        numbers,
        sorted_df["runtime"],
        bottom=sorted_df["pending_time"] + submit_offset,
        label="runtime",
    )

    plt.bar(
        numbers, sorted_df["pending_time"], bottom=submit_offset, label="pending_time",
    )

    plt.bar(numbers, submit_offset, color="grey")

    plt.xlabel("workflow run")
    plt.ylabel("time [s]")
    plt.legend()
    plt.savefig(f"{folder_path}/execution_progress.png")


def _execution_status_plot(folder_path: Path, df: pd.DataFrame) -> NoReturn:
    plt.clf()
    total = len(df)
    statuses = list(df["status"].unique())
    stats = {status: len(df[df["status"] == status]) for status in statuses}
    plt.pie(
        stats.values(),
        labels=stats.keys(),
        autopct=lambda val: round(((val / 100) * sum(stats.values()))),
    )
    plt.title("Status distribution")
    plt.text(-1, 1, f"total: {total}")
    plt.savefig(f"{folder_path}/execution_status.png")


def _create_histogram_plot(
    folder_path: Path, series: pd.Series, bin_size: int, label: str,
) -> NoReturn:
    plt.clf()
    plt.hist(series, bin_size, color="b", label=label)
    plt.xlabel(f"{label} [s] (bin size = {bin_size})")
    plt.ylabel("Number of runs")
    plt.legend()

    slowest, fastest, mean, median = _max_min_mean_median(series)

    plt.title(
        f"fastest: {fastest}, median: {median}," f" mean: {mean}, slowest: {slowest}"
    )

    plt.savefig(f"{folder_path}/histogram_{label}.png")


def _total_time_histogram(folder_path: Path, df: pd.DataFrame) -> NoReturn:
    _create_histogram_plot(
        folder_path, df["runtime"] + df["pending_time"], 10, "total_time"
    )


def _runtime_histogram(folder_path: Path, df: pd.DataFrame) -> NoReturn:
    _create_histogram_plot(folder_path, df["runtime"], 10, "runtime")


def _pending_time_histogram(folder_path: Path, df: pd.DataFrame) -> NoReturn:
    _create_histogram_plot(folder_path, df["pending_time"], 10, "pending_time")


def _create_plots(folder_path: Path, df: pd.DataFrame) -> NoReturn:
    logging.info("Creating plots...")
    _execution_progress_plot(folder_path, df)
    _execution_status_plot(folder_path, df)
    _total_time_histogram(folder_path, df)
    _runtime_histogram(folder_path, df)
    _pending_time_histogram(folder_path, df)


def _start_benchmark(
    workflow_name: str, number_of_submissions: int, file: str, workers: int
) -> pd.DataFrame:
    if _workflow_already_exists(workflow_name):
        raise Exception("Found duplicated workflow name. Please use unique name.")

    _create_and_upload_workflows(workflow_name, number_of_submissions, file, workers)

    submitted_results = _start_workflows_and_record_submit_dates(
        workflow_name, number_of_submissions, workers
    )
    return submitted_results


def _build_results_folder_path(workflow: str) -> Path:
    return Path(f"benchmark_{workflow}")


def _build_original_results_path(workflow: str) -> Path:
    return Path(f"{_build_results_folder_path(workflow)}/original_results.csv")


def _build_submitted_results_path(workflow: str) -> Path:
    return Path(f"{_build_results_folder_path(workflow)}/submitted_results.csv")


def _build_processed_results_path(workflow: str) -> Path:
    return Path(f"{_build_results_folder_path(workflow)}/processed_results.csv")


def _merge_workflows_and_submitted_results(
    workflows: pd.DataFrame, submitted: pd.DataFrame
) -> pd.DataFrame:
    logging.info("Merging workflows and submitted results...")
    return workflows.merge(submitted, on=["name"])


def _save_original_results(workflow: str, df: pd.DataFrame):
    logging.info("Saving original results...")
    original_results_path = _build_original_results_path(workflow)
    df.to_csv(original_results_path, index=False)


@cli.command()
@click.option("--workflow", "-w", help="Name of the workflow", required=True, type=str)
@click.option(
    "--number", "-n", help="Number of workflows to start", required=True, type=int
)
@click.option(
    "--file",
    "-f",
    help="REANA YAML specification file",
    default="reana.yaml",
    type=click.Path(exists=True),
)
@click.option(
    "--concurrency",
    "-c",
    help=f"Number of workers to submit workflows, default {WORKERS_DEFAULT_COUNT}",
    default=WORKERS_DEFAULT_COUNT,
    type=int,
)
def launch(workflow: str, number: int, file: str, concurrency: int):
    """Launch multiple workflows."""
    results_folder_path = _build_results_folder_path(workflow)

    try:
        os.mkdir(results_folder_path)
    except FileExistsError:
        logging.info(
            "Benchmark folder already exists. Will overwrite previous results."
        )

    try:
        submitted_results = _start_benchmark(workflow, number, file, concurrency)
    except Exception as e:
        logging.error(f"Something went wrong during benchmark launch: {e}")
        return

    logging.info("Saving intermediate submit results...")
    submitted_results_path = _build_submitted_results_path(workflow)
    submitted_results.to_csv(submitted_results_path, index=False)

    logging.info("Finished. Don't forget to collect the results.")


@cli.command()
@click.option("--workflow", "-w", help="Name of the workflow", required=True, type=str)
def analyze(workflow: str):
    """Produce various plots and derive metrics based on launch results collected before."""
    original_results_path = _build_original_results_path(workflow)
    original_results = pd.read_csv(original_results_path)

    processed_results = _derive_metrics(original_results)

    logging.info("Saving processed results...")
    processed_results_path = _build_processed_results_path(workflow)
    processed_results.to_csv(processed_results_path, index=False)

    results_folder_path = _build_results_folder_path(workflow)
    _create_plots(results_folder_path, processed_results)


@cli.command()
@click.option("--workflow", "-w", help="Name of the workflow", required=True, type=str)
@click.option(
    "--force",
    "-f",
    help="Force collect results even if workflows are still running",
    default=False,
    is_flag=True,
)
def collect(workflow: str, force: bool):
    """Collect workflows results, merge them with intermediate results and save."""
    submitted_results_path = _build_submitted_results_path(workflow)
    submitted_results = pd.read_csv(submitted_results_path)

    workflows = _get_workflows(workflow)
    if _workflows_finished(workflows) or force:
        results = _merge_workflows_and_submitted_results(workflows, submitted_results)
        results = _clean_results(results)
        _save_original_results(workflow, results)
        logging.info(f"Collected {len(results)} workflows. Finished.")
    else:
        logging.info(
            "Not collecting. Workflows are still running. Use -f option to force collect."
        )


if __name__ == "__main__":
    cli()
