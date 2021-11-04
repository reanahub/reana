#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""reana_bench script - benchmark script for REANA cluster"""

import concurrent.futures
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, NoReturn, Dict, Tuple

import click
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import urllib3
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from reana_client.api.client import start_workflow, create_workflow
from reana_client.utils import load_reana_spec

urllib3.disable_warnings()

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

REANA_ACCESS_TOKEN = os.getenv("REANA_ACCESS_TOKEN")

# 2 or more workers could hit reana-server API rate limit sometimes
WORKERS_DEFAULT_COUNT = 1

# common datetime format
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


@click.group()
def cli():
    """reana_bench script - runs single workflow multiple times, collects results, analyzes them.

    Prerequisites:

        - install reana-client 0.8.x, pandas and matplotlib Python packages
        - set REANA_ACCESS_TOKEN and REANA_SERVER_URL

    How to launch 50 concurrent workflows and collect results (option 1):

        .. code-block:: console

        \b
        $ cd reana-demo-root6-roofit  # find an example of REANA workflow
        $ reana_bench.py launch -w roofit50yadage -n 1-50 -f reana-yadage.yaml  # submit and start
        $ reana_bench.py collect -w roofit50yadage  # collect results and save them locally
        $ reana_bench.py analyze -w roofit50yadage -n 1-50  # analyzes results that were saved locally

    How to launch 50 concurrent workflows and collect results (option 2):

        .. code-block:: console

        \b
        $ cd reana-demo-root6-roofit  # find an example of REANA workflow
        $ reana_bench.py submit -w roofit50yadage -n 1-50 -f reana-yadage.yaml  # submit, do not start
        $ reana_bench.py start -w roofit50yadage  -n 1-50  # start workflows
        $ reana_bench.py collect -w roofit50yadage  # collect results and save them locally
        $ reana_bench.py analyze -w roofit50yadage -n 1-50  # analyzes results that were saved locally
    """
    pass


def _build_command(command_type: str, workflow_name: str) -> List[str]:
    return ["reana-client", command_type, "-w", workflow_name]


def _create_workflow(workflow: str, file: str) -> None:
    reana_specification = load_reana_spec(
        click.format_filename(file),
        access_token=REANA_ACCESS_TOKEN,
        skip_validation=True,
    )
    create_workflow(reana_specification, workflow, REANA_ACCESS_TOKEN)


def _upload_workflow(workflow: str) -> None:
    upload_cmd = _build_command("upload", workflow)
    subprocess.run(upload_cmd, stdout=subprocess.DEVNULL)


def _create_and_upload_single_workflow(workflow_name: str, file: str) -> None:
    _create_workflow(workflow_name, file)
    _upload_workflow(workflow_name)


def _build_extended_workflow_name(workflow: str, run_number: int) -> str:
    return f"{workflow}-{run_number}"


def _create_and_upload_workflows(
    workflow: str,
    workflow_range: (int, int),
    file: Optional[str] = None,
    workers: int = WORKERS_DEFAULT_COUNT,
) -> None:
    logging.info(f"Creating and uploading {workflow_range} workflows...")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _create_and_upload_single_workflow,
                _build_extended_workflow_name(workflow, i),
                file,
            )
            for i in range(workflow_range[0], workflow_range[1] + 1)
        ]
        for future in concurrent.futures.as_completed(futures):
            # collect results, in case of exception, it will be raised here
            future.result()


def _get_utc_now_timestamp() -> str:
    return datetime.utcnow().strftime(DATETIME_FORMAT)


def _start_single_workflow(workflow_name: str) -> (str, str):
    # TODO: maybe we can add "after" - "before" start_workflow to compensate for API latency
    start_workflow(workflow_name, REANA_ACCESS_TOKEN, {})
    submit_datetime = _get_utc_now_timestamp()
    return workflow_name, submit_datetime


def _start_workflows_and_record_submit_dates(
    workflow_name: str, workflow_range: (int, int), workers: int = WORKERS_DEFAULT_COUNT
) -> pd.DataFrame:
    logging.info(f"Starting {workflow_range} workflows...")
    df = pd.DataFrame(columns=["name", "submit_date", "submit_number"])
    submit_number = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _start_single_workflow, _build_extended_workflow_name(workflow_name, i)
            )
            for i in range(workflow_range[0], workflow_range[1] + 1)
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


def _get_workflows(workflow_prefix: str) -> pd.DataFrame:
    # TODO: in case of big number of workflows, this function can take a long time
    #  maybe, consider pagination and page size
    cmd = _build_reana_client_list_command(workflow_prefix)
    return pd.DataFrame(json.loads(subprocess.check_output(cmd).decode("ascii")))


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
        lambda x: int(time.mktime(datetime.strptime(x, DATETIME_FORMAT).timetuple()))
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


