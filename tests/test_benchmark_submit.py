# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Benchmark submission uses the workflow specification bundle protocol."""

import importlib
import sys
from types import ModuleType

import pytest
import yaml

REANA_YAML = """
inputs:
  files:
    - workflow/Snakefile
    - data/names.txt
  directories:
    - workflow
    - data
workflow:
  type: snakemake
  file: workflow/Snakefile
"""


@pytest.fixture
def analysis(tmp_path, monkeypatch):
    """Create a file-backed workflow with runtime inputs."""
    (tmp_path / "workflow").mkdir()
    (tmp_path / "workflow" / "Snakefile").write_text("rule all:\n")
    (tmp_path / "data" / "nested").mkdir(parents=True)
    (tmp_path / "data" / "names.txt").write_text("Jane Doe\n")
    (tmp_path / "data" / "nested" / "more.txt").write_text("John Doe\n")
    (tmp_path / "reana-snakemake.yaml").write_text(REANA_YAML)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def submit_module(analysis, monkeypatch):
    """Import the submit module against a recording fake of the REANA client."""
    calls = []

    def create_workflow_from_bundle(reana_file, name, access_token):
        if name.endswith("-2"):
            raise RuntimeError("server does not support specification bundles")
        calls.append(("create", name, reana_file, access_token))

    def upload_to_server(workflow, paths, access_token):
        calls.append(("upload", workflow, paths, access_token))

    def gather_validation_members(reana_file):
        specification = yaml.safe_load(open(reana_file))
        workflow_file = specification["workflow"]["file"]
        members = {
            "reana.yaml": reana_file,
            workflow_file: str(analysis / workflow_file),
        }
        return members, specification, False

    fakes = {
        "reana_client": {},
        "reana_client.api": {},
        "reana_client.api.client": {
            "create_workflow_from_bundle": create_workflow_from_bundle,
            "upload_to_server": upload_to_server,
        },
        "reana_client.auth": {},
        "reana_client.auth.oidc": {"get_access_token": lambda: "saved-token"},
        "reana_commons": {},
        "reana_commons.specification_paths": {
            "gather_validation_members": gather_validation_members,
        },
    }
    for name, attributes in fakes.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        parent, _, child = name.rpartition(".")
        if parent:
            setattr(sys.modules[parent], child, module)
    for name in ("reana.reana_benchmark.utils", "reana.reana_benchmark.submit"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.delenv("REANA_ACCESS_TOKEN", raising=False)

    module = importlib.import_module("reana.reana_benchmark.submit")
    yield module, calls
    for name in ("reana.reana_benchmark.utils", "reana.reana_benchmark.submit"):
        sys.modules.pop(name, None)


def test_submit_creates_from_bundle_then_uploads_runtime_inputs(
    submit_module, analysis
):
    """Workflow sources travel in the bundle; only runtime inputs are uploaded."""
    module, calls = submit_module

    module.submit("bench", (1, 1), "reana-snakemake.yaml", 1)

    assert calls == [
        ("create", "bench-1", f"{analysis}/reana-snakemake.yaml", "saved-token"),
        ("upload", "bench-1", f"{analysis}/data/names.txt", "saved-token"),
        ("upload", "bench-1", f"{analysis}/data/nested/more.txt", "saved-token"),
    ]


def test_submit_does_not_upload_when_creation_fails(submit_module):
    """A refused creation surfaces the client error before any upload."""
    module, calls = submit_module

    with pytest.raises(RuntimeError, match="specification bundles"):
        module.submit("bench", (2, 2), "reana-snakemake.yaml", 1)

    assert calls == []


def test_access_token_environment_override(submit_module, monkeypatch):
    """REANA_ACCESS_TOKEN keeps overriding the saved login."""
    module, calls = submit_module
    monkeypatch.setenv("REANA_ACCESS_TOKEN", "override")

    module.submit("bench", (3, 3), "reana-snakemake.yaml", 1)

    assert {call[-1] for call in calls} == {"override"}
