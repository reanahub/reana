# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Regression tests for upgrading shared modules across repositories."""

import subprocess

import pytest

from reana.reana_dev import utils


@pytest.mark.parametrize("component", ["reana-server", "reana-job-controller"])
@pytest.mark.parametrize("dependency_file", ["setup.py", "pyproject.toml"])
def test_upgrade_shared_module_after_tag_check(
    tmp_path, monkeypatch, component, dependency_file
):
    """Select dependency lines in the target after checking the module's tag."""
    module_dir = tmp_path / "reana-db"
    module_dir.mkdir()
    module_setup = module_dir / dependency_file
    module_contents = 'dependencies = ["reana-commons>=0.95.0a23,<0.96.0"]\n'
    module_setup.write_text(module_contents)
    subprocess.run(["git", "init", "-q"], cwd=module_dir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=REANA Tests",
            "-c",
            "user.email=tests@example.org",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-qm",
            "Release shared module",
        ],
        cwd=module_dir,
        check=True,
    )
    subprocess.run(["git", "tag", "0.95.0a13"], cwd=module_dir, check=True)

    component_dir = tmp_path / component
    component_dir.mkdir()
    dependencies = component_dir / dependency_file
    original_dependencies = (
        "dependencies = [\n"
        '    "reana-db[tests]>=0.95.0a12,<0.96.0",\n'
        '    "requests>=2.25.0",\n'
        '    "reana-db>=0.95.0a12,<0.96.0",\n'
        "]\n"
    )
    dependencies.write_text(original_dependencies)
    requirements = component_dir / "requirements.txt"
    requirements.write_text("reana-db==0.95.0a12    # via reana-server\n")
    monkeypatch.setattr(utils, "get_srcdir", lambda name: str(tmp_path / name))
    monkeypatch.chdir(component_dir)

    utils.update_module_in_cluster_components(
        "reana-db",
        "0.95.0a13",
        components_to_update=[component],
        use_latest_known_tag=False,
    )

    assert dependencies.read_text() == original_dependencies.replace(
        "0.95.0a12", "0.95.0a13"
    )
    assert requirements.read_text() == "reana-db==0.95.0a13\t# via reana-server\n"
    assert module_setup.read_text() == module_contents


@pytest.mark.parametrize("start_component", ["reana-server", "reana-job-controller"])
@pytest.mark.parametrize("dependency_file", ["setup.py", "pyproject.toml"])
def test_upgrade_shared_module_across_components(
    tmp_path, monkeypatch, start_component, dependency_file
):
    """Update each component's dependency without changing unrelated pins."""
    shared_dependency = '    "reana-db>=0.95.0a12,<0.96.0",\n'
    unrelated_dependency = '    "requests>=2.25.0,<3.0.0",\n'
    original_dependencies = {
        "reana-server": (
            f"dependencies = [\n{shared_dependency}{unrelated_dependency}]\n"
        ),
        "reana-job-controller": (
            f"dependencies = [\n{unrelated_dependency}{shared_dependency}]\n"
        ),
    }
    for component, contents in original_dependencies.items():
        component_dir = tmp_path / component
        component_dir.mkdir()
        (component_dir / dependency_file).write_text(contents)
    monkeypatch.setattr(utils, "get_srcdir", lambda name: str(tmp_path / name))
    monkeypatch.chdir(tmp_path / start_component)

    utils.update_module_in_cluster_components(
        "reana-db",
        "0.95.0a13",
        components_to_update=list(original_dependencies),
        use_latest_known_tag=True,
    )

    # Different line positions expose stale lookups in either processing order.
    for component, contents in original_dependencies.items():
        assert (tmp_path / component / dependency_file).read_text() == contents.replace(
            "0.95.0a12", "0.95.0a13"
        )
