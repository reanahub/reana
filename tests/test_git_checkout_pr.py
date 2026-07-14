# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Regression tests for the git-checkout-pr command."""

import json
from unittest.mock import patch

import pytest

from reana.reana_dev.git import _collect_prs_to_checkout, _get_prs_from_issue


def _reference(component, pull_request):
    """Return a closedByPullRequestsReferences entry."""
    return {
        "number": pull_request,
        "repository": {"name": component},
    }


@patch("reana.reana_dev.git.run_command")
def test_get_prs_from_issue_uses_current_open_references(mock_run):
    """Current open PR references are returned in deterministic order."""
    mock_run.return_value = json.dumps(
        {
            "closedByPullRequestsReferences": [
                _reference("reana-server", 780),
                _reference("reana-commons", 541),
                _reference("reana-db", 267),
                _reference("reana", 972),
                _reference("reana-ui", 516),
            ]
        }
    )

    prs = _get_prs_from_issue("reana-workflow-controller", "663")

    assert prs == [
        ("reana", "972"),
        ("reana-commons", "541"),
        ("reana-db", "267"),
        ("reana-server", "780"),
        ("reana-ui", "516"),
    ]
    mock_run.assert_called_once_with(
        [
            "gh",
            "issue",
            "view",
            "663",
            "--repo",
            "reanahub/reana-workflow-controller",
            "--json",
            "closedByPullRequestsReferences",
        ],
        display=False,
        return_output=True,
    )


@pytest.mark.parametrize("reverse", [False, True])
@patch("reana.reana_dev.git.run_command")
def test_issue_conflict_is_reported_deterministically(mock_run, reverse, capsys):
    """API result order does not change which component conflict is reported."""
    references = [
        _reference("reana-db", 267),
        _reference("reana-commons", 1000),
        _reference("reana-db", 265),
        _reference("reana-commons", 99),
    ]
    if reverse:
        references.reverse()
    mock_run.return_value = json.dumps({"closedByPullRequestsReferences": references})

    with pytest.raises(SystemExit):
        _collect_prs_to_checkout((), ("reana-workflow-controller", "663"))

    assert capsys.readouterr().out == (
        "Conflict for reana-commons: asked to check out both pr-99 and pr-1000. "
        "Remove the duplicate from -b/-i.\n"
    )
