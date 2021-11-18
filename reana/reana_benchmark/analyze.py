# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Responsible for plotting graphs based on collected benchmark results."""

import time
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import List, Dict, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from reana.reana_benchmark.collect import build_collected_results_path
from reana.reana_benchmark.utils import logger
from reana.reana_benchmark.config import DATETIME_FORMAT, WorkflowStatus


STATUS_TO_COLOR = {
    WorkflowStatus.created: "grey",
    WorkflowStatus.queued: "darkgoldenrod",
    WorkflowStatus.pending: "darkorange",
    WorkflowStatus.running: "blue",
    WorkflowStatus.failed: "firebrick",
    WorkflowStatus.finished: "forestgreen",
}


def _get_workflow_number_from_name(name: str) -> int:
    return int(name.split("-")[-1])


def _convert_str_date_to_epoch(s: str) -> int:
    return int(time.mktime(datetime.strptime(s, DATETIME_FORMAT).timetuple()))


def _derive_metrics(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Deriving metrics...")

    df["workflow_number"] = df.apply(
        lambda row: _get_workflow_number_from_name(row["name"]), axis=1
    )

    collected_date = df["collected_date"].iloc[0]

    def _calculate_difference(
        row: pd.Series, start_column: str, end_column: str
    ) -> int:
        """Calculate difference between two date times in string format."""
        start_date = row[start_column]
        end_date = row[end_column]

        start_date_exists = not pd.isna(start_date)
        end_date_exists = not pd.isna(end_date)

        if start_date_exists and end_date_exists:
            return _convert_str_date_to_epoch(end_date) - _convert_str_date_to_epoch(
                start_date
            )

        # if only start date exists, take current time as ended
        if start_date_exists and not end_date_exists:
            return _convert_str_date_to_epoch(
                collected_date
            ) - _convert_str_date_to_epoch(start_date)

        return 0

    df["pending_time"] = df.apply(
        partial(
            _calculate_difference,
            start_column="asked_to_start_date",
            end_column="started",
        ),
        axis=1,
    )
    df["pending_time"] = df["pending_time"].astype(int)

    df["runtime"] = df.apply(
        partial(_calculate_difference, start_column="started", end_column="ended"),
        axis=1,
    )
    df["runtime"] = df["runtime"].astype(int)
    return df


def _build_plots(df: pd.DataFrame, plot_parameters: Dict) -> List[Tuple[str, Figure]]:
    logger.info("Building plots...")

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


def _build_execution_progress_plot(
    df: pd.DataFrame, plot_parameters: Dict
) -> (str, Figure):
    title = plot_parameters["title"]
    interval = plot_parameters["time_interval"]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=200, constrained_layout=True)

    collected_date = df["collected_date"].iloc[0]
    collected_datetime = datetime.strptime(collected_date, DATETIME_FORMAT)

    for index, row in df.iterrows():
        workflow_number = row["workflow_number"]
        workflow_status = row["status"]

        created_date = datetime.strptime(row["created"], DATETIME_FORMAT)

        asked_to_start_date_exists = not pd.isna(row["asked_to_start_date"])
        started_exists = not pd.isna(row["started"])
        ended_exists = not pd.isna(row["ended"])

        # add created point, should always exist
        ax.plot(
            created_date,
            workflow_number,
            ".",
            markerfacecolor=STATUS_TO_COLOR[WorkflowStatus.created],
            markersize=3,
            color=STATUS_TO_COLOR[WorkflowStatus.created],
            label="1-created",
        )

        if asked_to_start_date_exists:
            asked_to_start_date = datetime.strptime(
                row["asked_to_start_date"], DATETIME_FORMAT
            )
            # add asked to start point
            ax.plot(
                asked_to_start_date,
                workflow_number,
                ".",
                markerfacecolor="navy",
                markersize=3,
                color="navy",
                label="2-asked to start",
            )

            if started_exists:
                started_date = datetime.strptime(row["started"], DATETIME_FORMAT)

                # add started point
                ax.plot(
                    started_date,
                    workflow_number,
                    ".",
                    markerfacecolor="sienna",
                    markersize=3,
                    color="sienna",
                    label="4-started",
                )

                if ended_exists:
                    ended_date = datetime.strptime(row["ended"], DATETIME_FORMAT)

                    # add ended point to indicate whatever workflow finished or failed
                    ax.plot(
                        ended_date,
                        workflow_number,
                        ".",
                        markerfacecolor=STATUS_TO_COLOR[workflow_status],
                        markersize=4 if workflow_status == WorkflowStatus.failed else 3,
                        # zorder, acts similar to z-index
                        zorder=10 if workflow_status == WorkflowStatus.failed else 5,
                        color=STATUS_TO_COLOR[workflow_status],
                        label=f"6-{workflow_status}",
                    )
                else:
                    ended_date = collected_datetime

                # draw running line
                ax.hlines(
                    workflow_number,
                    xmin=started_date,
                    xmax=ended_date,
                    colors=[STATUS_TO_COLOR[WorkflowStatus.running]],
                    label="5-running",
                )
            else:
                started_date = collected_datetime

            # add pending line
            ax.hlines(
                workflow_number,
                xmin=asked_to_start_date,
                xmax=started_date,
                colors=["orange"],
                label="3-pending",
            )

    # force integers on y axis
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # rotate dates on x axis
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    ax.set(title=title)
    ax.set(ylabel="workflow run")

    ax.set_ylim(ymin=df["workflow_number"].min() - 1)

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

        # sort labels in order of leading number in value if label (e.g 1-created)
        unique.sort(key=lambda x: x[1])

        # remove leading number from label
        unique = [(h, l.split("-")[1]) for h, l in unique]

        legends = ax.legend(*zip(*unique), loc="upper left")

        # increase size of points on the legend to be more visible
        for handler in legends.legendHandles:
            if hasattr(handler, "_legmarker"):
                handler._legmarker.set_markersize(6)

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

    patches, texts, pcts = ax.pie(
        stats.values(),
        labels=stats.keys(),
        autopct=lambda val: round(((val / 100) * sum(stats.values()))),
    )

    for i, patch in enumerate(patches):
        status = texts[i]._text
        color = STATUS_TO_COLOR[status]
        patch.set_color(color)

    plt.setp(pcts, color="white", fontsize=11, fontweight=600)
    plt.setp(texts, fontweight=600)

    ax.text(-1.3, 1.1, f"workflows: {total}", fontweight=600, fontsize=12)
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


def _save_plots(
    plots: List[Tuple[str, Figure]], workflow: str, workflow_range: (int, int)
) -> None:
    logger.info("Saving plots...")
    for base_name, figure in plots:
        path = Path(
            f"{workflow}_{base_name}_{workflow_range[0]}_{workflow_range[1]}.png"
        )
        figure.savefig(path)


def analyze(
    workflow_prefix: str, workflow_range: (int, int), plot_params: Dict
) -> None:  # noqa: D103
    results_path = build_collected_results_path(workflow_prefix)
    collected_results = pd.read_csv(results_path)

    collected_results = _derive_metrics(collected_results)

    filtered_df = collected_results[
        collected_results["workflow_number"].between(*workflow_range)
    ]

    # trim workflow_range to existing workflow numbers
    workflow_range = (
        filtered_df["workflow_number"].min(),
        filtered_df["workflow_number"].max(),
    )

    plots = _build_plots(filtered_df, plot_params)

    _save_plots(plots, workflow_prefix, workflow_range)
