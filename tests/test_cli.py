# -*- coding: utf-8 -*-
#
# This file is part of REANA
# Copyright (C) 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA CLI tests."""

from __future__ import absolute_import, print_function

import os
from pathlib import Path
import sys
from unittest.mock import call, patch

import click
from click.testing import CliRunner
import pytest

from reana.reana_dev.cli import reana_dev
from reana.reana_dev.run import ensure_client_login


def test_client_setup_environment_has_only_effective_url_option():
    """The environment helper should not advertise ignored cluster options."""
    runner = CliRunner()

    help_result = runner.invoke(reana_dev, ["client-setup-environment", "--help"])
    result = runner.invoke(
        reana_dev,
        [
            "client-setup-environment",
            "--server-hostname",
            "http://reana.example.org:8080",
        ],
    )

    assert help_result.exit_code == 0
    assert "--insecure-url" not in help_result.output
    assert "--namespace" not in help_result.output
    assert "--instance-name" not in help_result.output
    assert result.exit_code == 0
    assert (
        result.output == "reana-client login --server http://reana.example.org:8080\n"
    )


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
    if " test -w " in command and "cwl" in command:
        return """
        ==> Testing file "tests/cwl/log-messages.feature"...
          -> ERROR: Scenario "-> SUCCESS: Writing SUCCESS in the scenario name should make no difference"
          -> SUCCESS: Scenario "If one scenario fails, the whole test should fail"
        """
    elif " test -w " in command:
        return """
        ==> Testing file "tests/yadage/log-messages.feature"...
          -> SUCCESS: Scenario "-> ERROR: Writing ERROR in the scenario name should make no difference"
          -> SUCCESS: Scenario "If a different test fails, this one shouldn't"
        """
    elif " status -w " in command:
        return "finished"
    return ""


@pytest.mark.parametrize(
    ("client_options", "client_executable"),
    (
        ([], "reana-client"),
        (["--client", "python"], "reana-client"),
        (["--client", "go"], "reana-client-go"),
    ),
)
@patch("reana.reana_dev.run.ensure_client_login")
@patch("reana.reana_dev.run.shutil.which")
@patch(
    "reana.reana_dev.run.run_command",
    side_effect=lambda command, component, return_output=False: (
        """
        ==> Testing file "tests/cwl/log-messages.feature"...
          -> SUCCESS: Scenario "-> ERROR: Writing ERROR in the scenario name should make no difference"
        """
        if " test -w " in command
        else "finished" if " status -w " in command else ""
    ),
)
@patch(
    "reana.reana_dev.run.get_example_reana_yaml_file_path",
)
def test_run_example_check_only_passes(
    mock_get_example_reana_yaml_file_path,
    mock_run_command,
    mock_which,
    mock_ensure_client_login,
    tmp_path,
    client_options,
    client_executable,
):
    """Tests for run-example command with check-only flag, when all tests pass."""
    yaml_file = tmp_path / "reana-cwl.yaml"
    yaml_file.write_text("tests:\n  files:\n    - {file: output.txt}\n")
    mock_get_example_reana_yaml_file_path.return_value = str(yaml_file)
    # Running an installed client does not require its build tools.
    mock_which.side_effect = lambda executable: (
        "/fake/client" if executable == client_executable else None
    )
    runner = CliRunner(env={"REANA_SERVER_URL": "localhost"})
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
                *client_options,
            ],
        )
        assert "1 passed" in result.output
        assert "0 failed" in result.output
        assert result.exit_code == 0
        assert any(
            f"{client_executable} status" in invocation.args[0]
            for invocation in mock_run_command.call_args_list
        )


