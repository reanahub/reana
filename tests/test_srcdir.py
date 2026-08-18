# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for managed REANA source directories."""

import json
import re
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from reana.reana_dev import srcdir
from reana.reana_dev.cli import reana_dev


@pytest.fixture(autouse=True)
def clear_terminal_session_environment(monkeypatch, tmp_path):
    """Keep backend auto-detection independent of the test runner terminal."""
    for variable in ("TMUX", "KITTY_WINDOW_ID", "KITTY_LISTEN_ON"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


def test_srcdir_output_uses_homebrew_style_visual_hierarchy():
    """Use blue headings, green success markers, and left-aligned details."""

    @click.command()
    def render_output():
        srcdir._echo_heading("Auditing srcdir test-bar")
        srcdir._echo_field("Location", "/tmp/test-bar")
        srcdir._echo_success("Teardown audit found no unretained work")
        srcdir._echo_warning("Teardown audit found unretained work")
        srcdir._echo_command("reana-dev srcdir-workon test-bar")

    result = CliRunner().invoke(render_output, color=True)

    assert result.exit_code == 0, result.output
    assert result.output == (
        "\x1b[34m==>\x1b[0m \x1b[1mAuditing srcdir test-bar\x1b[0m\n"
        "Location     /tmp/test-bar\n"
        "\x1b[32m✓\x1b[0m Teardown audit found no unretained work\n"
        "\x1b[33mWarning:\x1b[0m Teardown audit found unretained work\n"
        "\x1b[36m$ \x1b[0mreana-dev srcdir-workon test-bar\n"
    )


def test_srcdir_errors_colour_only_semantic_label():
    """Highlight the error label while leaving its explanation unstyled."""

    @click.command()
    def fail():
        raise srcdir.SrcdirError("Preserve the reported work.")

    coloured_result = CliRunner().invoke(fail, color=True)
    plain_result = CliRunner().invoke(fail)

    assert coloured_result.exit_code == 1
    assert coloured_result.output == (
        "\x1b[31mError:\x1b[0m Preserve the reported work.\n"
    )
    assert plain_result.exit_code == 1
    assert plain_result.output == "Error: Preserve the reported work.\n"


def _git(repository, *arguments):
    """Run Git in a test repository and return its output."""
    return subprocess.run(
        ["git", *arguments],
        cwd=str(repository),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _create_repository(source_root, name):
    """Create a small Git repository with a master commit."""
    repository = source_root / name
    repository.mkdir(parents=True)
    _git(repository, "init", "--initial-branch=master")
    _git(repository, "config", "user.email", "developer@example.org")
    _git(repository, "config", "user.name", "REANA Developer")
    _git(repository, "config", "commit.gpgsign", "false")
    (repository / "tracked.txt").write_text("master\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "initial")
    return repository


def _create_source_collection(tmp_path):
    """Create a minimal REANA source collection."""
    source_root = tmp_path / "reanahub"
    source_root.mkdir()
    _create_repository(source_root, "reana")
    _create_repository(source_root, "reana-server")
    return source_root


def _srcdir_root(source_root):
    """Return the default managed source-directory root."""
    return source_root.parent / f"{source_root.name}-srcdirs"


def _create_srcdir(runner, monkeypatch, source_root, name):
    """Invoke srcdir-create with derived-state work disabled."""
    monkeypatch.chdir(source_root)
    monkeypatch.setattr(
        srcdir,
        "_copy_source_directory",
        lambda source, destination: shutil.copytree(source, destination),
    )
    monkeypatch.setattr(srcdir, "_sync_shared_modules", lambda destination: None)
    return runner.invoke(
        reana_dev,
        [
            "srcdir-create",
            name,
            "--no-mise-venv",
        ],
    )


def test_srcdir_create_is_flat_clean_and_master_based(tmp_path, monkeypatch):
    """Create a flat srcdir without copying the baseline's branch state."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    server = source_root / "reana-server"
    _git(server, "switch", "--create", "feat-quota-period")
    (server / "tracked.txt").write_text("quota period\n", encoding="utf-8")
    (server / "untracked.txt").write_text("scratch\n", encoding="utf-8")

    result = _create_srcdir(CliRunner(), monkeypatch, source_root, "auth-alignment")

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "auth-alignment"
    assert destination.is_dir()
    assert not (srcdir_root / "reviews" / "auth-alignment").exists()
    assert _git(destination / "reana-server", "branch", "--show-current") == "master"
    assert (
        _git(
            destination / "reana-server",
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads",
        )
        == "master"
    )
    assert srcdir._git_ref_exists(
        destination / "reana-server",
        "refs/remotes/local/feat-quota-period",
    )
    assert _git(server, "branch", "--show-current") == "feat-quota-period"
    assert (destination / "reana-server" / "tracked.txt").read_text() == "master\n"
    assert not (destination / "reana-server" / "untracked.txt").exists()
    assert _git(destination / "reana-server", "remote", "get-url", "local") == str(
        server
    )
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["state"] == "ready"
    assert marker["repositories"] == ["reana", "reana-server"]
    assert marker["initial_heads"]["reana-server"] == _git(
        destination / "reana-server", "rev-parse", "HEAD"
    )
    assert (source_root / srcdir.SRCDIR_POINTER).is_file()
    assert (srcdir_root / srcdir.SRCDIR_ROOT_MARKER).is_file()
    assert result.output.startswith("==> Creating srcdir auth-alignment\n")
    assert "==> Preparing 2 repositories" in result.output
    assert "✓ Created srcdir auth-alignment" in result.output
    assert re.search(r"Location\s+" + re.escape(str(destination)), result.output)
    assert (
        "==> Next steps:\n"
        "$ reana-dev srcdir-workon auth-alignment\n"
        "$ reana-dev git-checkout-pr -i REPOSITORY ISSUE --pull --reset\n"
        "$ reana-dev git-submodule --update"
    ) in result.output
    assert "After composing branches:" not in result.output


def test_git_checkout_restores_pruned_branch_with_multiple_remote_matches(
    tmp_path, monkeypatch
):
    """Compose an inherited branch explicitly from local despite remote matches."""
    source_root = _create_source_collection(tmp_path)
    server = source_root / "reana-server"
    _git(server, "switch", "--create", "feat-quota-period")
    (server / "tracked.txt").write_text("quota period\n", encoding="utf-8")
    _git(server, "add", "tracked.txt")
    _git(server, "commit", "-m", "add quota period")

    create_result = _create_srcdir(
        CliRunner(), monkeypatch, source_root, "broker-backoff"
    )
    assert create_result.exit_code == 0, create_result.output

    destination = _srcdir_root(source_root) / "broker-backoff"
    repository = destination / "reana-server"
    canonical_branch = "refs/remotes/local/feat-quota-period"
    canonical_head = _git(repository, "rev-parse", canonical_branch)
    _git(
        repository,
        "update-ref",
        "refs/remotes/origin/feat-quota-period",
        canonical_head,
    )
    _git(
        repository,
        "update-ref",
        "refs/remotes/upstream/feat-quota-period",
        canonical_head,
    )
    monkeypatch.chdir(destination)

    checkout_result = CliRunner().invoke(
        reana_dev,
        ["git-checkout", "feat-quota-period", "-c", "reana-server"],
    )

    assert checkout_result.exit_code == 0, checkout_result.output
    assert _git(repository, "branch", "--show-current") == "feat-quota-period"
    assert _git(repository, "rev-parse", "HEAD") == canonical_head


def test_srcdir_create_prunes_branch_with_ambiguous_short_ref(tmp_path, monkeypatch):
    """Prune a local branch even when Git disambiguates its short ref name."""
    source_root = _create_source_collection(tmp_path)
    server = source_root / "reana-server"
    _git(server, "branch", "upstream/pr/657")
    _git(
        server,
        "update-ref",
        "refs/remotes/upstream/pr/657",
        "refs/heads/upstream/pr/657",
    )

    result = _create_srcdir(CliRunner(), monkeypatch, source_root, "eos-egress")

    assert result.exit_code == 0, result.output
    repository = _srcdir_root(source_root) / "eos-egress" / "reana-server"
    assert (
        _git(
            repository,
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads",
        )
        == "master"
    )
    assert srcdir._git_ref_exists(
        repository,
        "refs/remotes/upstream/pr/657",
    )


def test_srcdir_create_from_task_copies_canonical_source(tmp_path, monkeypatch):
    """Create from inside a task without nesting or copying that task."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    first_result = _create_srcdir(runner, monkeypatch, source_root, "condor-creds")
    assert first_result.exit_code == 0, first_result.output

    first = srcdir_root / "condor-creds"
    _git(
        first / "reana-server",
        "switch",
        "--create",
        "refactor-htcondor-api",
    )
    monkeypatch.chdir(first / "reana-server")
    second_result = runner.invoke(
        reana_dev, ["srcdir-create", "dask-dashboard", "--no-mise-venv"]
    )

    assert second_result.exit_code == 0, second_result.output
    second = srcdir_root / "dask-dashboard"
    assert second.is_dir()
    assert _git(second / "reana-server", "branch", "--show-current") == "master"
    assert not (first / "dask-dashboard").exists()


def test_srcdir_create_accepts_names_outside_recommended_convention(
    tmp_path, monkeypatch
):
    """Keep the naming guidance advisory rather than enforced."""
    source_root = _create_source_collection(tmp_path)
    runner = CliRunner()

    result = _create_srcdir(runner, monkeypatch, source_root, "2-feat-quota-period")

    assert result.exit_code == 0, result.output
    assert (_srcdir_root(source_root) / "2-feat-quota-period").is_dir()


def test_srcdir_create_rejects_nested_name(tmp_path, monkeypatch):
    """Require one flat directory name."""
    source_root = _create_source_collection(tmp_path)
    monkeypatch.chdir(source_root)
    result = CliRunner().invoke(
        reana_dev, ["srcdir-create", "auth/alignment", "--no-mise-venv"]
    )
    assert result.exit_code != 0
    assert "one flat directory name" in result.output


def test_srcdir_create_rejects_linked_worktree(tmp_path, monkeypatch):
    """Reject source collections containing linked Git worktrees."""
    source_root = tmp_path / "reanahub"
    source_root.mkdir()
    _create_repository(source_root, "reana")
    linked = source_root / "reana-server"
    linked.mkdir()
    (linked / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    monkeypatch.chdir(source_root)
    result = CliRunner().invoke(
        reana_dev, ["srcdir-create", "auth-alignment", "--no-mise-venv"]
    )
    assert result.exit_code != 0
    assert "linked Git worktree" in result.output


def test_srcdir_create_rejects_repository_with_registered_worktrees(
    tmp_path, monkeypatch
):
    """Reject a main checkout that still owns linked worktrees."""
    source_root = _create_source_collection(tmp_path)
    registered = source_root / "reana-server" / ".git" / "worktrees" / "task"
    registered.mkdir(parents=True)
    monkeypatch.chdir(source_root)

    result = CliRunner().invoke(
        reana_dev, ["srcdir-create", "auth-alignment", "--no-mise-venv"]
    )

    assert result.exit_code != 0
    assert "registered linked Git worktrees" in result.output
    assert "git -C" in result.output
    assert "worktree prune" in result.output


def test_srcdir_create_rolls_back_incomplete_destination(tmp_path, monkeypatch):
    """Remove a copied srcdir when repository preparation fails."""
    source_root = _create_source_collection(tmp_path)
    destination = _srcdir_root(source_root) / "dask-dashboard"

    def fail_preparation(*args):
        raise srcdir.click.ClickException("preparation failed")

    monkeypatch.setattr(srcdir, "_prepare_repository", fail_preparation)
    result = _create_srcdir(CliRunner(), monkeypatch, source_root, "dask-dashboard")

    assert result.exit_code != 0
    assert "preparation failed" in result.output
    assert not destination.exists()


def test_srcdir_copy_uses_reflinks_after_successful_linux_probe(
    tmp_path, monkeypatch, capsys
):
    """Use and announce reflinks after probing the two filesystem paths."""
    commands = []
    monkeypatch.setattr(srcdir.platform, "system", lambda: "Linux")

    def record_run(arguments, check=True):
        commands.append((arguments, check))
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(srcdir, "_run", record_run)

    srcdir._copy_source_directory(tmp_path / "source", tmp_path / "destination")

    probe_arguments, probe_check = commands[0]
    assert probe_arguments[:2] == ["cp", "--reflink=always"]
    assert probe_arguments[2] == str(tmp_path / "source/reana/.git/HEAD")
    assert probe_check is False
    assert commands[-1] == (
        [
            "cp",
            "--archive",
            "--reflink=always",
            str(tmp_path / "source"),
            str(tmp_path / "destination"),
        ],
        True,
    )
    output = capsys.readouterr().out
    assert "==> Copying source collection" in output
    assert re.search(r"Strategy\s+copy-on-write clone", output)


def test_srcdir_copy_uses_full_copy_after_failed_linux_probe(
    tmp_path, monkeypatch, capsys
):
    """Announce a sized full copy when the Linux reflink probe fails."""
    commands = []
    monkeypatch.setattr(srcdir.platform, "system", lambda: "Linux")

    def record_run(arguments, check=True):
        commands.append((arguments, check))
        if arguments[:2] == ["cp", "--reflink=always"]:
            return subprocess.CompletedProcess(arguments, 1, "", "unsupported")
        if arguments[:2] == ["du", "-sk"]:
            return subprocess.CompletedProcess(arguments, 0, "782336\tsource\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(srcdir, "_run", record_run)

    srcdir._copy_source_directory(tmp_path / "source", tmp_path / "destination")

    assert commands[-1] == (
        [
            "cp",
            "--archive",
            "--reflink=never",
            str(tmp_path / "source"),
            str(tmp_path / "destination"),
        ],
        True,
    )
    assert re.search(r"Strategy\s+full copy, about 764 MiB", capsys.readouterr().out)


def test_srcdir_copy_uses_full_copy_on_other_platforms(tmp_path, monkeypatch, capsys):
    """Use a clearly announced archival copy on other Unix platforms."""
    commands = []
    monkeypatch.setattr(srcdir.platform, "system", lambda: "FreeBSD")

    def record_run(arguments, check=True):
        commands.append((arguments, check))
        if arguments[:2] == ["du", "-sk"]:
            return subprocess.CompletedProcess(arguments, 0, "1024\tsource\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(srcdir, "_run", record_run)

    srcdir._copy_source_directory(tmp_path / "source", tmp_path / "destination")

    assert commands[-1] == (
        [
            "cp",
            "-a",
            str(tmp_path / "source"),
            str(tmp_path / "destination"),
        ],
        True,
    )
    assert re.search(r"Strategy\s+full copy, about 1 MiB", capsys.readouterr().out)


def test_srcdir_copy_uses_full_copy_on_non_apfs_macos_volume(
    tmp_path, monkeypatch, capsys
):
    """Use a normal archival copy when clonefile is unavailable."""
    commands = []
    monkeypatch.setattr(srcdir.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(srcdir, "_darwin_filesystem", lambda path: "hfs")

    def record_run(arguments, check=True):
        commands.append((arguments, check))
        if arguments[:2] == ["du", "-sk"]:
            return subprocess.CompletedProcess(arguments, 0, "1024\tsource\n", "")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(srcdir, "_run", record_run)

    srcdir._copy_source_directory(tmp_path / "source", tmp_path / "destination")

    assert commands[-1] == (
        [
            "cp",
            "-a",
            str(tmp_path / "source"),
            str(tmp_path / "destination"),
        ],
        True,
    )
    assert re.search(r"Strategy\s+full copy, about 1 MiB", capsys.readouterr().out)


def test_srcdir_copy_uses_clonefile_on_same_apfs_volume(tmp_path, monkeypatch, capsys):
    """Use clonefile when both macOS paths share an APFS filesystem."""
    source = tmp_path / "source"
    source.mkdir()
    commands = []
    monkeypatch.setattr(srcdir.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(srcdir, "_darwin_filesystem", lambda path: "apfs")

    def record_run(arguments, check=True):
        commands.append((arguments, check))
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(srcdir, "_run", record_run)

    srcdir._copy_source_directory(source, tmp_path / "destination")

    assert commands == [
        (["cp", "-ac", str(source), str(tmp_path / "destination")], True)
    ]
    assert re.search(r"Strategy\s+copy-on-write clone", capsys.readouterr().out)


def test_darwin_filesystem_handles_mountpoint_with_spaces(tmp_path, monkeypatch):
    """Preserve the complete mountpoint while identifying APFS volumes."""

    def fake_run(arguments, check=True):
        if arguments[0] == "df":
            output = (
                "Filesystem 512-blocks Used Available Capacity Mounted on\n"
                "/dev/disk7 100 10 90 10% /Volumes/Backup Disk\n"
            )
        else:
            output = "/dev/disk7 on /Volumes/Backup Disk (apfs, local)\n"
        return subprocess.CompletedProcess(arguments, 0, output, "")

    monkeypatch.setattr(srcdir, "_run", fake_run)

    assert srcdir._darwin_filesystem(tmp_path) == "apfs"


def test_srcdir_list_reports_local_changes(tmp_path, monkeypatch):
    """Summarise changed HEADs, dirty repositories, and unique commits."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output

    repository = srcdir_root / "broker-backoff" / "reana-server"
    _git(repository, "switch", "--create", "feat-quota-period")
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "change")
    _git(
        repository,
        "update-ref",
        "refs/remotes/contributor/feat-quota-period",
        "HEAD",
    )
    (repository / "untracked.txt").write_text("scratch\n", encoding="utf-8")
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.chdir(srcdir_root)

    result = runner.invoke(reana_dev, ["srcdir-list"])

    assert result.exit_code == 0, result.output
    assert re.search(
        r"broker-backoff\s+ready\s+1\s+1\s+1\s+0\s+-\s+stopped",
        result.output,
    )
    marker = json.loads(
        (srcdir_root / "broker-backoff" / srcdir.SRCDIR_MARKER).read_text()
    )
    findings = srcdir._audit_before_delete(srcdir_root / "broker-backoff", marker)
    assert any(
        "commits not found in refreshed refs (canonical)" in item for item in findings
    )


def test_unique_commits_without_remotes_returns_unverified(tmp_path, monkeypatch):
    """Return an unverified sentinel without querying repository history."""

    def record_git(repository, *git_arguments):
        raise AssertionError("Git history must not be queried without remotes")

    monkeypatch.setattr(srcdir, "_git", record_git)

    commits = srcdir._unique_commits(tmp_path, [])

    assert commits is None


def test_srcdir_list_marks_unverified_unique_count(tmp_path, monkeypatch):
    """Render unknown uniqueness without traversing full repository history."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    repository = srcdir_root / "broker-backoff" / "reana-server"
    _git(repository, "remote", "remove", "local")
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.chdir(srcdir_root)

    result = runner.invoke(reana_dev, ["srcdir-list"])

    assert result.exit_code == 0, result.output
    assert re.search(
        r"broker-backoff\s+ready\s+0\s+0\s+\?\s+0\s+-\s+stopped",
        result.output,
    )


def test_srcdir_delete_refuses_dirty_source_directory(tmp_path, monkeypatch):
    """Refuse teardown when an uncommitted file would be lost."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "dask-dashboard")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "dask-dashboard"
    (destination / "reana-server" / "scratch.txt").write_text(
        "important\n", encoding="utf-8"
    )
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.chdir(srcdir_root)

    result = runner.invoke(reana_dev, ["srcdir-delete", "dask-dashboard", "--yes"])

    assert result.exit_code != 0
    assert "uncommitted files" in result.output
    assert "Refusing teardown" in result.output
    assert "repeat with --no-audit" in result.output
    assert destination.is_dir()


def test_srcdir_delete_skips_audit_but_requires_confirmation(tmp_path, monkeypatch):
    """Keep confirmation independent when explicitly disabling the audit."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "dask-dashboard")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "dask-dashboard"
    (destination / "reana-server" / "scratch.txt").write_text(
        "important\n", encoding="utf-8"
    )
    trash = tmp_path / "Trash"
    monkeypatch.setattr(srcdir, "_trash_directory", lambda: trash)
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(
        srcdir,
        "_audit_before_delete",
        lambda *arguments: pytest.fail("The audit must be skipped"),
    )
    monkeypatch.chdir(srcdir_root)

    refused_result = runner.invoke(
        reana_dev,
        ["srcdir-delete", "dask-dashboard", "--no-audit"],
        input="n\n",
    )

    assert refused_result.exit_code == 1
    assert destination.is_dir()
    assert "Skipping teardown audit for srcdir dask-dashboard" in (
        refused_result.output
    )
    assert f"Location     {destination}" in refused_result.output
    assert "Warning: Unretained work may be present" in refused_result.output
    assert f"Move {destination} to Trash? [y/N]: n" in refused_result.output

    result = runner.invoke(
        reana_dev,
        [
            "srcdir-delete",
            "dask-dashboard",
            "--no-audit",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not destination.exists()
    trashed = list(trash.glob("dask-dashboard-*"))
    assert len(trashed) == 1
    assert "Auditing srcdir" not in result.output
    assert f"Location     {destination}" in result.output
    assert "Warning: Unretained work may be present" in result.output
    assert "to Trash?" not in result.output


def test_srcdir_delete_moves_safe_source_directory_to_trash(tmp_path, monkeypatch):
    """Move an audited source directory to a recoverable Trash location."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "auth-alignment")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "auth-alignment"
    trash = tmp_path / "Trash"
    monkeypatch.setattr(srcdir, "_trash_directory", lambda: trash)
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.chdir(srcdir_root)

    result = runner.invoke(reana_dev, ["srcdir-delete", "auth-alignment", "--yes"])

    assert result.exit_code == 0, result.output
    assert not destination.exists()
    trashed = list(trash.glob("auth-alignment-*"))
    assert len(trashed) == 1
    assert (trashed[0] / srcdir.SRCDIR_MARKER).is_file()
    assert "==> Auditing srcdir auth-alignment" in result.output
    assert "✓ Teardown audit found no unretained work" in result.output
    assert "==> Moving srcdir auth-alignment to Trash" in result.output
    assert "✓ Moved srcdir auth-alignment to Trash" in result.output
    assert str(trashed[0]) in result.output


def test_srcdir_delete_is_safe_when_baseline_is_missing(tmp_path, monkeypatch):
    """Treat local state as unretained when the baseline has moved."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "auth-alignment")
    assert create_result.exit_code == 0, create_result.output
    source_root.rename(tmp_path / "moved-reanahub")
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.chdir(srcdir_root)

    result = runner.invoke(reana_dev, ["srcdir-delete", "auth-alignment", "--yes"])

    assert result.exit_code != 0
    assert "Canonical source directory is missing" in result.output
    assert "no remote could be verified" in result.output
    assert "treating all local commits as unretained" in result.output
    assert "initial" not in result.output
    assert "Refusing teardown" in result.output


def test_srcdir_list_continues_after_damaged_marker(tmp_path, monkeypatch):
    """Show an error row without hiding healthy managed srcdirs."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    damaged = srcdir_root / "auth-alignment"
    damaged.mkdir()
    marker = json.loads(
        (srcdir_root / "broker-backoff" / srcdir.SRCDIR_MARKER).read_text()
    )
    marker["name"] = "wrong-name"
    (damaged / srcdir.SRCDIR_MARKER).write_text(json.dumps(marker), encoding="utf-8")
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.chdir(srcdir_root)

    result = runner.invoke(reana_dev, ["srcdir-list"])

    assert result.exit_code == 0, result.output
    assert re.search(r"broker-backoff\s+ready", result.output)
    assert re.search(r"auth-alignment\s+ERROR", result.output)
    assert "Warning: cannot inspect auth-alignment" in result.output


def test_srcdir_workon_opens_shell_in_source_directory(tmp_path, monkeypatch):
    """Open an interactive shell in the selected source directory by default."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    original_which = srcdir.shutil.which

    def resolve_executable(command):
        if command == "/bin/zsh":
            return "/bin/zsh"
        if command == "tmux":
            return "/usr/bin/tmux"
        return original_which(command)

    monkeypatch.setattr(srcdir.shutil, "which", resolve_executable)
    commands = []

    def record_run(arguments, destination, environment):
        commands.append((arguments, destination, environment))

    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: pytest.fail("plain workon must not inspect Tmux sessions"),
    )
    monkeypatch.setattr(srcdir, "_run_interactive", record_run)
    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])

    assert result.exit_code == 0, result.output
    assert len(commands) == 1
    arguments, destination, _ = commands[0]
    assert arguments == ["/bin/zsh", "-i"]
    assert destination == srcdir_root / "broker-backoff"
    assert (
        "==> Opening shell for srcdir broker-backoff\n"
        f"{'Location':<13}{destination}\n"
        "\n"
        "Exit the shell to return."
    ) in result.output


def test_srcdir_workon_no_tmux_overrides_managed_terminal_context(
    tmp_path, monkeypatch
):
    """Open a plain shell when --no-tmux overrides Kitty and Tmux."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("TMUX", "socket,client,0")
    monkeypatch.setenv("KITTY_WINDOW_ID", "17")
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setattr(
        srcdir,
        "_kitty_remote_tree",
        lambda: pytest.fail("--no-tmux must not inspect Kitty"),
    )
    original_which = srcdir.shutil.which

    def resolve_executable(command):
        if command == "tmux":
            pytest.fail("--no-tmux must not inspect the tmux executable")
        return "/bin/zsh" if command == "/bin/zsh" else original_which(command)

    monkeypatch.setattr(srcdir.shutil, "which", resolve_executable)
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: pytest.fail("--no-tmux must not inspect Tmux sessions"),
    )
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run_interactive",
        lambda arguments, destination, environment: commands.append(
            (arguments, destination, environment)
        ),
    )

    result = runner.invoke(
        reana_dev,
        ["srcdir-workon", "broker-backoff", "--no-tmux"],
    )

    assert result.exit_code == 0, result.output
    assert len(commands) == 1
    arguments, shell_destination, _ = commands[0]
    assert arguments == ["/bin/zsh", "-i"]
    assert shell_destination == destination


def test_run_interactive_ignores_shell_exit_status(tmp_path, monkeypatch):
    """Return cleanly when an interactive shell's last command failed."""
    calls = []

    def record_run(arguments, cwd=None, env=None, check=True):
        calls.append((arguments, cwd, env, check))
        return subprocess.CompletedProcess(arguments, 1, "", "")

    monkeypatch.setattr(srcdir.subprocess, "run", record_run)
    srcdir._run_interactive(["/bin/zsh", "-i"], tmp_path, {"EXAMPLE": "1"})

    assert calls == [(["/bin/zsh", "-i"], str(tmp_path), {"EXAMPLE": "1"}, False)]


def test_srcdir_workon_selects_mise_virtual_environment(tmp_path, monkeypatch):
    """Run a srcdir shell through mise when it owns a local environment."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    marker_path = destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["python_environment"] = "mise"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    srcdir._write_mise_config(destination)
    reana_dev_executable = destination / ".venv" / "bin" / "reana-dev"
    reana_dev_executable.parent.mkdir(parents=True)
    reana_dev_executable.write_text(
        f"#!{destination / '.venv' / 'bin' / 'python'}\n", encoding="utf-8"
    )
    monkeypatch.chdir(srcdir_root)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: (
            command if command in {"/bin/zsh", "mise"} else original_which(command)
        ),
    )
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run_interactive",
        lambda arguments, destination, environment: commands.append(
            (arguments, destination, environment)
        ),
    )

    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])

    assert result.exit_code == 0, result.output
    arguments, shell_destination, _ = commands[0]
    assert arguments == [
        "mise",
        "exec",
        "-C",
        str(destination),
        "--",
        "/bin/zsh",
        "-i",
    ]
    assert shell_destination == destination


def test_interactive_shell_arguments_uses_login_shell_with_mise(monkeypatch):
    """Keep login initialisation around the srcdir's mise environment."""
    destination = Path("/srcdirs/broker-backoff")
    monkeypatch.setattr(srcdir.shutil, "which", lambda command: command)

    arguments = srcdir._interactive_shell_arguments(
        destination,
        {"python_environment": "mise"},
        "/bin/zsh",
        login=True,
    )

    assert arguments == [
        "mise",
        "exec",
        "-C",
        str(destination),
        "--",
        "/bin/zsh",
        "-l",
    ]


def test_srcdir_workon_auto_selects_tmux_from_managed_session(tmp_path, monkeypatch):
    """Auto-select Tmux from a managed terminal context."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "auth.alignment")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("TMUX", "socket,client,0")
    monkeypatch.setenv("KITTY_WINDOW_ID", "17")
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(
        srcdir,
        "_kitty_remote_tree",
        lambda: pytest.fail("Kitty must yield to Tmux"),
    )
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: (
            "/usr/bin/tmux" if command == "tmux" else original_which(command)
        ),
    )
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    commands = []

    def record_run(arguments, cwd=None, check=True):
        commands.append(arguments)
        stdout = "$7\n" if arguments[:2] == ["tmux", "new-session"] else ""
        return subprocess.CompletedProcess(arguments, 0, stdout, "")

    monkeypatch.setattr(srcdir, "_run", record_run)
    result = runner.invoke(reana_dev, ["srcdir-workon", "auth.alignment"])

    assert result.exit_code == 0, result.output
    assert "==> Creating Tmux session auth-alignment" in result.output
    assert "==> Entering Tmux session auth-alignment" in result.output
    assert [
        "tmux",
        "new-session",
        "-d",
        "-P",
        "-F",
        "#{session_id}",
        "-s",
        "auth-alignment",
        "-c",
        str(srcdir_root / "auth.alignment"),
        "/bin/sh -l",
    ] in commands
    assert [
        "tmux",
        "set-option",
        "-t",
        "$7",
        srcdir.TMUX_SRCDIR_OPTION,
        str(srcdir_root / "auth.alignment"),
    ] in commands
    assert ["tmux", "switch-client", "-t", "$7"] in commands


def test_srcdir_workon_auto_creates_kitty_session(tmp_path, monkeypatch):
    """Generate and activate a Kitty session when running inside Kitty."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "auth.alignment")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "auth.alignment"
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("KITTY_WINDOW_ID", "17")
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(srcdir, "_kitty_remote_tree", lambda: [])
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments)
        or subprocess.CompletedProcess(arguments, 0, "", ""),
    )

    result = runner.invoke(reana_dev, ["srcdir-workon", "auth.alignment"])

    assert result.exit_code == 0, result.output
    session_path = srcdir._kitty_session_path("auth.alignment")
    assert session_path.name == "auth.alignment.kitty-session"
    assert "==> Creating Kitty session auth.alignment" in result.output
    assert session_path.is_file()
    contents = session_path.read_text()
    assert contents.startswith(srcdir.KITTY_SESSION_HEADER)
    assert "new_os_window" not in contents
    launch_arguments = shlex.split(contents.splitlines()[2][len("launch ") :])
    assert launch_arguments == [
        "--cwd",
        str(destination),
        "--var",
        f"{srcdir.KITTY_SRCDIR_VAR}={destination}",
        "/bin/sh",
        "-l",
    ]
    assert commands == [
        [
            "kitten",
            "@",
            "--to",
            "unix:/tmp/kitty-test",
            "action",
            "goto_session",
            str(session_path),
        ]
    ]
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["kitty_session"] == str(session_path)


def test_srcdir_workon_refuses_foreign_same_named_kitty_session(tmp_path, monkeypatch):
    """Do not let Kitty's flat session namespace redirect the workon."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "c4p-gpus")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("KITTY_WINDOW_ID", "17")
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(
        srcdir,
        "_kitty_remote_tree",
        lambda: [
            {
                "tabs": [
                    {
                        "windows": [
                            {
                                "id": 23,
                                "session_name": "c4p-gpus",
                                "user_vars": {},
                            }
                        ]
                    }
                ]
            }
        ],
    )
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: pytest.fail(
            "a foreign Kitty session must not be entered"
        ),
    )

    result = runner.invoke(reana_dev, ["srcdir-workon", "c4p-gpus"])

    assert result.exit_code != 0
    assert "Kitty session 'c4p-gpus' is already open for something else" in (
        result.output
    )
    assert not srcdir._kitty_session_path("c4p-gpus").exists()


def test_srcdir_workon_switches_to_running_kitty_session(tmp_path, monkeypatch):
    """Focus an existing Kitty session instead of creating another one."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("KITTY_WINDOW_ID", "17")
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(
        srcdir,
        "_kitty_remote_tree",
        lambda: [
            {
                "tabs": [
                    {
                        "windows": [
                            {
                                "id": 23,
                                "session_name": "broker-backoff",
                                "user_vars": {
                                    srcdir.KITTY_SRCDIR_VAR: str(destination)
                                },
                            }
                        ]
                    }
                ]
            }
        ],
    )
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments)
        or subprocess.CompletedProcess(arguments, 0, "", ""),
    )

    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])

    assert result.exit_code == 0, result.output
    assert "==> Entering Kitty session broker-backoff" in result.output
    assert len(commands) == 1
    assert commands[0][-3:] == [
        "action",
        "goto_session",
        str(srcdir._kitty_session_path("broker-backoff")),
    ]


def test_srcdir_workon_unreachable_kitty_falls_back_to_plain_shell(
    tmp_path, monkeypatch
):
    """Keep workon useful when Kitty remote control is not reachable."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("KITTY_WINDOW_ID", "17")
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/missing-kitty")
    monkeypatch.setattr(srcdir, "_kitty_remote_tree", lambda: None)
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run_interactive",
        lambda arguments, destination, environment: commands.append(
            (arguments, destination, environment)
        ),
    )

    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])

    assert result.exit_code == 0, result.output
    assert "Kitty remote control is unavailable" in result.output
    assert commands[0][0] == ["/bin/sh", "-i"]


def test_srcdir_workon_explicit_kitty_reports_missing_remote_control(
    tmp_path, monkeypatch
):
    """Explain why an explicitly requested Kitty backend cannot be used."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: (
            "/usr/bin/kitten" if command == "kitten" else original_which(command)
        ),
    )

    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff", "--kitty"])

    assert result.exit_code != 0
    assert "--kitty requires Kitty remote control via KITTY_LISTEN_ON" in result.output


