# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Regression tests for git-upgrade-requirements command generation."""

import json
import os
import shlex
import subprocess
import sys
from unittest.mock import patch

import pytest

from reana.reana_dev.utils import upgrade_requirements


@pytest.mark.parametrize("offline_flag", ["", "--no-index "])
@pytest.mark.parametrize("upgrade_flag", ["", "-U ", "--upgrade "])
def test_upgrade_requirements_records_reusable_command(
    tmp_path, offline_flag, upgrade_flag
):
    """Both clean and affected headers support consecutive online upgrades."""
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"# pip-compile {offline_flag}{upgrade_flag}"
        "--output-file=requirements.txt setup.py\n"
    )

    for _ in range(2):
        with patch(
            "reana.reana_dev.utils.get_srcdir", return_value=str(tmp_path)
        ), patch("reana.reana_dev.utils.run_command") as run:
            assert upgrade_requirements("reana-server")

        command, component = run.call_args.args
        assert component == "reana-server"
        environment = command[command.index("--env") + 1]
        name, recorded_command = environment.split("=", 1)
        assert name == "CUSTOM_COMPILE_COMMAND"
        assert shlex.split(recorded_command) == [
            "pip-compile",
            "--annotation-style=line",
            "--output-file=requirements.txt",
            "setup.py",
        ]
        assert shlex.split(command[-1].split(" && ")[-1]) == [
            *shlex.split(recorded_command),
            "-U",
        ]
        # pip-tools records CUSTOM_COMPILE_COMMAND verbatim in its next header.
        requirements.write_text(f"# {recorded_command}\n")


def test_upgrade_requirements_preserves_quoted_options(tmp_path):
    """The container shell preserves custom options and literal source paths."""
    source_dir = tmp_path / "server's sources $(false)"
    source_dir.mkdir()
    options = [
        "--annotation-style",
        "split",
        "--extra=cwl",
        "--allow-unsafe",
        "--find-links",
        "wheel house",
        "--output-file=requirements.txt",
        "requirements' $(false).in",
    ]
    (source_dir / "requirements.txt").write_text(
        f"# {shlex.join(['pip-compile', '--no-index', *options])}\n"
    )
    with patch("reana.reana_dev.utils.get_srcdir", return_value=str(source_dir)), patch(
        "reana.reana_dev.utils.run_command"
    ) as run:
        assert upgrade_requirements("reana-server")

    command = run.call_args.args[0]
    assert command[command.index("-v") + 1] == f"{source_dir}:/code:z"
    name, recorded_command = command[command.index("--env") + 1].split("=", 1)
    assert shlex.split(recorded_command) == ["pip-compile", *options]

    # Exercise the real shell quoting without Docker, package installs or /code.
    capture = "import json, sys; print(json.dumps(sys.argv[1:]))"
    script = (
        "cd() { :; }\npip() { :; }\n"
        f"pip-compile() {{ {shlex.join([sys.executable, '-c', capture])} \"$@\"; }}\n"
        + command[-1]
    )
    result = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, name: recorded_command},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [*options, "-U"]