@patch("reana.reana_dev.run.ensure_client_login")
@patch("reana.reana_dev.run.shutil.which", return_value="/fake/client")
@patch(
    "reana.reana_dev.run.run_command",
    side_effect=run_command_possibilities,
)
@patch(
    "reana.reana_dev.run.get_example_reana_yaml_file_path",
)
def test_run_example_check_only_one_fail_one_pass(
    mock_get_example_reana_yaml_file_path,
    mock_run_command,
    mock_which,
    mock_ensure_client_login,
    tmp_path,
):
    """Test for run-example command with check-only flag, and where one example fails and one passes."""
    cwl_yaml = tmp_path / "reana-cwl.yaml"
    cwl_yaml.write_text("tests:\n  files:\n    - {file: output.txt}\n")
    yadage_yaml = tmp_path / "reana-yadage.yaml"
    yadage_yaml.write_text("tests:\n  files:\n    - {file: output.txt}\n")
    mock_get_example_reana_yaml_file_path.side_effect = (
        lambda component, workflow_engine, compute_backend: (
            str(cwl_yaml) if workflow_engine == "cwl" else str(yadage_yaml)
        )
    )
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


@patch("reana.reana_dev.run.ensure_client_login")
@patch("reana.reana_dev.run.shutil.which", return_value="/fake/client")
@patch(
    "reana.reana_dev.run.run_command",
    side_effect=lambda command, component, return_output=False: (
        "1"
        if " logs -w " in command
        else (
            "bmass.png\njpsimass.png"
            if " ls -w " in command
            else "finished" if " status -w " in command else ""
        )
    ),
)
@patch(
    "reana.reana_dev.run.get_example_reana_yaml_file_path",
)
def test_run_example_check_only_without_gherkin_tests(
    mock_get_example_reana_yaml_file_path,
    mock_run_command,
    mock_which,
    mock_ensure_client_login,
    tmp_path,
):
    """Tests for run-example command with check-only flag for examples without Gherkin tests."""
    yaml_file = tmp_path / "reana.yaml"
    yaml_file.write_text("workflow:\n  type: snakemake\n")
    mock_get_example_reana_yaml_file_path.return_value = str(yaml_file)
    env = {"REANA_SERVER_URL": "localhost"}
    runner = CliRunner(env=env)
    with runner.isolation():
        result = runner.invoke(
            reana_dev,
            [
                "run-example",
                "-c",
                "r-d-l-r-b2jpsik",
                "-w",
                "snakemake",
                "--check-only",
            ],
        )
        assert "1 passed" in result.output
        assert "0 failed" in result.output
        assert result.exit_code == 0


def _create_client_source_directories(tmp_path):
    """Create minimal Python and Go client source directories."""
    from reana.config import REPO_LIST_CLIENT

    source_directories = {}
    for component in REPO_LIST_CLIENT:
        source_directory = tmp_path / component
        source_directory.mkdir()
        source_directories[component] = source_directory
        if component == "reana-client-go":
            (source_directory / "go.mod").write_text("module example.org/client\n")
        else:
            (source_directory / "setup.py").write_text("")
    return source_directories


def test_client_install_builds_both_clients(tmp_path):
    """Test that client-install installs Python packages and builds Go."""
    from reana.config import REPO_LIST_CLIENT

    source_directories = _create_client_source_directories(tmp_path)
    scripts_dir = tmp_path / "bin"
    scripts_dir.mkdir()

    def get_srcdir(component):
        return str(source_directories[component])

    with patch("reana.reana_dev.client.get_srcdir", side_effect=get_srcdir), patch(
        "reana.reana_dev.client.get_scripts_dir", return_value=scripts_dir
    ), patch("reana.reana_dev.client.shutil.which", return_value="/usr/bin/go"), patch(
        "reana.reana_dev.client.run_command"
    ) as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-install"])

    python_paths = [
        str(source_directories[component])
        for component in REPO_LIST_CLIENT
        if component != "reana-client-go"
    ]
    go_executable = scripts_dir / "reana-client-go"
    assert result.exit_code == 0
    assert mock_run_command.call_args_list == [
        call(
            [sys.executable, "-m", "pip", "install", "--upgrade", *python_paths],
            "reana",
        ),
        call([sys.executable, "-m", "pip", "check"], "reana"),
        call(
            ["make", "install", f"BINDIR={scripts_dir}"],
            "reana-client-go",
        ),
        call([str(go_executable), "version"], "reana-client-go"),
    ]