def test_srcdir_workon_migrates_running_legacy_tmux_session(tmp_path, monkeypatch):
    """Migrate a live legacy session and ignore the attach client's status."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "auth-alignment")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "auth-alignment"
    marker_path = destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["tmux_session"] = "reana-auth-alignment"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    monkeypatch.chdir(srcdir_root)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setenv("SHELL", "/bin/sh")
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: (
            "/usr/bin/tmux" if command == "tmux" else original_which(command)
        ),
    )
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"reana-auth-alignment": ("$8", None, str(destination))},
    )
    regular_commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: regular_commands.append(arguments),
    )
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run_interactive",
        lambda arguments, destination, environment: commands.append(
            (arguments, destination, environment)
        ),
    )

    result = runner.invoke(
        reana_dev,
        ["srcdir-workon", "auth-alignment", "-t"],
    )

    assert result.exit_code == 0, result.output
    assert len(commands) == 1
    arguments, shell_destination, environment = commands[0]
    assert arguments == ["tmux", "attach-session", "-t", "$8"]
    assert shell_destination == destination
    assert environment["SHELL"] == "/bin/sh"
    assert [
        "tmux",
        "rename-session",
        "-t",
        "$8",
        "auth-alignment",
    ] in regular_commands
    assert [
        "tmux",
        "set-option",
        "-t",
        "$8",
        srcdir.TMUX_SRCDIR_OPTION,
        str(destination),
    ] in regular_commands
    assert json.loads(marker_path.read_text())["tmux_session"] == ("auth-alignment")


def test_srcdir_workon_reports_unavailable_tmux(tmp_path, monkeypatch):
    """Distinguish an ambient Tmux choice from an explicit request."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("TMUX", "socket,client,0")
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: None if command == "tmux" else original_which(command),
    )
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: pytest.fail("unavailable Tmux must fail before listing sessions"),
    )

    automatic = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])
    explicit = runner.invoke(
        reana_dev,
        ["srcdir-workon", "broker-backoff", "--tmux"],
    )

    assert automatic.exit_code != 0
    assert "TMUX is set, but the tmux executable is unavailable" in automatic.output
    assert "Use --no-tmux" in automatic.output
    assert explicit.exit_code != 0
    assert "--tmux requires the tmux executable" in explicit.output


