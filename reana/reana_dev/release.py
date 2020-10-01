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
import semver

from reana.reana_dev.docker import docker_push
from reana.reana_dev.git import (
    git_clean,
    git_is_current_version_tagged,
    is_last_commit_release_commit,
)
from reana.reana_dev.utils import (
    display_message,
    fetch_latest_pypi_version,
    get_current_component_version_from_source_files,
    get_docker_tag,
    is_component_dockerised,
    run_command,
    select_components,
)


def is_component_releasable(component, exit_code=False, display=False):
    """Determine whether a component is releasable.

    Last commit should be a release commit and the new version should be git tagged.

    :param component: Component to determine whether if it is releasable or not.
    :param exit_code: Whether the program should exit with error exit code if
        the condition is not met.
    :param display: Whether error messages providing instructions on how to fix
        the problem should be displayed to stdout.

    :type component: str
    :type exit_code: bool
    :type display: bool
    :rtype: bool
    """
    is_releasable = True
    error_message = ""
    if not is_last_commit_release_commit(component):
        error_message = "The last commit is not a release commit. Please use `reana-dev git-create-release-commit`."
        is_releasable = False
    if not git_is_current_version_tagged(component):
        error_message = (
            "The current version is not tagged. Please use `reana-dev git-tag`."
        )
        is_releasable = False

    if error_message and display:
        display_message(error_message, component)
    if not is_releasable and exit_code:
        sys.exit(1)

    return is_releasable


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
@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option("--image-name", help="Should the component have a custom image name?")
@release_commands.command(name="release-docker")
@click.pass_context
def release_docker(ctx, component, user, image_name):  # noqa: D301
    """Release a component on Docker Hub.

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
    cannot_release_on_dockerhub = []
    for component_ in components:
        if not is_component_dockerised(component_):
            cannot_release_on_dockerhub.append(component_)
        is_component_releasable(component_, exit_code=True, display=True)
        full_image_name = f"{user}/{image_name or component_}"
        docker_tag = get_docker_tag(component_)
        run_command(
            f"docker tag {full_image_name}:latest {full_image_name}:{docker_tag}",
            component_,
        )
        ctx.invoke(docker_push, component=[component_], tag=docker_tag, user=user)

    if cannot_release_on_dockerhub:
        click.secho(
            "The following components are not releasable on DockerHub: "
            f"{', '.join(cannot_release_on_dockerhub)}",
            fg="red",
        )
        sys.exit(1)


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
        is_component_releasable(component, exit_code=True, display=True)
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
