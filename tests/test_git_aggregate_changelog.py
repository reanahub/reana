# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for the git-aggregate-changelog command."""

import json
import subprocess
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from reana.reana_dev.git import (
    get_aggregate_changelog,
    get_changelog_git_ref,
    get_previous_versions_from_release_tag,
)

PREFETCH_SCRIPT = (
    "docker pull \\\n"
    "    docker.io/reanahub/reana-server:0.95.0-alpha.7 \\\n"
    "    docker.io/reanahub/reana-workflow-validator:0.95.0-alpha.1\n"
)


@patch("reana.reana_dev.git.run_command", return_value="0123abc")
def test_get_changelog_git_ref_keeps_resolvable_reference(mock_run):
    """Existing tags and commits are used as they are."""
    assert get_changelog_git_ref("reana-client-go", "ee4735b") == "ee4735b"


@pytest.mark.parametrize(
    "include_v_in_tag, expected",
    [(True, "v0.95.0-alpha.1"), (False, "0.95.0-alpha.1")],
)
@patch("reana.reana_dev.git.run_command")
def test_get_changelog_git_ref_uses_component_tag_name(
    mock_run, tmp_path, include_v_in_tag, expected
):
    """Versions that are not git references are translated to tag names."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "git rev-parse")
    (tmp_path / ".release-please-config.json").write_text(
        json.dumps({"include-v-in-tag": include_v_in_tag})
    )
    with patch("reana.reana_dev.utils.get_srcdir", return_value=str(tmp_path)):
        assert get_changelog_git_ref("reana-client-go", "0.95.0-alpha.1") == expected


@pytest.mark.parametrize("version", [None, ""])
@patch("reana.reana_dev.git.run_command")
def test_get_changelog_git_ref_without_version(mock_run, version):
    """New components without a previous version have no reference."""
    assert get_changelog_git_ref("reana-client-go", version) is None
    mock_run.assert_not_called()


@patch(
    "reana.reana_dev.git.get_current_component_version_from_source_files",
    side_effect=lambda component: {
        "reana-client": "0.95.0a6",
        "reana-client-go": "0.95.0-alpha.1",
    }[component],
)
@patch("reana.reana_dev.git.run_command", return_value=PREFETCH_SCRIPT)
def test_get_versions_from_release_tag_reads_clients_from_sources(
    mock_run, mock_source_version
):
    """Both clients take their versions from the checked-out sources."""
    versions = get_previous_versions_from_release_tag(
        "0.95.0-alpha.6",
        ["reana-client", "reana-client-go", "reana-workflow-validator"],
    )
    assert versions == {
        "reana-client": "0.95.0a6",
        "reana-client-go": "0.95.0-alpha.1",
        "reana-workflow-validator": "0.95.0-alpha.1",
    }


def _run_aggregate_changelog(extra_args):
    """Run git-aggregate-changelog and return the cog calls per component."""
    start_versions = {}

    def fake_versions(release_tag, components, override=None):
        if release_tag == "0.95.0-alpha.5":
            start_versions.update(override)
            return {
                component: (override or {}).get(component, "1.0.0")
                for component in components
            }
        return {
            component: ("0.95.0-alpha.1" if component == "reana-client-go" else "2.0.0")
            for component in components
        }

    cog_calls = {}

    def fake_cog(component, prev_version, current_version, commit_types=None):
        cog_calls[component] = (prev_version, current_version)
        return []

    with patch(
        "reana.reana_dev.git.get_previous_versions_from_release_tag",
        side_effect=fake_versions,
    ), patch(
        "reana.reana_dev.git.get_changelog_git_ref",
        side_effect=lambda component, version: (
            f"v{version}"
            if version and component == "reana-client-go" and "." in version
            else version
        ),
    ), patch(
        "reana.reana_dev.git.run_command", return_value=""
    ), patch(
        "reana.reana_dev.git.generate_changelog_with_cog", side_effect=fake_cog
    ):
        result = CliRunner().invoke(
            get_aggregate_changelog,
            [
                "--previous-reana-client",
                "0.95.0a5",
                "--commit-range",
                "0.95.0-alpha.5..0.95.0-alpha.6",
            ]
            + extra_args,
        )
    assert result.exit_code == 0, result.output
    return start_versions, cog_calls


def test_aggregate_changelog_includes_client_go_as_new_component():
    """Without a previous version, reana-client-go is aggregated as new."""
    start_versions, cog_calls = _run_aggregate_changelog([])
    assert start_versions["reana-client-go"] is None
    assert cog_calls["reana-client-go"] == (None, "v0.95.0-alpha.1")
    assert cog_calls["reana-client"] == ("0.95.0a5", "2.0.0")


def test_aggregate_changelog_uses_previous_client_go_version():
    """A previous reana-client-go version or commit bounds its changelog."""
    _, cog_calls = _run_aggregate_changelog(["--previous-reana-client-go", "ee4735b"])
    assert cog_calls["reana-client-go"] == ("ee4735b", "v0.95.0-alpha.1")


def test_aggregate_changelog_can_exclude_client_go():
    """The short name of reana-client-go can be excluded."""
    _, cog_calls = _run_aggregate_changelog(["--exclude-components", "r-c-go"])
    assert "reana-client-go" not in cog_calls
    assert "reana-client" in cog_calls
