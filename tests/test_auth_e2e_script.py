# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for the manual authentication E2E script's portable path handling."""

import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "test-auth-workflow-e2e.py"


@pytest.fixture(scope="module")
def e2e_script():
    """Load the standalone, hyphenated script as a test module."""
    spec = importlib.util.spec_from_file_location("auth_workflow_e2e", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_explicit_relative_paths_are_resolved_before_client_changes_cwd(
    e2e_script, monkeypatch, tmp_path
):
    """Relative executable and demo paths remain anchored to the caller's cwd."""
    client = tmp_path / "bin" / "reana-client"
    client.parent.mkdir()
    client.touch()
    demo = tmp_path / "demo"
    demo.mkdir()
    (demo / "reana.yaml").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--reana-client",
            "bin/reana-client",
            "--demo-dir",
            "demo",
        ],
    )

    args = e2e_script.parse_args()

    assert args.reana_client == client.resolve()
    assert args.demo_dir == demo.resolve()


def test_client_is_discovered_from_path(e2e_script, monkeypatch, tmp_path):
    """An activated client environment needs no checkout-specific path."""
    client = tmp_path / "reana-client"
    client.touch()
    demo = tmp_path / "demo"
    demo.mkdir()
    (demo / "reana.yaml").touch()
    monkeypatch.setattr(e2e_script.shutil, "which", lambda _name: str(client))
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--demo-dir", str(demo)],
    )

    args = e2e_script.parse_args()

    assert args.reana_client == client.resolve()


def test_missing_demo_is_rejected_before_the_test_runs(
    e2e_script, monkeypatch, tmp_path, capsys
):
    """Missing prerequisites fail during argument parsing, before cluster writes."""
    client = tmp_path / "reana-client"
    client.touch()
    missing_demo = tmp_path / "missing-demo"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--reana-client",
            str(client),
            "--demo-dir",
            str(missing_demo),
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        e2e_script.parse_args()

    assert "--demo-dir does not exist" in capsys.readouterr().err


def test_directory_without_workflow_specification_is_rejected(
    e2e_script, monkeypatch, tmp_path, capsys
):
    """An arbitrary directory must not fail later during workflow creation."""
    client = tmp_path / "reana-client"
    client.touch()
    not_a_demo = tmp_path / "not-a-demo"
    not_a_demo.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--reana-client",
            str(client),
            "--demo-dir",
            str(not_a_demo),
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        e2e_script.parse_args()

    assert "missing reana.yaml" in capsys.readouterr().err