def test_srcdir_workon_reallocates_late_foreign_tmux_collision(tmp_path, monkeypatch):
    """Move to a free name when a foreign session takes the recorded name."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv("SHELL", "/bin/sh")
    monkeypatch.setenv("TMUX", "socket,client,0")
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: (
            "/usr/bin/tmux" if command == "tmux" else original_which(command)
        ),
    )
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"broker-backoff": ("$9", None, "/private/tmp")},
    )
    commands = []

    def record_run(arguments, cwd=None, check=True):
        commands.append(arguments)
        stdout = "$10\n" if arguments[:2] == ["tmux", "new-session"] else ""
        return subprocess.CompletedProcess(arguments, 0, stdout, "")

    monkeypatch.setattr(srcdir, "_run", record_run)

    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff", "--tmux"])

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "broker-backoff"
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["tmux_session"].startswith("broker-backoff-")
    assert any(command[:2] == ["tmux", "new-session"] for command in commands)
    assert ["tmux", "switch-client", "-t", "$10"] in commands
    assert not any("$9" in command for command in commands)


def test_srcdir_list_reports_same_named_foreign_tmux_session(tmp_path, monkeypatch):
    """Report a same-named unmarked Tmux session as a conflict."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"broker-backoff": ("$9", None, "/private/tmp")},
    )

    result = runner.invoke(reana_dev, ["srcdir-list"])

    assert result.exit_code == 0, result.output
    assert re.search(r"broker-backoff\s+ready.*conflict", result.output)


