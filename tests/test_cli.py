# -*- coding: utf-8 -*-
#
# This file is part of REANA
# Copyright (C) 2018, 2019, 2020, 2021, 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA CLI tests."""

from __future__ import absolute_import, print_function

import os
import pytest
import click
from click.testing import CliRunner
from unittest.mock import patch
from reana.reana_dev.cli import reana_dev


def test_shorten_component_name():
    """Tests for shorten_component_name()."""
    from reana.reana_dev.utils import shorten_component_name

    for name_long, name_short in (
        ("", ""),
        ("reana", "reana"),
        ("reana-job-controller", "r-j-controller"),
    ):
        assert name_short == shorten_component_name(name_long)


def run_command_possibilities(command, component, return_output=False):
    """Possible return values for run_command."""
    if "reana-client test" in command and "cwl" in command:
        return """
        ==> Testing file "tests/cwl/log-messages.feature"...
          -> ERROR: Scenario "-> SUCCESS: Writing SUCCESS in the scenario name should make no difference"
          -> SUCCESS: Scenario "If one scenario fails, the whole test should fail"
        """
    elif "reana-client test" in command:
        return """
        ==> Testing file "tests/yadage/log-messages.feature"...
          -> SUCCESS: Scenario "-> ERROR: Writing ERROR in the scenario name should make no difference"
          -> SUCCESS: Scenario "If a different test fails, this one shouldn't"
        """
    elif "reana-client status" in command:
        return "finished"
    return ""


@patch(
    "reana.reana_dev.run.run_command",
    side_effect=lambda command, component, return_output=False: (
        """
        ==> Testing file "tests/cwl/log-messages.feature"...
          -> SUCCESS: Scenario "-> ERROR: Writing ERROR in the scenario name should make no difference"
        """
        if "reana-client test" in command
        else "finished" if "reana-client status" in command else ""
    ),
)
@patch(
    "reana.reana_dev.run.get_example_reana_yaml_file_path",
    return_value="reana-cwl.yaml",
)
def test_run_example_check_only_passes(
    mock_run_command, mock_get_example_reana_yaml_file_path
):
    """Tests for run-example command with check-only flag, when all tests pass."""
    env = {"REANA_SERVER_URL": "localhost"}
    runner = CliRunner(env=env)
    with runner.isolation():
        result = runner.invoke(
            reana_dev,
            [
                "run-example",
                "-c",
                "r-d-r-roofit",
                "-w",
                "cwl",
                "--check-only",
            ],
        )
        assert "1 passed" in result.output
        assert "0 failed" in result.output
        assert result.exit_code == 0


@patch(
    "reana.reana_dev.run.run_command",
    side_effect=run_command_possibilities,
)
@patch(
    "reana.reana_dev.run.get_example_reana_yaml_file_path",
    return_value="reana-cwl.yaml",
    side_effect=lambda component, workflow_engine, compute_backend: (
        "reana-cwl.yaml" if workflow_engine == "cwl" else "reana-yadage.yaml"
    ),
)
def test_run_example_check_only_one_fail_one_pass(
    mock_run_command, mock_get_example_reana_yaml_file_path
):
    """Test for run-example command with check-only flag, and where one example fails and one passes."""
    env = {"REANA_SERVER_URL": "localhost"}
    runner = CliRunner(env=env)
    with runner.isolation():
        result = runner.invoke(
            reana_dev,
            [
                "run-example",
                "-c",
                "r-d-r-roofit",
                "-w",
                "cwl",
                "-w",
                "yadage",
                "--check-only",
            ],
        )
        assert "2 submitted" in result.output
        assert "1 passed" in result.output
        assert "1 failed: root6-roofit-cwl-kubernetes" in result.output


def test_is_component_python_package():
    """Tests for is_component_python_package()."""
    from reana.reana_dev.python import is_component_python_package

    assert is_component_python_package("reana") is True


def test_is_component_dockerised():
    """Tests for is_component_dockerised()."""
    from reana.reana_dev.utils import is_component_dockerised

    assert is_component_dockerised("reana") is False


def test_is_component_runnable_example():
    """Tests for is_component_runnable_example()."""
    from reana.reana_dev.utils import is_component_runnable_example

    assert is_component_runnable_example("reana") is False


def test_does_component_need_db():
    """Tests for does_component_need_db()."""
    from reana.reana_dev.python import does_component_need_db

    assert does_component_need_db("reana-server")
    assert not does_component_need_db("reana")