def _get_workflow_number_from_name(name: str) -> int:
    return int(name.split("-")[-1])


def _derive_metrics(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Deriving metrics...")

    df["workflow_number"] = df.apply(
        lambda row: _get_workflow_number_from_name(row["name"]), axis=1
    )

    df["pending_time"] = _convert_str_date_to_epoch(
        df["started"]
    ) - _convert_str_date_to_epoch(df["submit_date"])
    df["pending_time"] = df["pending_time"].astype(int)

    df["runtime"] = _convert_str_date_to_epoch(
        df["ended"]
    ) - _convert_str_date_to_epoch(df["started"])
    df["runtime"] = df["runtime"].astype(int)
    return df


def _build_execution_progress_plot(
    df: pd.DataFrame, plot_parameters: Dict
) -> (str, Figure):
    title = plot_parameters["title"]
    interval = plot_parameters["time_interval"]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=200, constrained_layout=True)

    for index, row in df.iterrows():
        created_date = datetime.strptime(row["created"], DATETIME_FORMAT)
        started_date = datetime.strptime(row["started"], DATETIME_FORMAT)
        ended_date = datetime.strptime(row["ended"], DATETIME_FORMAT)
        start_submit_date = datetime.strptime(row["submit_date"], DATETIME_FORMAT)
        workflow_number = row["workflow_number"]

        # add created point
        ax.plot(
            created_date,
            workflow_number,
            ".",
            markerfacecolor="grey",
            markersize=1,
            color="grey",
            label="1-created",
        )

        # add asked to start point
        ax.plot(
            start_submit_date,
            workflow_number,
            ".",
            markerfacecolor="darkorange",
            markersize=1,
            color="darkorange",
            label="2-asked to start",
        )

        # add pending line
        ax.hlines(
            workflow_number,
            xmin=start_submit_date,
            xmax=started_date,
            colors=["orange"],
            label="3-pending",
        )

        # add started point
        ax.plot(
            started_date,
            workflow_number,
            ".",
            markerfacecolor="darkgreen",
            markersize=1,
            color="darkgreen",
            label="4-started",
        )

        # add running line
        ax.hlines(
            workflow_number,
            xmin=started_date,
            xmax=ended_date,
            colors=["blue"],
            label="5-running",
        )

        # add finished point
        ax.plot(
            ended_date,
            workflow_number,
            ".",
            markerfacecolor="lightblue",
            markersize=1,
            color="lightblue",
            label="6-finished",
        )

    # force integers on y axis
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # rotate dates on x axis
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    ax.set(title=title)
    ax.set(ylabel="workflow run")
    ax.set_ylim(ymin=df["workflow_number"].min())
    ax.grid(color="black", linestyle="--", alpha=0.15)

    def _build_legend(axes):
        # remove labels duplicates
        # origin - https://stackoverflow.com/a/56253636
        handles, labels = axes.get_legend_handles_labels()
        unique = [
            (h, l)
            for i, (h, l) in enumerate(zip(handles, labels))
            if l not in labels[:i]
        ]

        # sort labels in preferred order according to label values
        unique.sort(key=lambda x: x[1])
        unique = [(h, l.split("-")[1]) for h, l in unique]

        legends = ax.legend(*zip(*unique), loc="upper left")

        # increase size of dots on the legend, indexes according to label order
        legends.legendHandles[0]._legmarker.set_markersize(6)
        legends.legendHandles[1]._legmarker.set_markersize(6)
        legends.legendHandles[3]._legmarker.set_markersize(6)
        legends.legendHandles[5]._legmarker.set_markersize(6)

    _build_legend(ax)
    return "execution_progress", fig


def _build_execution_status_plot(
    df: pd.DataFrame, plot_parameters: Dict
) -> (str, Figure):
    title = plot_parameters["title"]
    total = len(df)
    statuses = list(df["status"].unique())
    stats = {status: len(df[df["status"] == status]) for status in statuses}

    fig, ax = plt.subplots(figsize=(6, 6), constrained_layout=True)

    ax.pie(
        stats.values(),
        labels=stats.keys(),
        autopct=lambda val: round(((val / 100) * sum(stats.values()))),
    )
    ax.text(-1, 1, f"workflows: {total}")
    ax.set(title=title)
    return "execution_status", fig


def _max_min_mean_median(series: pd.Series) -> (int, int, int, int):
    max_value = series.max()
    min_value = series.min()
    mean_value = series.mean()
    median_value = series.median()
    return int(max_value), int(min_value), int(mean_value), int(median_value)


