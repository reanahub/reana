# -*- coding: utf-8 -*-
#
# This file is part of REANA
# Copyright (C) 2024, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA CLI cluster command tests."""

from __future__ import absolute_import, print_function

import copy

import pytest
import yaml
from click.testing import CliRunner
from mock import patch
from unittest.mock import call


def _helm_install_command(values_dict):
    """Render the expected inline Helm values document."""
    values_yaml = yaml.dump(values_dict, width=100000) if values_dict else ""
    return (
        "cat <<EOF | helm install reana helm/reana -n default --create-namespace --wait -f -\n"
        f"{values_yaml}\n"
        "EOF"
    )


@pytest.mark.parametrize(
    "mode, shared_storage_backend, values_files, expected",
    [
        (
            "latest",
            "hostpath",
            (),
            ("helm/configurations/values-dev.yaml",),
        ),
        ("releasehelm", "hostpath", (), ()),
        (
            "latest",
            "cephfs",
            (),
            (
                "helm/configurations/values-dev.yaml",
                "helm/configurations/values-dev-cephfs.yaml",
            ),
        ),
        (
            "latest",
            "hostpath",
            ("helm/configurations/values-dev-cephfs.yaml",),
            (
                "helm/configurations/values-dev.yaml",
                "helm/configurations/values-dev-cephfs.yaml",
            ),
        ),
    ],
)
def test_default_cluster_values_files(
    mode, shared_storage_backend, values_files, expected
):
    """Cluster deploy should layer local dev values files predictably."""
    from reana.reana_dev.cluster import default_cluster_values_files

    assert (
        default_cluster_values_files(mode, shared_storage_backend, values_files)
        == expected
    )


@patch("reana.reana_dev.cluster.display_message")
def test_validate_shared_storage_backend_rejects_non_kind_cephfs(
    display_message_mock,
):
    """Local CephFS must remain explicitly scoped to Kind for now."""
    from reana.reana_dev.cluster import validate_shared_storage_backend

    with pytest.raises(SystemExit):
        validate_shared_storage_backend("colima/k3s", "cephfs")

    display_message_mock.assert_called_once_with(
        "[ERROR] Local CephFS shared storage is currently supported only with --kubernetes kind. Exiting.",
        "reana",
    )


@pytest.mark.parametrize(
    "options, initial_values, expected_values_files, expected_final_values, run_command_side_effects, exit_code",
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
            {},
            ("alternative-values-dev.yaml",),
            {
                "components": {"reana_ui": {"enabled": False}},
                "debug": {"enabled": True},
            },
            [None] * 6,
            0,
        ),
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
            ],
            {
                "debug": {"enabled": True},
                "components": {
                    "reana_workflow_controller": {
                        "environment": {"REANA_OPENSEARCH_ENABLED": True}
                    }
                },
            },
            ("helm/configurations/values-dev.yaml",),
            {
                "debug": {"enabled": True},
                "components": {
                    "reana_workflow_controller": {
                        "environment": {"REANA_OPENSEARCH_ENABLED": True}
                    }
                },
            },
            [None] * 4,
            0,
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
            {},
            None,
            {},
            [None] * 4,
            0,
        ),
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
                "--shared-storage-backend",
                "cephfs",
            ],
            {
                "shared_storage": {
                    "backend": "cephfs",
                    "fs_group": 0,
                    "storage_class_name": "rook-cephfs",
                }
            },
            (
                "helm/configurations/values-dev.yaml",
                "helm/configurations/values-dev-cephfs.yaml",
            ),
            {
                "shared_storage": {
                    "backend": "cephfs",
                    "fs_group": 0,
                    "storage_class_name": "rook-cephfs",
                }
            },
            [None] * 4,
            0,
        ),
        (
            [
                "--admin-email",
                "john.doe@reana.io",
                "--admin-password",
                "admin",
            ],
            {},
            ("helm/configurations/values-dev.yaml",),
            {},
            [None, None, None, ValueError()],
            1,
        ),
    ],
)
@patch("reana.reana_dev.cluster.get_srcdir")
@patch("reana.reana_dev.cluster.load_cluster_values")
@patch("reana.reana_dev.cluster.run_command")
def test_cluster_deploy(
    run_command_mock,
    load_cluster_values_mock,
    get_srcdir_mock,
    options,
    initial_values,
    expected_values_files,
    expected_final_values,
    run_command_side_effects,
    exit_code,
):
    """Test cluster-deploy command."""
    from reana.reana_dev.cluster import cluster_deploy

    run_command_mock.side_effect = run_command_side_effects
    load_cluster_values_mock.return_value = copy.deepcopy(initial_values)
    get_srcdir_mock.return_value = "/code/src/reana"

    runner = CliRunner()
    result = runner.invoke(cluster_deploy, options)

    if expected_values_files is None:
        load_cluster_values_mock.assert_not_called()
    else:
        load_cluster_values_mock.assert_called_once_with(expected_values_files)

    expected_run_command_calls = []
    if "--mode" in options and options[options.index("--mode") + 1] == "debug":
        expected_run_command_calls.extend(
            [
                call("reana-dev python-install-eggs", "reana"),
                call("reana-dev git-submodule --update", "reana"),
            ]
        )
    expected_run_command_calls.extend(
        [
            call("helm dep update helm/reana", "reana"),
            call(_helm_install_command(expected_final_values), "reana"),
            call("kubectl config set-context --current --namespace=default", "reana"),
            call(
                "/code/src/reana/scripts/create-admin-user.sh default reana john.doe@reana.io admin",
                "reana",
            ),
        ]
    )

    assert run_command_mock.call_args_list == expected_run_command_calls
    assert result.exit_code == exit_code