def test_srcdir_list_reports_running_kitty_session(tmp_path, monkeypatch):
    """Show Kitty session state independently from Tmux state."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(srcdir, "_list_kitty_sessions", lambda: {str(destination)})

    result = runner.invoke(reana_dev, ["srcdir-list"])

    assert result.exit_code == 0, result.output
    assert "TMUX" in result.output
    assert "KITTY" in result.output
    assert re.search(r"broker-backoff\s+ready.*stopped\s+running", result.output)


def test_srcdir_list_marks_unavailable_kitty_state_as_unknown(tmp_path, monkeypatch):
    """Do not claim a Kitty session is stopped when it cannot be queried."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(srcdir, "_list_kitty_sessions", lambda: None)

    result = runner.invoke(reana_dev, ["srcdir-list"])

    assert result.exit_code == 0, result.output
    assert re.search(r"broker-backoff\s+ready.*stopped\s+-", result.output)
    assert "Kitty state unavailable" in result.output


def test_srcdir_delete_ignores_same_named_foreign_tmux_session(tmp_path, monkeypatch):
    """Delete the srcdir without killing a same-named foreign session."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"broker-backoff": ("$9", None, "/private/tmp")},
    )
    monkeypatch.setattr(srcdir, "_trash_directory", lambda: tmp_path / "Trash")
    original_run = srcdir._run
    commands = []

    def record_run(arguments, **kwargs):
        commands.append(arguments)
        return original_run(arguments, **kwargs)

    monkeypatch.setattr(srcdir, "_run", record_run)

    result = runner.invoke(
        reana_dev,
        ["srcdir-delete", "broker-backoff", "--kill-tmux", "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert not (srcdir_root / "broker-backoff").exists()
    assert ["tmux", "kill-session", "-t", "$9"] not in commands


def test_srcdir_rename_preserves_repository_state(tmp_path, monkeypatch):
    """Rename a srcdir without changing its branches or working files."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    assert create_result.exit_code == 0, create_result.output
    old_destination = srcdir_root / "eos-egress"
    repository = old_destination / "reana-server"
    _git(repository, "switch", "--create", "gitlab-group")
    (repository / "scratch.txt").write_text("preserve me\n", encoding="utf-8")
    old_marker = json.loads((old_destination / srcdir.SRCDIR_MARKER).read_text())
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "eos-egress", "gitlab-groups"],
    )

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "gitlab-groups"
    assert not old_destination.exists()
    assert (destination / "reana-server" / "scratch.txt").read_text() == (
        "preserve me\n"
    )
    assert _git(destination / "reana-server", "branch", "--show-current") == (
        "gitlab-group"
    )
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["name"] == "gitlab-groups"
    assert marker["tmux_session"] == "gitlab-groups"
    assert marker["initial_heads"] == old_marker["initial_heads"]
    assert "==> Renaming srcdir eos-egress to gitlab-groups" in result.output
    assert "✓ Renamed srcdir eos-egress to gitlab-groups" in result.output
    assert ("==> Next steps:\n$ reana-dev srcdir-workon gitlab-groups") in result.output