def _build_histogram_plot(
    series: pd.Series, bin_size: int, label: str, title: str,
) -> Figure:
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)

    ax.hist(series, bin_size, color="b", label=label)
    ax.set(xlabel=f"{label} [s] (bin size = {bin_size})")
    ax.set(ylabel="Number of runs")
    ax.legend()

    slowest, fastest, mean, median = _max_min_mean_median(series)

    ax.set(
        title=f"{title}\nfastest: {fastest}, median: {median}, mean: {mean}, slowest: {slowest}"
    )
    return fig


def _build_total_time_histogram(
    df: pd.DataFrame, plot_parameters: Dict
) -> (str, Figure):
    title = plot_parameters["title"]
    return (
        "histogram_total_time",
        _build_histogram_plot(
            df["runtime"] + df["pending_time"], 10, "total_time", title
        ),
    )


def _build_runtime_histogram(df: pd.DataFrame, plot_parameters: Dict) -> (str, Figure):
    title = plot_parameters["title"]
    return (
        "histogram_runtime",
        _build_histogram_plot(df["runtime"], 10, "runtime", title),
    )


def _build_pending_time_histogram(
    df: pd.DataFrame, plot_parameters: Dict
) -> (str, Figure):
    title = plot_parameters["title"]
    return (
        "histogram_pending_time",
        _build_histogram_plot(df["pending_time"], 10, "pending_time", title),
    )


def _build_plots(df: pd.DataFrame, plot_parameters: Dict) -> List[Tuple[str, Figure]]:
    logging.info("Building plots...")

    plots = []
    for build_plot in [
        _build_execution_progress_plot,
        _build_execution_status_plot,
        _build_total_time_histogram,
        _build_runtime_histogram,
        _build_pending_time_histogram,
    ]:
        plot_base_name, figure = build_plot(df, plot_parameters)
        plots.append((plot_base_name, figure))

    return plots


def _save_plots(
    plots: List[Tuple[str, Figure]], workflow: str, workflow_range: (int, int)
) -> None:
    logging.info("Saving plots...")
    for base_name, figure in plots:
        path = Path(
            f"{workflow}_{base_name}_{workflow_range[0]}_{workflow_range[1]}.png"
        )
        figure.savefig(path)


def _build_collected_results_path(workflow: str) -> Path:
    return Path(f"{workflow}_collected_results.csv")


def _build_submitted_results_path(workflow: str) -> Path:
    return Path(f"{workflow}_submitted_results.csv")


def _build_derived_results_path(workflow: str) -> Path:
    return Path(f"{workflow}_analyzed_results.csv")


def _merge_workflows_and_submitted_results(
    workflows: pd.DataFrame, submitted: pd.DataFrame
) -> pd.DataFrame:
    logging.info("Merging workflows and submitted results...")
    return workflows.merge(submitted, on=["name"])


def _save_collected_results(workflow: str, df: pd.DataFrame):
    logging.info("Saving collected results...")
    results_path = _build_collected_results_path(workflow)
    df.to_csv(results_path, index=False)


def submit(
    workflow_prefix: str, workflow_range: (int, int), file: str, workers: int
) -> None:
    """Submit multiple workflows, do not start them."""
    _create_and_upload_workflows(workflow_prefix, workflow_range, file, workers)
    logging.info("Finished creating and uploading workflows.")


def _append_to_existing_submit_results(
    workflow_name: str, new_submit_results: pd.DataFrame
) -> pd.DataFrame:
    """Append new submit results to existing submit results and return them."""

    submitted_results_path = _build_submitted_results_path(workflow_name)

    existing_submit_results = pd.DataFrame()

    if submitted_results_path.exists():
        logging.info("Loading existing submit results. Appending...")
        existing_submit_results = pd.read_csv(submitted_results_path)

    return existing_submit_results.append(new_submit_results, ignore_index=True)


def start(workflow_name: str, workflow_range: (int, int), workers: int) -> None:
    """Start already submitted workflows."""

    submitted_results = _start_workflows_and_record_submit_dates(
        workflow_name, workflow_range, workers
    )

    submitted_results = _append_to_existing_submit_results(
        workflow_name, submitted_results
    )

    logging.info("Saving intermediate submit results...")
    submitted_results_path = _build_submitted_results_path(workflow_name)
    submitted_results.to_csv(submitted_results_path, index=False)
    logging.info("Finished starting workflows.")


workflow_option = click.option(
    "--workflow", "-w", help="Name of the workflow", required=True, type=str
)