@pytest.mark.parametrize("missing_tools", (("go",), ("make",), ("go", "make")))
def test_client_install_skips_go_without_build_tools(tmp_path, missing_tools):
    """Test that missing Go tools do not prevent Python installation."""
    source_directories = _create_client_source_directories(tmp_path)
    scripts_dir = tmp_path / "bin"
    scripts_dir.mkdir()

    def find_executable(executable):
        return None if executable in missing_tools else f"/usr/bin/{executable}"

    with patch(
        "reana.reana_dev.client.get_srcdir",
        side_effect=lambda component: str(source_directories[component]),
    ), patch("reana.reana_dev.client.get_scripts_dir", return_value=scripts_dir), patch(
        "reana.reana_dev.client.shutil.which", side_effect=find_executable
    ), patch(
        "reana.reana_dev.client.run_command"
    ) as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-install"])

    python_paths = [
        str(directory)
        for component, directory in source_directories.items()
        if component != "reana-client-go"
    ]
    assert result.exit_code == 0
    assert "[WARNING] Skipping Go client installation" in result.output
    assert f"build tools were not found: {', '.join(missing_tools)}" in result.output
    assert mock_run_command.call_args_list == [
        call(
            [sys.executable, "-m", "pip", "install", "--upgrade", *python_paths],
            "reana",
        ),
        call([sys.executable, "-m", "pip", "check"], "reana"),
    ]


@pytest.mark.parametrize("failure_stage", ("build", "smoke_test"))
def test_client_install_propagates_go_failures(tmp_path, failure_stage):
    """Test that Go build and smoke-test failures still fail installation."""
    source_directories = _create_client_source_directories(tmp_path)

    def run_command(command, component):
        if component == "reana-client-go" and (
            failure_stage == "build" or command[-1] == "version"
        ):
            raise SystemExit(7)

    with patch(
        "reana.reana_dev.client.get_srcdir",
        side_effect=lambda component: str(source_directories[component]),
    ), patch(
        "reana.reana_dev.client.get_scripts_dir", return_value=tmp_path / "bin"
    ), patch(
        "reana.reana_dev.client.shutil.which", return_value="/fake/tool"
    ), patch(
        "reana.reana_dev.client.run_command", side_effect=run_command
    ) as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-install"])

    assert result.exit_code == 7
    assert "Skipping Go client installation" not in result.output
    assert mock_run_command.call_count == (3 if failure_stage == "build" else 4)


def test_client_uninstall_removes_both_clients(tmp_path):
    """Test that client-uninstall removes Python packages and the Go binary."""
    from reana.config import REPO_LIST_CLIENT

    source_directories = _create_client_source_directories(tmp_path)
    scripts_dir = tmp_path / "bin"
    scripts_dir.mkdir()

    with patch(
        "reana.reana_dev.client.get_srcdir",
        side_effect=lambda component: str(source_directories[component]),
    ), patch("reana.reana_dev.client.get_scripts_dir", return_value=scripts_dir), patch(
        "reana.reana_dev.client.shutil.which", return_value="/usr/bin/make"
    ), patch(
        "reana.reana_dev.client.run_command"
    ) as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-uninstall"])

    python_components = [
        component for component in REPO_LIST_CLIENT if component != "reana-client-go"
    ]
    assert result.exit_code == 0
    assert mock_run_command.call_args_list == [
        call(
            [
                sys.executable,
                "-m",
                "pip",
                "uninstall",
                "-y",
                *python_components,
            ],
            "reana",
        ),
        call([sys.executable, "-m", "pip", "check"], "reana"),
        call(
            ["make", "uninstall", f"BINDIR={scripts_dir}"],
            "reana-client-go",
        ),
    ]


def test_client_uninstall_validates_environment_before_changes():
    """Test that client-uninstall validates its environment before changes."""
    with patch.object(sys, "prefix", "/usr"), patch.object(
        sys, "base_prefix", "/usr"
    ), patch("reana.reana_dev.client.run_command") as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-uninstall"])

    assert result.exit_code == 1
    assert "not running inside a virtual environment" in result.output
    mock_run_command.assert_not_called()


