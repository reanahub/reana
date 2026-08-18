# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for release commands."""

import shlex
import sys

import pytest
from click.testing import CliRunner

from reana.reana_dev import release
from reana.reana_dev.cli import reana_dev


def test_pypi_release_uses_modules_from_active_environment():
    """Build and upload through modules from the active environment."""
    python = shlex.quote(sys.executable)
    commands = release._pypi_release_commands()

    assert commands[1].startswith(f"{python} -m build ")
    assert commands[2].startswith(f"{python} -m twine ")


def test_pypi_release_requires_release_tools(monkeypatch):
    """Fail before release work when the active environment lacks tools."""
    monkeypatch.setattr(
        release.importlib.util,
        "find_spec",
        lambda module: None if module == "twine" else object(),
    )

    with pytest.raises(release.click.ClickException, match="twine") as error:
        release._ensure_pypi_release_tools()

    assert "pip install --editable" in str(error.value)
    assert "<reana-source-directory>[release]" in str(error.value)


def test_pypi_release_checks_tools_before_cleaning(monkeypatch):
    """Do not clean release trees when the active environment lacks tooling."""
    cleaned = []

    def reject_missing_tools():
        raise release.click.ClickException("missing release tools")

    monkeypatch.setattr(release, "_ensure_pypi_release_tools", reject_missing_tools)
    monkeypatch.setattr(release, "select_components", lambda component: ["reana"])
    monkeypatch.setattr(
        release, "is_component_releasable", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        release.git_clean,
        "callback",
        lambda **kwargs: cleaned.append(kwargs),
    )
    monkeypatch.setattr(release, "_pypi_release_commands", lambda: [])
    monkeypatch.setattr(release, "fetch_latest_pypi_version", lambda component: "1")
    monkeypatch.setattr(
        release,
        "get_current_component_version_from_source_files",
        lambda component: "1",
    )

    result = CliRunner().invoke(reana_dev, ["release-pypi", "-c", "reana"])

    assert result.exit_code != 0
    assert "missing release tools" in result.output
    assert cleaned == []
