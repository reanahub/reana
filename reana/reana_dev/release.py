# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s release commands."""

import sys
from time import sleep

import click

from reana.reana_dev.git import (
    git_clean,
    git_is_current_version_tagged,
    is_last_commit_release_commit,
)
from reana.reana_dev.utils import (
    fetch_latest_pypi_version,
    get_current_component_version_from_source_files,
    run_command,
    select_components,
)


@click.group()
def release_commands():
    """Release commands group."""


@click.option(
    "--component",
    "-c",
    required=True,
    multiple=True,
    help="Which components? [name|CLUSTER]",
)
@click.option(
    "--timeout",
    required=True,
    type=int,
    default=90,
    help="How many seconds should we wait to confirm successful PyPI release?",
)
@release_commands.command(name="release-pypi")
@click.pass_context
def release_pypi(ctx, component, timeout):  # noqa: D301
    """Release a component on pypi.org.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-workflow-controller';
                         * (2) short component name such as 'r-w-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components [default];
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'DEMO' that will expand
                               to include several runable REANA demo examples;
                         * (7) special value 'ALL' that will expand to include
                               all REANA repositories.
    :type component: str
    """
    components = select_components(component)
    for component in components:
        if not is_last_commit_release_commit(component):
            click.secho(
                "The last commit is not a release commit. Please use `reana-dev git-create-release-commit`.",
                fg="red",
            )
            sys.exit(1)
        if not git_is_current_version_tagged(component):
            click.secho(
                "The current version is not tagged. Please use `reana-dev git-tag`.",
                fg="red",
            )
            sys.exit(1)
        ctx.invoke(git_clean, component=[component])

        for cmd in ["rm -rf dist", "python setup.py sdist", "twine upload ./dist/*"]:
            run_command(cmd, component)

        retry_interval = 15
        time_elapsed = 0
        while fetch_latest_pypi_version(
            component
        ) != get_current_component_version_from_source_files(component):
            sleep(retry_interval)
            time_elapsed += retry_interval
            if time_elapsed >= timeout:
                click.secho("Something went wrong with the PyPI release.", fg="red")
                sys.exit(1)

        click.secho(f"{component} successfully released on PyPI", fg="green")


release_commands_list = list(release_commands.commands.values())