def test_client_uninstall_skips_go_without_make(tmp_path):
    """Test that Python removal proceeds with a warning about the retained Go binary."""
    source_directories = _create_client_source_directories(tmp_path)
    scripts_dir = tmp_path / "bin"
    scripts_dir.mkdir()
    go_executable = scripts_dir / "reana-client-go"
    go_executable.write_text("installed Go client")

    with patch(
        "reana.reana_dev.client.get_srcdir",
        side_effect=lambda component: str(source_directories[component]),
    ), patch("reana.reana_dev.client.get_scripts_dir", return_value=scripts_dir), patch(
        "reana.reana_dev.client.shutil.which", return_value=None
    ), patch(
        "reana.reana_dev.client.run_command"
    ) as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-uninstall"])

    python_components = [
        component for component in source_directories if component != "reana-client-go"
    ]
    assert result.exit_code == 0
    assert "[WARNING] Skipping Go client removal" in result.output
    assert "Any installed Go client binary remains" in result.output
    assert go_executable.read_text() == "installed Go client"
    assert mock_run_command.call_args_list == [
        call(
            [sys.executable, "-m", "pip", "uninstall", "-y", *python_components],
            "reana",
        ),
        call([sys.executable, "-m", "pip", "check"], "reana"),
    ]


def test_client_uninstall_requires_checked_out_components(tmp_path):
    """Test that client-uninstall does not silently skip missing sources."""
    source_directories = _create_client_source_directories(tmp_path)
    missing_component = "reana-client"
    (source_directories[missing_component] / "setup.py").unlink()
    source_directories[missing_component].rmdir()

    with patch(
        "reana.reana_dev.client.get_srcdir",
        side_effect=lambda component: str(source_directories[component]),
    ), patch(
        "reana.reana_dev.client.get_scripts_dir", return_value=tmp_path / "bin"
    ), patch(
        "reana.reana_dev.client.run_command"
    ) as mock_run_command:
        result = CliRunner().invoke(reana_dev, ["client-uninstall"])

    assert result.exit_code == 1
    assert f"Expected client component '{missing_component}'" in result.output
    mock_run_command.assert_not_called()


def test_get_scripts_dir_uses_running_environment():
    """Test scripts-directory lookup without relying on VIRTUAL_ENV."""
    from reana.reana_dev.client import get_scripts_dir

    with patch.object(sys, "prefix", "/virtualenv"), patch.object(
        sys, "base_prefix", "/usr"
    ), patch(
        "reana.reana_dev.client.sysconfig.get_path", return_value="/virtualenv/bin"
    ):
        assert get_scripts_dir() == Path("/virtualenv/bin")


