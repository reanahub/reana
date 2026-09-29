# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for package configuration."""

import runpy
from pathlib import Path

import setuptools


def test_release_dependencies_are_opt_in(monkeypatch):
    """Keep publishing tools out of the aggregate development extra."""
    project_root = Path(__file__).resolve().parents[1]
    setup_arguments = {}
    monkeypatch.setattr(
        setuptools,
        "setup",
        lambda **kwargs: setup_arguments.update(kwargs),
    )
    monkeypatch.chdir(project_root)

    runpy.run_path(str(project_root / "setup.py"), run_name="__main__")

    extras = setup_arguments["extras_require"]
    assert extras["release"] == ["build", "twine"]
    assert "build" not in extras["all"]
    assert "twine" not in extras["all"]
