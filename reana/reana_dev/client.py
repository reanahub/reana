# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2022, 2023, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s command line client commands."""

import os
import sys

import click

from reana.config import REPO_LIST_CLIENT
from reana.reana_dev.utils import get_srcdir, run_command


@click.group()
def client_commands():
    """Client commands group."""


@client_commands.command(name="client-install")
def client_install():  # noqa: D301
    """Install latest REANA client and its dependencies.

    All components are installed in a single pip invocation so that
    pip can resolve version constraints from all local source
    directories together, avoiding conflicts when local branches
    have different dependency pins than published PyPI versions.
    """
    paths = []
    for component in REPO_LIST_CLIENT:
        srcdir = get_srcdir(component)
        if not os.path.isdir(srcdir):
            click.secho(
                f"[ERROR] Expected client component '{component}' is not "
                f"checked out at {srcdir}.",
                fg="red",
            )
            sys.exit(1)
        if os.path.exists(os.path.join(srcdir, "setup.py")) or os.path.exists(
            os.path.join(srcdir, "pyproject.toml")
        ):
            paths.append(srcdir)
    if paths:
        cmd = "pip install --upgrade " + " ".join(paths)
        run_command(cmd, "reana")
    run_command("pip check", "reana")


@client_commands.command(name="client-uninstall")
def client_uninstall():  # noqa: D301
    """Uninstall REANA client and its dependencies."""
    cmd = "pip uninstall -y " + " ".join(REPO_LIST_CLIENT)
    run_command(cmd, "reana")
    run_command("pip check", "reana")


@client_commands.command(name="client-setup-environment")
@click.option("--server-hostname", help="Set customized REANA Server hostname.")
def client_setup_environment(server_hostname):  # noqa: D301
    """Display commands to set up shell environment for local cluster.

    Display commands how to set up REANA_SERVER_URL suitable for current local
    REANA cluster deployment. The output should be passed to eval.
    """
    click.echo(
        "export REANA_SERVER_URL={}".format(
            server_hostname or "https://localhost:30443"
        )
    )


client_commands_list = list(client_commands.commands.values())