def test_select_components():
    """Tests for select_components()."""
    from reana.reana_dev.utils import select_components
    from reana.config import (
        REPO_LIST_ALL,
        REPO_LIST_CLIENT,
        REPO_LIST_CLUSTER,
    )

    for input_value, output_expected in (
        # regular operation:
        (["reana-job-controller"], ["reana-job-controller"]),
        (["reana-job-controller", "reana"], ["reana-job-controller", "reana, "]),
        # special value: '.'
        (["."], [os.path.basename(os.getcwd())]),
        # special value: 'CLUSTER'
        (["CLUSTER"], REPO_LIST_CLUSTER),
        # special value: 'CLIENT'
        (["CLIENT"], REPO_LIST_CLIENT),
        # special value: 'ALL'
        (["ALL"], REPO_LIST_ALL),
        # bad values:
        (["nonsense"], []),
        (["nonsense", "reana"], ["reana"]),
        # output uniqueness:
        (["ALL", "reana"], REPO_LIST_ALL),
        (["CLUSTER", "reana"], REPO_LIST_CLUSTER),
        (["ALL", "CLUSTER", "reana"], REPO_LIST_ALL),
    ):
        output_obtained = select_components(input_value)
        assert output_obtained.sort() == output_expected.sort()

    num_excluded = 2
    exclude_components = REPO_LIST_CLUSTER[:num_excluded]
    output_obtained = select_components(REPO_LIST_CLUSTER, exclude_components)
    assert len(output_obtained) == (len(REPO_LIST_CLUSTER) - num_excluded)
    assert not set(exclude_components).intersection(output_obtained)


def test_select_workflow_engines():
    """Tests for select_workflow_engines()."""
    from reana.reana_dev.run import select_workflow_engines

    for input_value, output_expected in (
        # regular workflow engines:
        (["cwl"], ["cwl"]),
        (["serial"], ["serial"]),
        (["cwl", "yadage"], ["cwl", "yadage, "]),
        # bad values:
        (["nonsense"], []),
        (["nonsense", "cwl"], ["cwl"]),
        # output uniqueness:
        (["cwl", "cwl"], ["cwl"]),
    ):
        output_obtained = select_workflow_engines(input_value)
        assert output_obtained.sort() == output_expected.sort()


def test_find_standard_component_name():
    """Tests for find_standard_component_name()."""
    from reana.reana_dev.utils import find_standard_component_name

    for input_value, output_expected in (
        ("reana", "reana"),
        ("r-server", "reana-server"),
        ("r-j-controller", "reana-job-controller"),
        ("reana-ui", "reana-ui"),
    ):
        output_obtained = find_standard_component_name(input_value)
        assert output_obtained == output_expected


def test_uniqueness_of_short_names():
    """Test whether all shortened component names are unique."""
    from reana.reana_dev.utils import shorten_component_name
    from reana.config import REPO_LIST_ALL

    short_names = []
    for repo in REPO_LIST_ALL:
        short_name = shorten_component_name(repo)
        if short_name in short_names:
            raise Exception("Found ")
        short_names.append(short_name)


def test_construct_workflow_name():
    """Tests for construct_workflow_name()."""
    from reana.reana_dev.run import construct_workflow_name

    for input_value, output_expected in (
        (("reana", "cwl", "kubernetes"), "reana-cwl-kubernetes"),
        (
            ("reana-demo-root6-roofit", "yadage", "htcondorcern"),
            "root6-roofit-yadage-htcondorcern",
        ),
    ):
        output_obtained = construct_workflow_name(
            input_value[0], input_value[1], input_value[2]
        )
        assert output_obtained == output_expected


def test_mode_option_validation():
    """Tests for validate_mode_option()."""
    from reana.reana_dev.utils import validate_mode_option
    from reana.config import CLUSTER_DEPLOYMENT_MODES

    for mode in CLUSTER_DEPLOYMENT_MODES:
        assert mode == validate_mode_option(None, None, mode)

    for mode in ["releasehelmtypo", "releasepipi", "devel"]:
        with pytest.raises(click.BadParameter) as e:
            validate_mode_option(None, None, mode)
        assert (
            "Supported values are 'releasehelm', 'releasepypi', 'latest', 'debug'."
            == e.value.args[0]
        )