@pytest.mark.parametrize("command", ("run-example", "run-ci"))
def test_run_commands_reject_unknown_client(command):
    """Test strict validation of the client option."""
    result = CliRunner().invoke(
        reana_dev,
        [command, "--client", "gopher"],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--client'" in result.output


@pytest.mark.parametrize(
    ("client_options", "client_flavour"),
    (([], "python"), (["--client", "python"], "python"), (["--client", "go"], "go")),
)
@patch("reana.reana_dev.client.shutil.which")
@patch("reana.reana_dev.run.run_command")
@patch("reana.reana_dev.run.select_components", return_value=[])
@patch("reana.reana_dev.run.is_cluster_created", return_value=True)
def test_run_ci_propagates_client_flavour(
    mock_is_cluster_created,
    mock_select_components,
    mock_run_command,
    mock_which,
    client_options,
    client_flavour,
):
    """Test client propagation and Python CI without Go build tools."""
    mock_which.return_value = "/fake/tool" if client_flavour == "go" else None
    result = CliRunner().invoke(
        reana_dev,
        [
            "run-ci",
            "--mode",
            "releasehelm",
            "--admin-email",
            "john.doe@example.org",
            "--admin-password",
            "secret",
            *client_options,
        ],
    )

    commands = [invocation.args[0] for invocation in mock_run_command.call_args_list]
    assert result.exit_code == 0
    assert "reana-dev client-install" in commands
    assert all("eval " not in command for command in commands)
    assert any(
        "--server https://localhost:" in command and "--no-tls-verify" in command
        for command in commands
    )
    assert any(
        f"reana-dev run-example --client {client_flavour}" in command
        for command in commands
    )


@pytest.mark.parametrize("missing_tools", (("go",), ("make",), ("go", "make")))
@patch("reana.reana_dev.run.run_command")
@patch("reana.reana_dev.run.is_cluster_created")
def test_run_ci_requires_go_tools_before_cluster_operations(
    mock_is_cluster_created, mock_run_command, missing_tools
):
    """Test that an existing Go binary cannot bypass CI build prerequisites."""
    with patch(
        "reana.reana_dev.client.shutil.which",
        side_effect=lambda executable: (
            None if executable in missing_tools else f"/existing/{executable}"
        ),
    ):
        result = CliRunner().invoke(
            reana_dev,
            [
                "run-ci",
                "--admin-email",
                "john.doe@example.org",
                "--admin-password",
                "secret",
                "--client",
                "go",
            ],
        )

    assert result.exit_code == 1
    assert "Cannot run CI with the Go client" in result.output
    assert f"build tools were not found: {', '.join(missing_tools)}" in result.output
    mock_is_cluster_created.assert_not_called()
    mock_run_command.assert_not_called()


@patch("reana.reana_dev.run.shutil.which", return_value=None)
@patch("reana.reana_dev.run.run_command")
def test_run_example_missing_go_client_explains_installation(
    mock_run_command, mock_which
):
    """Test that the missing Go executable error explains its build prerequisites."""
    result = CliRunner().invoke(
        reana_dev,
        ["run-example", "--client", "go"],
        env={"REANA_SERVER_URL": "localhost"},
    )

    assert result.exit_code == 1
    assert "Could not find 'reana-client-go' executable" in result.output
    assert "ensure Go and make are available" in result.output
    assert "reana-dev client-install" in result.output
    mock_run_command.assert_not_called()


@patch("reana.reana_dev.run.run_command")
def test_run_ci_submit_only_and_check_only_are_left_to_run_example(mock_run_command):
    """Tests for run-ci command when both submit-only and check-only flags are given."""
    result = CliRunner().invoke(
        reana_dev,
        [
            "run-ci",
            "-c",
            "r-d-r-roofit",
            "-w",
            "serial",
            "--submit-only",
            "--check-only",
        ],
    )
    commands = [invocation.args[0] for invocation in mock_run_command.call_args_list]
    assert result.exit_code == 0
    assert commands == [
        "reana-dev run-example --client python"
        " --server https://localhost:30443 --no-tls-verify"
        " -c reana-demo-root6-roofit -w serial --submit-only --check-only"
    ]


def test_run_ci_without_admin_credentials():
    """Tests for run-ci command when admin credentials are missing."""
    result = CliRunner().invoke(reana_dev, ["run-ci", "-c", "r-d-r-roofit"])
    assert "--admin-email and --admin-password are required" in result.output
    assert result.exit_code == 1


@pytest.mark.parametrize("client_flavour", ("python", "go"))
@patch("reana.reana_dev.client.shutil.which", return_value=None)
@patch("reana.reana_dev.run.run_command")
def test_run_ci_check_only(mock_run_command, mock_which, client_flavour):
    """Tests for run-ci command with check-only flag, which should not build anything."""
    result = CliRunner().invoke(
        reana_dev,
        [
            "run-ci",
            "-c",
            "r-d-r-roofit",
            "-w",
            "serial",
            "--client",
            client_flavour,
            "--check-only",
        ],
    )
    commands = [invocation.args[0] for invocation in mock_run_command.call_args_list]
    assert result.exit_code == 0
    assert commands == [
        f"reana-dev run-example --client {client_flavour}"
        " --server https://localhost:30443 --no-tls-verify"
        " -c reana-demo-root6-roofit -w serial --check-only"
    ]


@patch("reana.reana_dev.run.is_cluster_created", return_value=False)
@patch("reana.reana_dev.run.run_command")
def test_run_ci_submit_only(mock_run_command, mock_is_cluster_created):
    """Tests for run-ci command with submit-only flag, which should build the cluster."""
    result = CliRunner().invoke(
        reana_dev,
        [
            "run-ci",
            "-c",
            "r-d-r-roofit",
            "-w",
            "serial",
            "-m",
            "/var/reana:/var/reana",
            "-j",
            "/mydata:/mydata",
            "-b",
            "COMPUTE_BACKENDS=kubernetes",
            "--exclude-components",
            "r-ui",
            "--no-cache",
            "--disable-default-cni",
            "--admin-email",
            "john.doe@example.org",
            "--admin-password",
            "mysecretpassword",
            "--submit-only",
        ],
    )
    commands = [invocation.args[0] for invocation in mock_run_command.call_args_list]
    assert result.exit_code == 0
    assert commands == [
        "reana-dev cluster-create --kubernetes kind --mode latest --extra-ports 30443"
        " -m /var/reana:/var/reana --disable-default-cni",
        "reana-dev docker-pull -c reana-demo-root6-roofit",
        "reana-dev kind-load-docker-image -c reana-demo-root6-roofit",
        "reana-dev cluster-undeploy --kubernetes kind",
        "reana-dev client-install",
        "reana-dev cluster-build --kubernetes kind --mode latest"
        " --exclude-components r-ui -b COMPUTE_BACKENDS=kubernetes"
        " --no-cache --parallel 1",
        "reana-dev cluster-deploy --mode latest --namespace default"
        " --admin-email john.doe@example.org --admin-password mysecretpassword"
        " --exclude-components r-ui -j /mydata:/mydata",
        "reana-dev run-example --client python"
        " --server https://localhost:30443 --no-tls-verify"
        " -c reana-demo-root6-roofit -w serial --submit-only",
    ]


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


def _make_stub_client(tmp_path, script):
    """Create a stub client executable behaving as the given shell script."""
    stub = tmp_path / "stub-client"
    stub.write_text(f"#!/bin/sh\n{script}\n")
    stub.chmod(0o755)
    return str(stub)


class _AlwaysTTY:
    """Wrap a stream so that it reports being an interactive terminal."""

    def __init__(self, stream):
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def isatty(self):
        return True


def _pretend_interactive(monkeypatch):
    monkeypatch.setattr(sys, "stdin", _AlwaysTTY(sys.stdin))
    monkeypatch.setattr(sys, "stdout", _AlwaysTTY(sys.stdout))


def test_ensure_client_login_guides_initial_setup(monkeypatch, capsys, tmp_path):
    """With no resolved server, show initial local login guidance."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    with pytest.raises(SystemExit):
        ensure_client_login(
            _make_stub_client(tmp_path, 'echo "No REANA server is configured"\nexit 1')
        )
    output = capsys.readouterr().out
    assert "login --server https://localhost:30443\n" in output
    assert "add `--no-tls-verify` to the login command" in output


def test_ensure_client_login_passes_with_working_credentials(tmp_path, monkeypatch):
    """A successful probe proceeds and keeps a working token untouched."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.setenv("REANA_ACCESS_TOKEN", "working-token")
    ensure_client_login(
        _make_stub_client(
            tmp_path, 'echo "REANA server: https://localhost:30443"\nexit 0'
        )
    )
    assert os.environ["REANA_ACCESS_TOKEN"] == "working-token"


def test_ensure_client_login_noninteractive_shows_resume_commands(
    tmp_path, monkeypatch, capsys
):
    """Without a terminal, print the diagnostic and exact resume commands."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.setenv("REANA_ACCESS_TOKEN", "stale-token")
    stub = _make_stub_client(tmp_path, 'echo "==> ERROR: please run login" >&2\nexit 1')
    with pytest.raises(SystemExit):
        ensure_client_login(stub, "https://localhost:30443")
    output = capsys.readouterr().out
    assert "==> ERROR: please run login" in output
    assert f"{stub} login --server https://localhost:30443" in output
    assert (
        "env -u REANA_ACCESS_TOKEN" in output
        and "--server https://localhost:30443" in output
    )
    assert os.environ["REANA_ACCESS_TOKEN"] == "stale-token"


def test_ensure_client_login_starts_login_interactively(tmp_path, monkeypatch, capsys):
    """Without a token, log in directly and keep the probe diagnostic quiet."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.delenv("REANA_ACCESS_TOKEN", raising=False)
    state = tmp_path / "logged-in"
    stub = _make_stub_client(
        tmp_path,
        f'if [ "$1" = "login" ]; then touch "{state}"; exit 0; fi\n'
        f'if test -f "{state}"; then echo "REANA server: https://localhost:30443"; exit 0; fi\n'
        'echo "==> ERROR: please run login" >&2; exit 1',
    )
    _pretend_interactive(monkeypatch)
    ensure_client_login(stub, "https://localhost:30443")
    captured = capsys.readouterr()
    assert "Logged in to https://localhost:30443." in captured.out
    assert "==> ERROR: please run login" not in captured.out
    assert "==> ERROR: please run login" not in captured.err


def test_ensure_client_login_confirms_before_dropping_token(
    tmp_path, monkeypatch, capsys
):
    """A failing token is dropped only after showing why and confirming."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.setenv("REANA_ACCESS_TOKEN", "stale-token")
    state = tmp_path / "logged-in"
    stub = _make_stub_client(
        tmp_path,
        f'if [ "$1" = "login" ]; then touch "{state}"; exit 0; fi\n'
        f'if test -f "{state}"; then echo "REANA server: https://localhost:30443"; exit 0; fi\n'
        'echo "==> ERROR: HTTP 401" >&2; exit 1',
    )
    _pretend_interactive(monkeypatch)
    confirmations = []
    monkeypatch.setattr(
        click, "confirm", lambda *args, **kwargs: confirmations.append(args) or True
    )
    ensure_client_login(stub, "https://localhost:30443")
    assert len(confirmations) == 1
    assert "REANA_ACCESS_TOKEN" not in os.environ
    assert "==> ERROR: HTTP 401" in capsys.readouterr().out


def test_ensure_client_login_keeps_token_when_declined(tmp_path, monkeypatch, capsys):
    """Declining the confirmation keeps the token and exits with guidance."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.setenv("REANA_ACCESS_TOKEN", "chosen-token")
    stub = _make_stub_client(tmp_path, "exit 1")
    _pretend_interactive(monkeypatch)
    monkeypatch.setattr(click, "confirm", lambda *args, **kwargs: False)
    with pytest.raises(SystemExit):
        ensure_client_login(stub, "https://localhost:30443")
    assert os.environ["REANA_ACCESS_TOKEN"] == "chosen-token"
    assert "env -u REANA_ACCESS_TOKEN" in capsys.readouterr().out


def test_ensure_client_login_reports_login_failure(tmp_path, monkeypatch, capsys):
    """A failing login exits with resume commands carrying the server URL."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.delenv("REANA_ACCESS_TOKEN", raising=False)
    stub = _make_stub_client(tmp_path, "exit 1")
    _pretend_interactive(monkeypatch)
    with pytest.raises(SystemExit):
        ensure_client_login(stub, "https://localhost:30443")
    output = capsys.readouterr().out
    assert "Login did not succeed." in output
    assert "--server https://localhost:30443" in output
    assert "env -u" not in output


def test_ensure_client_login_reports_failing_confirmation(
    tmp_path, monkeypatch, capsys
):
    """A login that still cannot ping shows that probe's diagnostic."""
    monkeypatch.delenv("REANA_SERVER_URL", raising=False)
    monkeypatch.delenv("REANA_ACCESS_TOKEN", raising=False)
    stub = _make_stub_client(
        tmp_path,
        'if [ "$1" = "login" ]; then exit 0; fi\n'
        'echo "==> ERROR: HTTP 403 missing role" >&2\nexit 1',
    )
    _pretend_interactive(monkeypatch)
    with pytest.raises(SystemExit):
        ensure_client_login(stub, "https://localhost:30443")
    output = capsys.readouterr().out
    assert "did not establish a working connection" in output
    assert "==> ERROR: HTTP 403 missing role" in output