def test_srcdir_rename_discards_path_bound_virtual_environment(tmp_path, monkeypatch):
    """Update the named environment and discard its path-bound files."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    old_destination = srcdir_root / "broker-backoff"
    marker_path = old_destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["python_environment"] = "mise"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    srcdir._write_mise_config(old_destination)
    reana_dev_entry_point = old_destination / ".venv" / "bin" / "reana-dev"
    reana_dev_entry_point.parent.mkdir(parents=True)
    reana_dev_entry_point.write_text(
        f"#!{old_destination / '.venv' / 'bin' / 'python'}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "broker-backoff", "auth-alignment"],
    )

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "auth-alignment"
    assert not (destination / ".venv").exists()
    mise_config = (destination / srcdir.MISE_LOCAL_CONFIG).read_text()
    assert '"--prompt", "auth-alignment"' in mise_config
    assert '"--prompt", "broker-backoff"' not in mise_config
    assert "srcdir-workon will recreate it" in result.output


def test_srcdir_rename_preserves_custom_mise_configuration(tmp_path, monkeypatch):
    """Keep developer-owned mise configuration unchanged during rename."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    old_destination = srcdir_root / "broker-backoff"
    marker_path = old_destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["python_environment"] = "mise"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    custom_config = "[tools]\nnode = '22'\n"
    (old_destination / srcdir.MISE_LOCAL_CONFIG).write_text(
        custom_config, encoding="utf-8"
    )
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "broker-backoff", "auth-alignment"],
    )

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "auth-alignment"
    assert (destination / srcdir.MISE_LOCAL_CONFIG).read_text() == custom_config
    assert "Keeping the customised mise.local.toml" in result.output


