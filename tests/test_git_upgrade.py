# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Regression tests for the git-upgrade command."""

from unittest.mock import patch

from click.testing import CliRunner

from reana.reana_dev.cli import reana_dev

COMPONENT = "reana-server"
BASE = "maint-1.2"


def _invoke(base=BASE, create_branch=False):
    args = ["git-upgrade", "--base", base, "-c", COMPONENT]
    if create_branch:
        args.append("--create-branch")
    return CliRunner().invoke(reana_dev, args)


def _ls_remote_returns(output):
    """Return a run_command side_effect that answers ls-remote calls with *output*."""

    def side_effect(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "ls-remote" in cmd:
            return output
        return None

    return side_effect


@patch("reana.reana_dev.git.display_message")
@patch("reana.reana_dev.git.branch_exists", return_value=False)
@patch("reana.reana_dev.git.select_components", return_value=[COMPONENT])
@patch("reana.reana_dev.git.run_command")
def test_create_branch_exact_upstream(mock_run, mock_select, mock_exists, mock_display):
    """Branch is created when the upstream ref matches exactly."""
    mock_run.side_effect = _ls_remote_returns(f"abc123\trefs/heads/{BASE}")

    result = _invoke(create_branch=True)

    assert result.exit_code == 0
    mock_run.assert_any_call(
        ["git", "ls-remote", "--heads", "upstream", f"refs/heads/{BASE}"],
        COMPONENT,
        display=False,
        return_output=True,
    )
    mock_run.assert_any_call(
        ["git", "checkout", "-b", BASE, f"upstream/{BASE}"], COMPONENT
    )
    mock_run.assert_any_call(["git", "push", "-u", "origin", BASE], COMPONENT)
    mock_run.assert_any_call(["git", "checkout", "-"], COMPONENT)


@patch("reana.reana_dev.git.display_message")
@patch("reana.reana_dev.git.branch_exists", return_value=False)
@patch("reana.reana_dev.git.select_components", return_value=[COMPONENT])
@patch("reana.reana_dev.git.run_command")
def test_missing_upstream_branch_skipped(
    mock_run, mock_select, mock_exists, mock_display
):
    """Component is skipped with a message when the base branch is absent from upstream."""
    mock_run.side_effect = _ls_remote_returns("")

    result = _invoke(create_branch=True)

    assert result.exit_code == 0
    mock_display.assert_called_once_with(
        f"Branch {BASE} does not exist in upstream, skipping.",
        component=COMPONENT,
    )
    called_cmds = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "fetch", "upstream"] not in called_cmds


@patch("reana.reana_dev.git.display_message")
@patch("reana.reana_dev.git.branch_exists", return_value=False)
@patch("reana.reana_dev.git.select_components", return_value=[COMPONENT])
@patch("reana.reana_dev.git.run_command")
def test_failed_push_restores_original_branch(
    mock_run, mock_select, mock_exists, mock_display
):
    """git checkout - runs in the finally block even when origin push is rejected."""

    def side_effect(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "ls-remote" in cmd:
            return f"abc123\trefs/heads/{BASE}"
        if isinstance(cmd, list) and cmd[:3] == ["git", "push", "-u"]:
            raise SystemExit(1)
        return None

    mock_run.side_effect = side_effect

    result = _invoke(create_branch=True)

    assert result.exit_code != 0
    called_cmds = [c.args[0] for c in mock_run.call_args_list]
    assert ["git", "checkout", "-"] in called_cmds
    push_idx = next(
        i
        for i, c in enumerate(called_cmds)
        if c == ["git", "push", "-u", "origin", BASE]
    )
    checkout_idx = called_cmds.index(["git", "checkout", "-"])
    assert checkout_idx > push_idx


@patch("reana.reana_dev.git.display_message")
@patch("reana.reana_dev.git.branch_exists", return_value=False)
@patch("reana.reana_dev.git.select_components", return_value=[COMPONENT])
@patch("reana.reana_dev.git.run_command")
def test_shell_metacharacters_in_branch_name(
    mock_run, mock_select, mock_exists, mock_display
):
    """Branch names with shell metacharacters are passed as list elements, not interpolated."""
    unsafe_base = "maint;echo"
    mock_run.side_effect = _ls_remote_returns(f"abc123\trefs/heads/{unsafe_base}")

    result = _invoke(base=unsafe_base, create_branch=True)

    assert result.exit_code == 0
    called_cmds = [c.args[0] for c in mock_run.call_args_list]
    # Defensive guard: no shell-string command should ever interpolate the
    # branch name. Today every command in this code path is list-form, so
    # this loop is a no-op. It exists to catch a future regression where
    # someone reintroduces an f-string into a shell-form run_command call.
    for cmd in called_cmds:
        if isinstance(cmd, str):
            assert (
                unsafe_base not in cmd
            ), f"Branch name interpolated into shell string: {cmd!r}"
    assert [
        "git",
        "checkout",
        "-b",
        unsafe_base,
        f"upstream/{unsafe_base}",
    ] in called_cmds
    assert ["git", "push", "-u", "origin", unsafe_base] in called_cmds


@patch("reana.reana_dev.git.display_message")
@patch("reana.reana_dev.git.branch_exists", return_value=True)
@patch("reana.reana_dev.git.select_components", return_value=[COMPONENT])
@patch("reana.reana_dev.git.run_command")
def test_existing_branch_runs_merge_push_flow(
    mock_run, mock_select, mock_exists, mock_display
):
    """When the local branch exists, the upgrade runs fetch / checkout / ff-merge / push / restore in order."""
    result = _invoke()

    assert result.exit_code == 0
    assert [c.args[0] for c in mock_run.call_args_list] == [
        ["git", "fetch", "upstream"],
        ["git", "checkout", BASE],
        ["git", "merge", "--ff-only", f"upstream/{BASE}"],
        ["git", "push", "origin", BASE],
        ["git", "checkout", "-"],
    ]
