# -*- coding: utf-8 -*-
#
# This file is part of REANA
# Copyright (C) 2024 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA CLI cluster command tests."""

from __future__ import absolute_import, print_function

import pytest

from click.testing import CliRunner
from mock import patch, mock_open
from unittest.mock import call


helm_command = """cat <<EOF | helm install reana helm/reana -n default --create-namespace --wait -f -
components:
  reana_ui:
    enabled: false
debug:
  enabled: true

EOF"""


@pytest.mark.parametrize(
    "options, run_command_calls, run_command_side_effects, exit_code, open_calls, open_mock_read_value",
    [
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
                "--values",
                "alternative-values-dev.yaml",
                "--mode",
                "debug",
                "--exclude-components",
                "reana-ui,reana-workflow-controller",
            ],
            [
                call("reana-dev python-install-eggs", "reana"),
                call("reana-dev git-submodule --update", "reana"),
                call("helm dep update helm/reana", "reana"),
                call(helm_command, "reana"),
                call(
                    "kubectl config set-context --current --namespace=default", "reana"
                ),
                call(
                    "/code/src/reana/scripts/create-admin-user.sh default reana john.doe@reana.io admin",
                    "reana",
                ),
            ],
            [None] * 6,
            0,
            [call("/code/src/reana/alternative-values-dev.yaml")],
            "",
        ),
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
            ],
            [
                call("helm dep update helm/reana", "reana"),
                call(
                    "cat <<EOF | helm install reana helm/reana -n default --create-namespace --wait -f -\ncomponents:\n  reana_workflow_controller:\n    environment:\n      REANA_OPENSEARCH_ENABLED: true\ndebug:\n  enabled: true\n\nEOF",
                    "reana",
                ),
                call(
                    "kubectl config set-context --current --namespace=default", "reana"
                ),
                call(
                    "/code/src/reana/scripts/create-admin-user.sh default reana john.doe@reana.io admin",
                    "reana",
                ),
            ],
            [None] * 4,
            0,
            [call("/code/src/reana/helm/configurations/values-dev.yaml")],
            "debug:\n  enabled: true\ncomponents:\n  reana_workflow_controller:\n    environment:\n      REANA_OPENSEARCH_ENABLED: true\n",
        ),
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
                "--mode",
                "releasehelm",
            ],
            [
                call("helm dep update helm/reana", "reana"),
                call(
                    "cat <<EOF | helm install reana helm/reana -n default --create-namespace --wait -f -\n\nEOF",
                    "reana",
                ),
                call(
                    "kubectl config set-context --current --namespace=default", "reana"
                ),
                call(
                    "/code/src/reana/scripts/create-admin-user.sh default reana john.doe@reana.io admin",
                    "reana",
                ),
            ],
            [None] * 4,
            0,
            [],
            "",
        ),
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
            ],
            [
                call("helm dep update helm/reana", "reana"),
                call(
                    "cat <<EOF | helm install reana helm/reana -n default --create-namespace --wait -f -\n\nEOF",
                    "reana",
                ),
                call(
                    "kubectl config set-context --current --namespace=default", "reana"
                ),
                call(
                    "/code/src/reana/scripts/create-admin-user.sh default reana john.doe@reana.io admin",
                    "reana",
                ),
            ],
            [None, None, None, ValueError()],
            1,
            [call("/code/src/reana/helm/configurations/values-dev.yaml")],
            "",
        ),
    ],
)
@patch("reana.reana_dev.cluster.get_srcdir")
@patch("reana.reana_dev.cluster.run_command")
@patch("builtins.open", new_callable=mock_open)
def test_cluster_deploy(
    open_mock,
    run_command_mock,
    get_srcdir_mock,
    options,
    run_command_calls,
    run_command_side_effects,
    exit_code,
    open_calls,
    open_mock_read_value,
):
    """Test cluster-deploy command."""
    from reana.reana_dev.cluster import cluster_deploy

    run_command_count = len(run_command_calls)
    open_mock.return_value.read.return_value = open_mock_read_value

    run_command_mock.side_effect = run_command_side_effects
    get_srcdir_mock.return_value = "/code/src/reana"
    runner = CliRunner()
    result = runner.invoke(cluster_deploy, options)
    assert run_command_mock.call_count == run_command_count
    assert run_command_mock.call_args_list == run_command_calls
    assert result.exit_code == exit_code
    assert open_mock.call_count == len(open_calls)
    assert open_mock.call_args_list == open_calls
