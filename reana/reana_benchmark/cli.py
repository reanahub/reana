#!/usr/bin/env python
# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Combines reana-benchmark modules into CLI commands."""

import logging
from typing import NoReturn

import click
import urllib3

from reana.reana_benchmark.analyze import analyze
from reana.reana_benchmark.collect import collect
from reana.reana_benchmark.config import WORKERS_DEFAULT_COUNT
from reana.reana_benchmark.start import start
from reana.reana_benchmark.submit import submit
from reana.reana_benchmark.utils import logger

urllib3.disable_warnings()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.WARNING,
    force=True,
)


@click.group()
def reana_benchmark():  # noqa: D301
    """reana-benchmark script - runs single workflow multiple times, collects results, analyzes them.

    Prerequisites:

        - install reana-client 0.8.x, pandas and matplotlib Python packages
        - set REANA_ACCESS_TOKEN and REANA_SERVER_URL

    How to launch 50 concurrent workflows and collect results (option 1):

        .. code-block:: console

        \b
        $ cd reana-demo-root6-roofit  # find an example of REANA workflow
        $ reana-benchmark launch -w roofit50yadage -n 1-50 -f reana-yadage.yaml  # submit and start
        $ reana-benchmark collect -w roofit50yadage  # collect results and save them locally
        $ reana-benchmark analyze -w roofit50yadage -n 1-50  # analyzes results that were saved locally

    How to launch 50 concurrent workflows and collect results (option 2):

        .. code-block:: console

        \b
        $ cd reana-demo-root6-roofit  # find an example of REANA workflow
        $ reana-benchmark submit -w roofit50yadage -n 1-50 -f reana-yadage.yaml  # submit, do not start
        $ reana-benchmark start -w roofit50yadage  -n 1-50  # start workflows
        $ reana-benchmark collect -w roofit50yadage  # collect results and save them locally
        $ reana-benchmark analyze -w roofit50yadage -n 1-50  # analyzes results that were saved locally
    """
    pass


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
        logger.error(
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


@reana_benchmark.command(name="submit")
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
        logger.error(f"Something went wrong during workflow submission: {e}")


@reana_benchmark.command(name="start")
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
        logger.error(f"Something went wrong during benchmark launch: {e}")


@reana_benchmark.command()
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
        logger.error(f"Something went wrong during workflow submission: {e}")
        return

    try:
        start(workflow, workflow_range, concurrency)
    except Exception as e:
        logger.error(f"Something went wrong during benchmark launch: {e}")


@reana_benchmark.command(name="analyze")
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
def analyze_command(
    workflow: str, workflow_range: (int, int), title: str, interval: int
) -> NoReturn:
    """Produce plots based on workflows results collected before."""
    plot_params = {
        "title": title,
        "time_interval": interval,
    }

    try:
        analyze(workflow, workflow_range, plot_params)
    except Exception as e:
        logger.error(f"Something went wrong when analyzing results: {e}")


@reana_benchmark.command(name="collect")
@workflow_option
@click.option(
    "--force",
    "-f",
    help="Force collect results even if workflows are still running",
    default=False,
    is_flag=True,
)
def collect_command(workflow: str, force: bool) -> NoReturn:
    """Collect workflows results, merge them with intermediate results and save."""
    try:
        collect(workflow, force)
    except Exception as e:
        logger.error(f"Something went wrong when collecting results: {e}")
