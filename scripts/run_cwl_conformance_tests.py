#!/usr/bin/env python
#
# This file is part of REANA.
# Copyright (C) 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Run REANA CWL conformance tests and generate markdown results."""

from __future__ import annotations

import logging
import os.path
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import IO, Optional
from urllib.request import urlretrieve

import click
from reana.version import __version__

logging.basicConfig(format="%(asctime)s | %(message)s", level=logging.INFO)


def _save_to_file(markdown: str, filename: str = "output.md") -> None:
    """Save conformance tests output markdown to a file."""
    logging.info("Storing CWL conformance tests output to a file")
    logging.info(f"Final markdown output:\n{markdown}")
    with open(filename, "w") as f:
        f.write(markdown)


def _print_summary(results: list[dict]) -> None:
    """Print summary of CWL conformance tests results."""
    for item in results:
        logging.info(
            f"\nSummary of CWL {item['version']} tests:\n"
            f"{item['conformance']}\n"
            f"Failed tests:\n{item['failed_tests']}\n"
            f"CWL specification path: {item['cwl_path']}\n"
            f"Please find generated badges in '/badges' folder "
            f"and detailed report in 'test_outputs.xml file.\n"
        )


def _generate_markdown(cwl_spec: str, conformance: str, failed_tests: list[str]) -> str:
    """Generate markdown output for CWL conformance tests."""
    time = datetime.now().strftime("%Y-%m-%d")
    passed, failed, unsupported = conformance.split(",")
    tests_list = "".join([f"\t- {test}\n" for test in failed_tests])
    return (
        f"\n# CWL {cwl_spec} specification conformance results\n\n"
        f"REANA {__version__} tested on {time}\n\n"
        f"- {passed}\n"
        f"- {failed.strip()}\n"
        f"{tests_list}"
        f"- {unsupported.strip()}\n"
    )


def _parse_output(pipe: Optional[IO[bytes]]) -> tuple[str, list[str]]:
    """Parse the output of CWL conformance tests."""
    failed_tests = []
    conformance = ""
    test_name = ""
    for line in iter(pipe.readline, b""):
        line = line.decode("utf-8").strip("\r\n")
        if not line:
            continue
        if "Test [" in line:
            test_name = line
        if "failed:" in line or "timed out:" in line:
            failed_tests.append(test_name)
        if "tests passed" in line:
            conformance = line
        logging.info(line)

    return conformance, failed_tests


def _run_cwl_tests(cwl_path: str, tests_path: str) -> tuple[str, list[str]]:
    """Run CWL conformance tests for a given version."""
    cmd = [
        "cwltest",
        "--tool=reana-cwl-runner",
        "--test={}".format(tests_path),
        "--badgedir={}".format(os.path.join(cwl_path, "badges")),
        "--junit-xml={}".format(os.path.join(cwl_path, "test_outputs.xml")),
        "--basedir={}".format(os.path.join(cwl_path, "v1.0")),
    ]

    logging.info(f"Running CWL tests: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd, cwd=cwl_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    conformance, failed_tests = _parse_output(process.stdout)
    process.wait()
    return conformance, failed_tests


def _download_cwl_spec(repo: str, tag: str) -> str:
    """Downloading CWL specification for a given version."""
    logging.info(f"Downloading CWL specification for {repo}.")
    cwl_path = tempfile.mkdtemp()
    cwl_zip = os.path.join(cwl_path, "cwl.zip")
    urlretrieve(
        f"https://www.github.com/common-workflow-language/{repo}/zipball/{tag}/",
        cwl_zip,
    )
    shutil.unpack_archive(cwl_zip, cwl_path)
    os.remove(cwl_zip)
    cwl_dir = os.listdir(cwl_path)[0]
    return os.path.join(cwl_path, cwl_dir)


def _launch_cwl_tests(cwl_spec: str, repo: str, tag: str, tests_path: str) -> dict:
    """Download CWL specification and run CWL conformance tests."""
    logging.info(f"Launching CWL {cwl_spec} test suit.")
    cwl_path = _download_cwl_spec(repo, tag)
    tests_path = os.path.join(cwl_path, tests_path)
    logging.info(f"Test suit for {cwl_spec} CWL spec is located at {tests_path}")
    conformance, failed_tests = _run_cwl_tests(cwl_path, tests_path)
    logging.info(
        f"Output of CWL {cwl_spec} tests:\n{conformance}\n"
        f"Failed tests:\n{failed_tests}"
    )
    return {
        "version": cwl_spec,
        "conformance": conformance,
        "failed_tests": failed_tests,
        "cwl_path": cwl_path,
        "markdown": _generate_markdown(cwl_spec, conformance, failed_tests),
    }


@click.command()
@click.option(
    "--version",
    type=str,
    help="Specify CWL version to test, e.g 'v1.2'. [default=ALL]",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default="output.md",
    help="Path where to save Markdown report. [default=output.md]",
)
def run_tests(version: Optional[str], output: str) -> None:
    """Run CWL conformance tests. Generate markdown report.

    The script requires python 3.7+.

    Steps to run CWL conformance tests:

        .. code-block:: console

        \b
        $ pip install reana-client  # install reana-client to use reana-cwl-runner
        $ pip install cwltest  # install CWL test tool
        $ export REANA_ACCESS_TOKEN=<your access token>
        $ export REANA_SERVER_URL=<your REANA server URL>
        $ reana-client ping  # check if REANA server is reachable
        $ python run_cwl_conformance_tests.py --version v1.2  # to run tests for CWL v1.2 only
        $ python run_cwl_conformance_tests.py  # to run tests for all CWL versions

    WARNING: This script is working on Linux, but not on MacOS. You will need to use Docker to run it on MacOS.

        .. code-block:: console

        \b
        # execute Docker command below, in the "reana/scripts/" folder
        $ docker run --rm -v $PWD:/pwd --network="host" --name cwl-test -it python:3.8.12 bash
        $ git clone https://github.com/reanahub/reana.git  # inside container
        $ pip install -e reana/  # inside container
        $ cd /pwd  # change folders inside container
        # repeat steps to run CWL tests

    """
    specs = [
        {
            "version": "v1.0",
            "repo": "common-workflow-language",
            "tag": "v1.0.2",
            "tests_path": "v1.0/conformance_test_v1.0.yaml",
        },
        {
            "version": "v1.1",
            "repo": "cwl-v1.1",
            "tag": "v1.1.0",
            "tests_path": "conformance_tests.yaml",
        },
        {
            "version": "v1.2",
            "repo": "cwl-v1.2",
            "tag": "v1.2.0",
            "tests_path": "conformance_tests.yaml",
        },
    ]
    markdown = ""
    results = []
    selected_specs = specs

    if version:
        selected_specs = [spec for spec in specs if spec["version"] == version]

    for spec in selected_specs:
        result = _launch_cwl_tests(
            spec["version"], spec["repo"], spec["tag"], spec["tests_path"]
        )
        markdown += result["markdown"]
        results.append(result)
    _save_to_file(markdown, output)
    _print_summary(results)


if __name__ == "__main__":
    run_tests()
