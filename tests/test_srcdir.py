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
import shutil
import subprocess
import tomllib

import click
import pytest
from click.testing import CliRunner

from reana.reana_dev import srcdir
from reana.reana_dev.cli import reana_dev


def test_srcdir_output_uses_homebrew_style_visual_hierarchy():
    """Use blue headings, green success markers, and left-aligned details."""

    @click.command()
    def render_output():
        srcdir._echo_heading("Auditing srcdir test-bar")
        srcdir._echo_field("Location", "/tmp/test-bar")
        srcdir._echo_success("Teardown audit found no unretained work")
        srcdir._echo_warning("Teardown audit found unretained work")
        srcdir._echo_command("reana-dev srcdir-workon -t test-bar")

    result = CliRunner().invoke(render_output, color=True)

    assert result.exit_code == 0, result.output
    assert result.output == (
        "\x1b[34m==>\x1b[0m \x1b[1mAuditing srcdir test-bar\x1b[0m\n"
        "Location     /tmp/test-bar\n"
        "\x1b[32m✓\x1b[0m Teardown audit found no unretained work\n"
        "\x1b[33mWarning:\x1b[0m Teardown audit found unretained work\n"
        "\x1b[36m$ \x1b[0mreana-dev srcdir-workon -t test-bar\n"
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
        "$ reana-dev srcdir-workon -t auth-alignment\n"
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
    monkeypatch.setenv("SHELL", "/bin/zsh")
    original_which = srcdir.shutil.which
    monkeypatch.setattr(
        srcdir.shutil,
        "which",
        lambda command: (
            "/bin/zsh" if command == "/bin/zsh" else original_which(command)
        ),
    )
    commands = []

    def record_run(arguments, destination, environment):
        commands.append((arguments, destination, environment))

    monkeypatch.setattr(srcdir, "_run_interactive", record_run)
    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])

    assert result.exit_code == 0, result.output
    assert len(commands) == 1
    arguments, destination, environment = commands[0]
    assert arguments == ["/bin/zsh", "-i"]
    assert destination == srcdir_root / "broker-backoff"
    assert environment[srcdir.REANA_SRCDIR_ENV] == str(destination)
    assert (
        "==> Opening shell for srcdir broker-backoff\n"
        f"{'Location':<13}{destination}\n"
        "\n"
        "Exit the shell to return."
    ) in result.output


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
    arguments, shell_destination, environment = commands[0]
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
    assert environment[srcdir.REANA_SRCDIR_ENV] == str(destination)


def test_srcdir_workon_refuses_nested_shell(tmp_path, monkeypatch):
    """Refuse to stack managed srcdir shells invisibly."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "broker-backoff")
    assert create_result.exit_code == 0, create_result.output
    monkeypatch.chdir(srcdir_root)
    monkeypatch.setenv(srcdir.REANA_SRCDIR_ENV, "/existing/srcdir")

    result = runner.invoke(reana_dev, ["srcdir-workon", "broker-backoff"])

    assert result.exit_code != 0
    assert "Already working in the srcdir shell /existing/srcdir" in result.output
    assert "Exit it before opening" in result.output


def test_srcdir_workon_creates_explicit_tmux_session(tmp_path, monkeypatch):
    """Address an explicitly requested tmux session by its stable ID."""
    source_root = _create_source_collection(tmp_path)
    srcdir_root = _srcdir_root(source_root)
    runner = CliRunner()
    create_result = _create_srcdir(runner, monkeypatch, source_root, "auth.alignment")
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
    monkeypatch.setattr(srcdir, "_list_tmux_sessions", lambda: {})
    commands = []

    def record_run(arguments, cwd=None, check=True):
        commands.append(arguments)
        stdout = "$7\n" if arguments[:2] == ["tmux", "new-session"] else ""
        return subprocess.CompletedProcess(arguments, 0, stdout, "")

    monkeypatch.setattr(srcdir, "_run", record_run)
    result = runner.invoke(
        reana_dev,
        [
            "srcdir-workon",
            "auth.alignment",
            "-t",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "==> Creating tmux session auth-alignment" in result.output
    assert "==> Entering tmux session auth-alignment" in result.output
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
        "env REANA_SRCDIR=" f"{srcdir_root / 'auth.alignment'} /bin/sh -i",
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
        ["srcdir-workon", "auth-alignment", "--tmux"],
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
    """Report a same-named unmarked tmux session as a conflict."""
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
    assert (
        "==> Next steps:\n$ reana-dev srcdir-workon -t gitlab-groups"
    ) in result.output


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
    """Require explicit permission before stopping a srcdir's tmux session."""
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
    """Disambiguate a renamed srcdir from a live foreign tmux session."""
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
    """Allocate a usable tmux name when the exact global name is taken."""
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
    """Parse marked and unmarked tmux sessions with their initial paths."""
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


def test_tmux_session_name_disambiguates_collisions():
    """Give punctuation-equivalent task names distinct tmux targets."""
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
        "srcdir-workon": 2,
        "srcdir-rename": 2,
        "srcdir-list": 1,
        "srcdir-delete": 4,
    }

    for command, expected_count in expected_counts.items():
        result = runner.invoke(reana_dev, [command, "--help"])
        assert result.exit_code == 0, result.output
        assert result.output.count("[optional") == expected_count

    workon_help = runner.invoke(reana_dev, ["srcdir-workon", "--help"])
    assert "-t, --tmux" in workon_help.output
    assert "--create-tmux-session" not in workon_help.output
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
    assert "reana-dev srcdir-workon -t auth-audit" in result.output
    assert "reana-dev git-checkout-pr -i reana 977 --pull --reset" in result.output