def test_srcdir_rename_requires_stopping_owned_tmux_session(tmp_path, monkeypatch):
    """Require explicit permission before stopping a srcdir's Tmux session."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    assert create_result.exit_code == 0, create_result.output
    source = srcdir_root / "eos-egress"
    marker = json.loads((source / srcdir.SRCDIR_MARKER).read_text())
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {marker["tmux_session"]: ("$8", str(source), str(source))},
    )
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments),
    )
    monkeypatch.setattr(srcdir, "_current_tmux_session_id", lambda: None)

    refused = runner.invoke(
        reana_dev,
        ["srcdir-rename", "eos-egress", "gitlab-groups"],
    )
    renamed = runner.invoke(
        reana_dev,
        [
            "srcdir-rename",
            "eos-egress",
            "gitlab-groups",
            "--kill-tmux",
        ],
    )

    assert refused.exit_code != 0
    assert "pass --kill-tmux" in refused.output
    assert renamed.exit_code == 0, renamed.output
    assert ["tmux", "kill-session", "-t", "$8"] in commands


def test_srcdir_rename_refuses_to_run_from_inside_target(tmp_path, monkeypatch):
    """Avoid leaving the invoking shell in a renamed directory."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root / "eos-egress" / "reana-server")

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "eos-egress", "gitlab-groups"],
    )

    assert result.exit_code != 0
    assert "while working inside it" in result.output


def test_srcdir_rename_refuses_existing_destination(tmp_path, monkeypatch):
    """Never overwrite another managed srcdir during a rename."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    first_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    second_result = _create_srcdir(runner, monkeypatch, source_root, "gitlab-groups")
    assert first_result.exit_code == 0, first_result.output
    assert second_result.exit_code == 0, second_result.output
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "eos-egress", "gitlab-groups"],
    )

    assert result.exit_code != 0
    assert "Destination already exists" in result.output
    assert (srcdir_root / "eos-egress").is_dir()
    assert (srcdir_root / "gitlab-groups").is_dir()


def test_srcdir_rename_disambiguates_taken_tmux_target(tmp_path, monkeypatch):
    """Disambiguate a renamed srcdir from a live foreign Tmux session."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"gitlab-groups": ("$9", None, "/private/tmp")},
    )

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "eos-egress", "gitlab-groups"],
    )

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "gitlab-groups"
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["tmux_session"].startswith("gitlab-groups-")