def _to_range(workflow_range: str) -> (int, int):
    """Convert string range to an integer tuple with two elements start and end.

    This is callback for click.option.
    """
    workflow_range = workflow_range.split("-")

    # remove empty stings
    workflow_range = [s for s in workflow_range if s]

    if len(workflow_range) != 2:
        logging.error(
            "Workflow range is incorrect. Correct format: 'number-number', e.g '100-200'."
        )
        exit(1)

    return int(workflow_range[0]), int(workflow_range[1])


workflow_range_option = click.option(
    "--number",
    "-n",
    "workflow_range",
    help="Workflow range, inclusive, e.g '10-20'",
    required=True,
    type=str,
    callback=lambda c, p, v: _to_range(v),
)
concurrency_option = click.option(
    "--concurrency",
    "-c",
    help=f"Number of workers to submit workflows, default {WORKERS_DEFAULT_COUNT}",
    type=int,
    default=WORKERS_DEFAULT_COUNT,
)

reana_file_option = click.option(
    "--file",
    "-f",
    help="REANA YAML specification file",
    default="reana.yaml",
    type=click.Path(exists=True),
)


@cli.command(name="submit")
@workflow_option
@workflow_range_option
@reana_file_option
@concurrency_option
def submit_command(
    workflow: str, workflow_range: (int, int), file: str, concurrency: int
) -> NoReturn:
    """Submit workflows, do not start them."""
    try:
        submit(workflow, workflow_range, file, concurrency)
    except Exception as e:
        logging.error(f"Something went wrong during workflow submission: {e}")


@cli.command(name="start")
@workflow_option
@workflow_range_option
@concurrency_option
def start_command(
    workflow: str, workflow_range: (int, int), concurrency: int
) -> NoReturn:
    """Start submitted workflows and record intermediate results."""
    try:
        start(workflow, workflow_range, concurrency)
    except Exception as e:
        logging.error(f"Something went wrong during benchmark launch: {e}")


@cli.command()
@workflow_option
@workflow_range_option
@reana_file_option
@concurrency_option
def launch(
    workflow: str, workflow_range: (int, int), file: str, concurrency: int
) -> NoReturn:
    """Submit and start workflows."""
    try:
        submit(workflow, workflow_range, file, concurrency)
    except Exception as e:
        logging.error(f"Something went wrong during workflow submission: {e}")
        return

    try:
        start(workflow, workflow_range, concurrency)
    except Exception as e:
        logging.error(f"Something went wrong during benchmark launch: {e}")


@cli.command()
@workflow_option
@workflow_range_option
@click.option(
    "--title",
    "-t",
    help="Title of the generated plots.",
    type=str,
    # use workflow parameter as default if title is not provided
    callback=lambda c, p, v: v if v is not None else c.params["workflow"],
)
@click.option(
    "--interval",
    "-i",
    help="Execution progress plot interval in minutes.",
    type=int,
    default=10,
)
def analyze(
    workflow: str, workflow_range: (int, int), title: str, interval: int
) -> NoReturn:
    """Produce various plots and derive metrics based on launch results collected before."""
    results_path = _build_collected_results_path(workflow)
    collected_results = pd.read_csv(results_path)

    derived_results = _derive_metrics(collected_results)

    logging.info("Saving analyzed results...")
    derived_results_path = _build_derived_results_path(workflow)
    derived_results.to_csv(derived_results_path, index=False)

    filtered_df = derived_results[
        derived_results["workflow_number"].between(*workflow_range)
    ]

    # trim workflow_range to existing workflow numbers
    workflow_range = (
        filtered_df["workflow_number"].min(),
        filtered_df["workflow_number"].max(),
    )

    plot_params = {
        "title": title,
        "time_interval": interval,
    }

    plots = _build_plots(filtered_df, plot_params)

    _save_plots(plots, workflow, workflow_range)


@cli.command()
@workflow_option
@click.option(
    "--force",
    "-f",
    help="Force collect results even if workflows are still running",
    default=False,
    is_flag=True,
)
def collect(workflow: str, force: bool) -> NoReturn:
    """Collect workflows results, merge them with intermediate results and save."""
    submitted_results_path = _build_submitted_results_path(workflow)
    submitted_results = pd.read_csv(submitted_results_path)

    workflows = _get_workflows(workflow)
    if _workflows_finished(workflows) or force:
        results = _merge_workflows_and_submitted_results(workflows, submitted_results)
        results = _clean_results(results)
        _save_collected_results(workflow, results)
        logging.info(f"Collected {len(results)} workflows. Finished.")
    else:
        logging.info(
            "Not collecting. Workflows are still running. Use -f option to force collect."
        )


if __name__ == "__main__":
    cli()