@patch("reana.reana_dev.cluster.get_srcdir")
@patch("reana.reana_dev.cluster.run_command")
def test_cluster_create_cephfs_invokes_kind_helpers(run_command_mock, get_srcdir_mock):
    """Kind cluster creation should own the local CephFS bootstrap steps."""
    from reana.reana_dev.cluster import cluster_create

    run_command_mock.side_effect = ["", None, None, None, None, None, None]
    get_srcdir_mock.return_value = "/code/src/reana"

    result = CliRunner().invoke(
        cluster_create,
        ["--shared-storage-backend", "cephfs"],
    )

    assert result.exit_code == 0
    assert run_command_mock.call_args_list[0] == call(
        "docker version", return_output=True
    )
    cluster_create_cmd = run_command_mock.call_args_list[1]
    assert cluster_create_cmd.args[1] == "reana"
    assert "kind create cluster" in cluster_create_cmd.args[0]
    assert "containerPort: 30080" in cluster_create_cmd.args[0]
    assert "containerPort: 30443" in cluster_create_cmd.args[0]
    assert 'node-labels: "ingress-ready=true"' in cluster_create_cmd.args[0]
    assert run_command_mock.call_args_list[2:] == [
        call(
            "docker exec kind-control-plane sh -c 'mkdir -p /var/reana && chmod g+rwx /var/reana'",
            "reana",
        ),
        call(
            ["/bin/sh", "/code/src/reana/scripts/setup-kind-rook-loop-devices.sh"],
            "reana",
        ),
        call(
            ["/bin/sh", "/code/src/reana/scripts/deploy-kind-rook-cephfs.sh"],
            "reana",
        ),
        call("reana-dev docker-pull -c reana", "reana"),
        call("reana-dev kind-load-docker-image -c reana", "reana"),
    ]


@patch("reana.reana_dev.cluster.get_srcdir")
@patch("reana.reana_dev.cluster.run_command")
def test_cluster_delete_cephfs_invokes_kind_helpers(run_command_mock, get_srcdir_mock):
    """Kind cluster deletion should tear local CephFS down before removing Kind."""
    from reana.reana_dev.cluster import cluster_delete

    get_srcdir_mock.return_value = "/code/src/reana"

    result = CliRunner().invoke(
        cluster_delete,
        ["--shared-storage-backend", "cephfs"],
    )

    assert result.exit_code == 0
    assert run_command_mock.call_args_list == [
        call(
            ["/bin/sh", "/code/src/reana/scripts/undeploy-kind-rook-cephfs.sh"],
            "reana",
        ),
        call(
            ["/bin/sh", "/code/src/reana/scripts/cleanup-kind-rook-loop-devices.sh"],
            "reana",
        ),
        call("kind delete cluster", "reana"),
    ]