def test_srcdir_rename_ignores_late_foreign_tmux_collision(tmp_path, monkeypatch):
    """Rename a srcdir without touching a foreign session using its old name."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "dask-dashboard")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"dask-dashboard": ("$9", None, "/private/tmp")},
    )
    commands = []
    original_run = srcdir._run

    def record_run(arguments, **kwargs):
        commands.append(arguments)
        return original_run(arguments, **kwargs)

    monkeypatch.setattr(srcdir, "_run", record_run)

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "dask-dashboard", "condor-creds"],
    )

    assert result.exit_code == 0, result.output
    destination = srcdir_root / "condor-creds"
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["tmux_session"] == "condor-creds"
    assert not any(
        command[:2] == ["tmux", "rename-session"] or "$9" in command
        for command in commands
    )


def test_srcdir_create_disambiguates_live_tmux_session(tmp_path, monkeypatch):
    """Allocate a usable Tmux name when the exact global name is taken."""
    source_root = _create_source_collection(tmp_path)
    monkeypatch.setattr(
        srcdir,
        "_list_tmux_sessions",
        lambda: {"dask-dashboard": ("$9", None, "/private/tmp")},
    )

    result = _create_srcdir(CliRunner(), monkeypatch, source_root, "dask-dashboard")

    assert result.exit_code == 0, result.output
    destination = _srcdir_root(source_root) / "dask-dashboard"
    marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert marker["tmux_session"].startswith("dask-dashboard-")


def test_owned_tmux_session_adopts_matching_session_path(tmp_path, monkeypatch):
    """Adopt an unmarked intermediate-commit session only by exact path."""
    destination = tmp_path / "broker-backoff"
    destination.mkdir()
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments),
    )

    session_id = srcdir._owned_tmux_session_id(
        "broker-backoff",
        ("$8", None, str(destination)),
        destination,
    )

    assert session_id == "$8"
    assert [
        "tmux",
        "set-option",
        "-t",
        "$8",
        srcdir.TMUX_SRCDIR_OPTION,
        str(destination),
    ] in commands


def test_list_tmux_sessions_reads_owner_and_session_path(monkeypatch):
    """Parse marked and unmarked Tmux sessions with their initial paths."""
    monkeypatch.setattr(srcdir.shutil, "which", lambda command: "/usr/bin/tmux")
    output = (
        "$16\tmarked\t/some/srcdir\t/some/srcdir\n" "$15\tunmarked\t\t/private/tmp\n"
    )
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: subprocess.CompletedProcess(
            arguments, 0, output, ""
        ),
    )

    sessions = srcdir._list_tmux_sessions()

    assert sessions == {
        "marked": ("$16", "/some/srcdir", "/some/srcdir"),
        "unmarked": ("$15", None, "/private/tmp"),
    }


def test_kitty_srcdir_sessions_reads_window_user_variables():
    """Index tagged Kitty windows without depending on session display names."""
    sessions = srcdir._kitty_srcdir_sessions(
        [
            {
                "tabs": [
                    {
                        "windows": [
                            {
                                "id": 41,
                                "session_name": "broker-backoff",
                                "user_vars": {
                                    srcdir.KITTY_SRCDIR_VAR: "/srcdirs/broker-backoff"
                                },
                            },
                            {
                                "id": 42,
                                "session_name": "broker-backoff",
                                "user_vars": {},
                            },
                        ]
                    }
                ]
            }
        ]
    )

    assert sessions == {"/srcdirs/broker-backoff"}


def test_kitty_session_owners_pairs_each_window_with_its_own_session():
    """Read session names from windows, which is where Kitty reports them.

    One OS window commonly holds tabs belonging to different sessions, so a
    foreign session must not inherit a srcdir tag from a sibling tab.
    """
    owners = srcdir._kitty_session_owners(
        [
            {
                "tabs": [
                    {
                        "windows": [
                            {
                                "id": 41,
                                "session_name": "broker-backoff",
                                "user_vars": {
                                    srcdir.KITTY_SRCDIR_VAR: "/srcdirs/broker-backoff"
                                },
                            }
                        ]
                    },
                    {
                        "windows": [
                            {"id": 42, "session_name": "c4p-gpus", "user_vars": {}}
                        ]
                    },
                ]
            }
        ]
    )

    assert owners == {
        "broker-backoff": {"/srcdirs/broker-backoff"},
        "c4p-gpus": set(),
    }
    assert srcdir._foreign_kitty_session(
        [
            {
                "tabs": [
                    {
                        "windows": [
                            {"id": 42, "session_name": "c4p-gpus", "user_vars": {}}
                        ]
                    }
                ]
            }
        ],
        "c4p-gpus",
        Path("/srcdirs/c4p-gpus"),
    )


def test_kitty_remote_tree_reads_the_configured_endpoint(monkeypatch):
    """Read Kitty state through the endpoint exported into its windows."""
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(srcdir.shutil, "which", lambda command: "/usr/bin/kitten")
    commands = []

    def record_run(arguments, **kwargs):
        commands.append((arguments, kwargs))
        return subprocess.CompletedProcess(
            arguments, 0, '[{"session_name": "broker-backoff"}]', ""
        )

    monkeypatch.setattr(srcdir, "_run", record_run)

    tree = srcdir._kitty_remote_tree()

    assert tree == [{"session_name": "broker-backoff"}]
    assert commands == [
        (
            ["kitten", "@", "--to", "unix:/tmp/kitty-test", "ls"],
            {"check": False},
        )
    ]


@pytest.mark.parametrize(
    "returncode, output",
    [(1, "[]"), (0, "not json"), (0, '{"session_name": "wrong shape"}')],
)
def test_kitty_remote_tree_degrades_to_none(monkeypatch, returncode, output):
    """Treat failed, undecodable, and unexpected Kitty output as unavailable."""
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(srcdir.shutil, "which", lambda command: "/usr/bin/kitten")
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: subprocess.CompletedProcess(
            arguments, returncode, output, ""
        ),
    )

    assert srcdir._kitty_remote_tree() is None


def test_close_kitty_session_uses_an_anchored_owner_match(monkeypatch):
    """Keep sibling srcdir tabs safe when closing every owned Kitty tab."""
    monkeypatch.setenv("KITTY_LISTEN_ON", "unix:/tmp/kitty-test")
    monkeypatch.setattr(srcdir.shutil, "which", lambda command: "/usr/bin/kitten")
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments)
        or subprocess.CompletedProcess(arguments, 0, "", ""),
    )
    destination = Path("/srcdirs/auth[1]")

    srcdir._close_kitty_session(destination)

    assert commands == [
        [
            "kitten",
            "@",
            "--to",
            "unix:/tmp/kitty-test",
            "close-tab",
            "--match",
            r"var:srcdir=^/srcdirs/auth\[1\]$",
        ]
    ]
    owner_pattern = commands[0][-1].split("=", 1)[1]
    assert re.search(owner_pattern, str(destination))
    assert not re.search(owner_pattern, "/srcdirs/auth[1]-audit")


def test_srcdir_rename_moves_generated_kitty_session(tmp_path, monkeypatch):
    """Retarget the generated Kitty session when its srcdir is renamed."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    assert create_result.exit_code == 0, create_result.output
    source = srcdir_root / "eos-egress"
    destination = srcdir_root / "gitlab-groups"
    marker = json.loads((source / srcdir.SRCDIR_MARKER).read_text())
    old_session_path = srcdir._kitty_session_path("eos-egress")
    srcdir._write_kitty_session(old_session_path, source, ["/bin/zsh", "-i"])
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(srcdir, "_list_kitty_sessions", lambda: {str(source)})
    closed = []
    monkeypatch.setattr(
        srcdir, "_close_kitty_session", lambda managed: closed.append(managed)
    )

    result = runner.invoke(
        reana_dev,
        ["srcdir-rename", "eos-egress", "gitlab-groups", "--kill-kitty"],
    )

    assert result.exit_code == 0, result.output
    new_session_path = srcdir._kitty_session_path("gitlab-groups")
    assert closed == [source]
    assert not old_session_path.exists()
    assert new_session_path.is_file()
    contents = new_session_path.read_text()
    assert srcdir._kitty_session_owner(contents) == str(destination)
    assert str(source) not in shlex.split(contents.splitlines()[2][len("launch ") :])
    assert str(destination) in shlex.split(contents.splitlines()[2][len("launch ") :])
    updated_marker = json.loads((destination / srcdir.SRCDIR_MARKER).read_text())
    assert updated_marker["kitty_session"] == str(new_session_path)
    assert marker["kitty_session"] == str(old_session_path)


