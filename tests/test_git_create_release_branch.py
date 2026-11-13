# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for the ``reana-dev git-create-release-branch`` command."""

from typing import Optional

import pytest

from reana.config import (
    DOCKER_VERSION_FILE,
    GO_VERSION_FILE,
    HELM_VERSION_FILE,
    JAVASCRIPT_VERSION_FILE,
    OPENAPI_VERSION_FILE,
    PYTHON_VERSION_FILE,
)
from reana.reana_dev import git


def mock_component(monkeypatch, current_version: str, **version_files: str):
    """Mock a component and return the list of commands run on it.

    Version files not given get an empty path, as in the real helper.
    """
    all_version_files = {
        DOCKER_VERSION_FILE: "",
        HELM_VERSION_FILE: "",
        OPENAPI_VERSION_FILE: "",
        JAVASCRIPT_VERSION_FILE: "",
        PYTHON_VERSION_FILE: "",
        GO_VERSION_FILE: "",
    }
    all_version_files.update(version_files)
    monkeypatch.setattr(
        git,
        "get_component_version_files",
        lambda component, abs_path=False: all_version_files,
    )
    monkeypatch.setattr(
        git,
        "get_current_component_version_from_source_files",
        lambda component, version_file=None: current_version,
    )
    monkeypatch.setattr(git, "display_message", lambda *args, **kwargs: None)

    commands = []
    monkeypatch.setattr(
        git, "run_command", lambda cmd, component, **kwargs: commands.append(cmd)
    )
    return commands


@pytest.mark.parametrize(
    "next_version, expected_branch",
    [
        (None, "release-0.95.0-alpha.3"),
        ("0.95.0-alpha.3", "release-0.95.0-alpha.3"),
        ("0.95.0a3", "release-0.95.0-alpha.3"),
    ],
)
def test_go_component_uses_semver2(
    monkeypatch, next_version: Optional[str], expected_branch: str
):
    """Test that Go components are released with SemVer 2 versions."""
    commands = mock_component(
        monkeypatch, "0.95.0-alpha.2", **{GO_VERSION_FILE: "cmd/version.go"}
    )

    git.git_create_release_branch("reana-client-go", next_version)

    assert commands == [f"git checkout -b {expected_branch}"]


@pytest.mark.parametrize("next_version", [None, "0.95.0a3", "0.95.0-alpha.3"])
def test_python_component_uses_pep440(monkeypatch, next_version: Optional[str]):
    """Test that Python components keep PEP 440 versions with or without --version."""
    commands = mock_component(
        monkeypatch,
        "0.95.0a2",
        **{PYTHON_VERSION_FILE: "reana_commons/version.py"},
    )

    git.git_create_release_branch("reana-commons", next_version)

    assert commands == ["git checkout -b release-0.95.0a3"]


def test_component_without_version_files_fails(monkeypatch):
    """Test that a component without any version file cannot be released."""
    commands = mock_component(monkeypatch, "")

    with pytest.raises(SystemExit):
        git.git_create_release_branch("reana-demo-helloworld", "0.95.0")

    assert commands == []