def test_srcdir_rename_warns_when_kitty_state_is_unavailable(tmp_path, monkeypatch):
    """Make the skipped live-session guard visible outside Kitty."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "eos-egress")
    assert create_result.exit_code == 0, create_result.output
    source = srcdir_root / "eos-egress"
    srcdir._write_kitty_session(
        srcdir._kitty_session_path("eos-egress"), source, ["/bin/zsh", "-i"]
    )
    marker_path = source / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["kitty_session"] = str(srcdir._kitty_session_path("eos-egress"))
    srcdir._write_json(marker_path, marker)
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(srcdir, "_list_kitty_sessions", lambda: None)

    result = runner.invoke(reana_dev, ["srcdir-rename", "eos-egress", "gitlab-groups"])

    assert result.exit_code == 0, result.output
    assert "Cannot verify whether the Kitty session is running" in result.output
    assert (srcdir_root / "gitlab-groups").is_dir()


def test_srcdir_delete_closes_kitty_and_removes_generated_session(
    tmp_path, monkeypatch
):
    """Clean up Kitty state when explicitly tearing down its srcdir."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    session_path = srcdir._kitty_session_path("broker-backoff")
    srcdir._write_kitty_session(session_path, destination, ["/bin/zsh", "-i"])
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(srcdir, "_list_kitty_sessions", lambda: {str(destination)})
    monkeypatch.setattr(srcdir, "_trash_directory", lambda: tmp_path / "Trash")
    closed = []
    monkeypatch.setattr(
        srcdir, "_close_kitty_session", lambda managed: closed.append(managed)
    )

    result = runner.invoke(
        reana_dev,
        [
            "srcdir-delete",
            "broker-backoff",
            "--kill-kitty",
            "--no-audit",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert closed == [destination]
    assert not session_path.exists()
    assert not destination.exists()


def test_srcdir_delete_warns_when_kitty_state_is_unavailable(tmp_path, monkeypatch):
    """Make the skipped live-session guard visible before teardown."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    session_path = srcdir._kitty_session_path("broker-backoff")
    srcdir._write_kitty_session(session_path, destination, ["/bin/zsh", "-i"])
    marker_path = destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["kitty_session"] = str(session_path)
    srcdir._write_json(marker_path, marker)
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    monkeypatch.setattr(srcdir, "_list_kitty_sessions", lambda: None)
    monkeypatch.setattr(srcdir, "_trash_directory", lambda: tmp_path / "Trash")

    result = runner.invoke(
        reana_dev,
        ["srcdir-delete", "broker-backoff", "--no-audit", "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert "Cannot verify whether the Kitty session is running" in result.output
    assert not destination.exists()


def test_srcdir_delete_refuses_to_run_from_inside_target(tmp_path, monkeypatch):
    """Avoid leaving the invoking shell in a deleted directory."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    destination = srcdir_root / "broker-backoff"
    monkeypatch.chdir(destination / "reana-server")

    result = runner.invoke(
        reana_dev,
        ["srcdir-delete", "broker-backoff", "--no-audit", "--yes"],
    )

    assert result.exit_code != 0
    assert "while working inside it" in result.output
    assert destination.is_dir()


def test_tmux_session_name_disambiguates_collisions():
    """Give punctuation-equivalent task names distinct Tmux targets."""
    existing = {"auth-alignment": "auth.alignment"}
    session_name = srcdir._tmux_session_name("auth:alignment", existing)
    assert session_name.startswith("auth-alignment-")


def test_harmonise_tmux_session_updates_stopped_legacy_marker(tmp_path, monkeypatch):
    """Migrate a stopped legacy session without recreating the srcdir."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    result = _create_srcdir(CliRunner(), monkeypatch, source_root, "auth-alignment")
    assert result.exit_code == 0, result.output
    destination = srcdir_root / "auth-alignment"
    marker_path = destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["tmux_session"] = "reana-auth-alignment"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    session_name, session_id = srcdir._harmonise_tmux_session(destination, marker, {})

    assert session_name == "auth-alignment"
    assert session_id is None
    assert json.loads(marker_path.read_text())["tmux_session"] == session_name


def test_harmonise_tmux_session_disambiguates_taken_target(tmp_path, monkeypatch):
    """Move a legacy owned session to a free name when its target is taken."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    result = _create_srcdir(CliRunner(), monkeypatch, source_root, "auth-alignment")
    assert result.exit_code == 0, result.output
    destination = srcdir_root / "auth-alignment"
    marker_path = destination / srcdir.SRCDIR_MARKER
    marker = json.loads(marker_path.read_text())
    marker["tmux_session"] = "reana-auth-alignment"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments),
    )

    session_name, session_id = srcdir._harmonise_tmux_session(
        destination,
        marker,
        {
            "reana-auth-alignment": ("$8", None, str(destination)),
            "auth-alignment": ("$9", None, "/private/tmp"),
        },
    )

    assert session_name.startswith("auth-alignment-")
    assert session_id == "$8"
    assert ["tmux", "rename-session", "-t", "$8", session_name] in commands
    assert not any("$9" in command for command in commands)


def test_mise_local_config_selects_local_virtual_environment(tmp_path):
    """Generate the mise override used throughout a managed srcdir."""
    destination = tmp_path / "flaky-fixtures"
    destination.mkdir()
    config = srcdir._write_mise_config(destination)
    contents = config.read_text()
    assert 'path = ".venv"' in contents
    assert "create = true" in contents
    assert 'uv_create_args = ["--seed", "--prompt", ' '"flaky-fixtures"]' in contents
    assert 'python_create_args = ["--prompt", ' '"flaky-fixtures"]' in contents
    assert contents.startswith(srcdir.MISE_LOCAL_CONFIG_HEADER)


def test_mise_local_config_supports_unicode_environment_name(tmp_path):
    """Generate valid TOML for srcdir names outside the basic multilingual plane."""
    destination = tmp_path / "release-rave-🎉"
    destination.mkdir()

    contents = srcdir._write_mise_config(destination).read_text()
    configuration = tomllib.loads(contents)

    virtual_environment = configuration["env"]["_"]["python"]["venv"]
    assert virtual_environment["python_create_args"][-1] == destination.name
    assert virtual_environment["uv_create_args"][-1] == destination.name


def test_managed_environment_installs_release_tools(tmp_path, monkeypatch):
    """Install reana-dev with its release extra in a managed environment."""
    destination = tmp_path / "flaky-fixtures"
    commands = []
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments),
    )

    srcdir._install_reana_dev(destination)

    assert commands == [
        [
            "mise",
            "exec",
            "-C",
            str(destination),
            "--",
            "python",
            "-m",
            "pip",
            "install",
            "--editable",
            f"{destination / 'reana'}[release]",
        ]
    ]


def test_workon_refreshes_stale_generated_mise_environment(tmp_path, monkeypatch):
    """Rebuild an existing environment after refreshing its mise override."""
    destination = tmp_path / "flaky-fixtures"
    config = destination / srcdir.MISE_LOCAL_CONFIG
    config.parent.mkdir()
    config.write_text(
        srcdir.MISE_LOCAL_CONFIG_LEGACY_HEADERS[0]
        + "[env]\n"
        + '_.python.venv = { path = ".venv", create = true, '
        + 'uv_create_args = ["--seed"] }\n',
        encoding="utf-8",
    )
    reana_dev = destination / ".venv" / "bin" / "reana-dev"
    reana_dev.parent.mkdir(parents=True)
    reana_dev.write_text(
        f"#!{destination / '.venv' / 'bin' / 'python'}\n",
        encoding="utf-8",
    )
    discarded = []
    commands = []
    monkeypatch.setattr(srcdir.shutil, "which", lambda command: "/usr/bin/mise")
    monkeypatch.setattr(
        srcdir,
        "_discard_mise_environment",
        lambda managed: discarded.append(managed) or True,
    )
    monkeypatch.setattr(
        srcdir,
        "_run",
        lambda arguments, **kwargs: commands.append(arguments),
    )

    srcdir._ensure_mise_environment(destination, {"python_environment": "mise"})

    assert discarded == [destination]
    refreshed_config = config.read_text()
    assert refreshed_config.startswith(srcdir.MISE_LOCAL_CONFIG_HEADER)
    assert '"--prompt", "flaky-fixtures"' in refreshed_config
    assert any("[release]" in argument for command in commands for argument in command)


def test_srcdir_help_marks_options_as_optional():
    """Describe srcdir command options as optional overrides and actions."""
    runner = CliRunner()
    expected_counts = {
        "srcdir-create": 3,
        "srcdir-workon": 4,
        "srcdir-rename": 3,
        "srcdir-list": 1,
        "srcdir-delete": 5,
    }

    for command, expected_count in expected_counts.items():
        result = runner.invoke(reana_dev, [command, "--help"])
        assert result.exit_code == 0, result.output
        assert result.output.count("[optional") == expected_count

    workon_help = runner.invoke(reana_dev, ["srcdir-workon", "--help"])
    assert "-t, --tmux" in workon_help.output
    assert "-k, --kitty" in workon_help.output
    assert "--plain, --no-kitty, --no-tmux" in workon_help.output
    assert "--use-tmux" not in workon_help.output
    compact_workon_help = " ".join(workon_help.output.split())
    assert "using Kitty or Tmux when already inside either" in compact_workon_help
    assert "Tmux takes precedence" in compact_workon_help
    create_help = runner.invoke(reana_dev, ["srcdir-create", "--help"])
    assert "names that differ early" in " ".join(create_help.output.split())
    rename_help = runner.invoke(reana_dev, ["srcdir-rename", "--help"])
    assert "OLD_NAME NEW_NAME" in rename_help.output
    delete_help = runner.invoke(reana_dev, ["srcdir-delete", "--help"])
    assert "--audit / --no-audit" in delete_help.output
    assert "-y, --yes" in delete_help.output
    assert "--force" not in delete_help.output


def test_main_help_shows_realistic_srcdir_review_flow():
    """Show a concise authentication review workflow in top-level help."""
    result = CliRunner().invoke(reana_dev, ["--help"])

    assert result.exit_code == 0, result.output
    assert "reana-dev srcdir-create auth-audit" in result.output
    assert "reana-dev srcdir-workon auth-audit" in result.output
    assert "reana-dev git-checkout-pr -i reana 977 --pull --reset" in result.output
