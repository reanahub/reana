# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s Helm commands."""

import os
import re
import sys
from typing import List

import click

from reana.config import REPO_LIST_CLUSTER
from reana.reana_dev.git import (
    git_diff,
    git_is_current_version_tagged,
    git_push_to_origin,
)
from reana.reana_dev.utils import (
    display_message,
    get_docker_tag,
    get_srcdir,
    is_component_dockerised,
)


@click.group()
def helm_commands():
    """Helm commands group."""


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option(
    "--push",
    is_flag=True,
    default=False,
    help="Should the feature branch with the upgrade be pushed to origin?",
)
@helm_commands.command(name="helm-upgrade-components")
@click.pass_context
def helm_upgrade_components(ctx, user, push):  # noqa: D301
    """Upgrade REANA Helm dependencies.

    Checks if any docker releases are missed.
    If yes, exists with the error and lists missing components.
    If not, updates values.yaml and prefetch-images.sh with new docker images version
    """
    _check_if_missing_docker_releases()
    new_docker_images = _get_docker_releases(user)

    values_yaml_abs_path = os.path.join(get_srcdir("reana"), "helm/reana/values.yaml")
    _upgrade_docker_images(values_yaml_abs_path, new_docker_images)

    prefetch_script_abs_path = os.path.join(
        get_srcdir("reana"), "scripts/prefetch-images.sh"
    )
    _upgrade_docker_images(prefetch_script_abs_path, new_docker_images)

    ctx.invoke(git_diff, component=["reana"])
    if push:
        git_push_to_origin(["reana"])


def _get_docker_releases(dockerhub_user: str) -> List[str]:
    """Return released docker images (name + tag) of all components.

    Iterate over the components that provide Docker image and
    have a current version os source code tagged, extract docker images
    and return as a list
    """
    docker_images = []
    for component in REPO_LIST_CLUSTER:
        if is_component_dockerised(component) and git_is_current_version_tagged(
            component
        ):
            docker_images.append(
                f"{dockerhub_user}/{component}:{get_docker_tag(component)}"
            )

    return docker_images


def _check_if_missing_docker_releases() -> None:
    """Check if all dockerised components are released.

    If not, print those components and exit with status 1.
    """
    remaining_docker_releases = []
    for component in REPO_LIST_CLUSTER:
        if not is_component_dockerised(component):
            continue
        if not git_is_current_version_tagged(component):
            remaining_docker_releases.append(component)

    if remaining_docker_releases:
        line_by_line_missing_releases = "\n".join(remaining_docker_releases)
        click.secho(
            "The following components are missing to be released:\n"
            f"{line_by_line_missing_releases}",
            fg="red",
        )
        sys.exit(1)


def _upgrade_docker_images(file_path: str, new_docker_images: List[str]) -> None:
    """Upgrade docker images in the file_path.

    Read the content of the provided file_path,
    replace docker image strings in the content with the provided new docker images (name + tag),
    save the updated content back to the file_path
    """
    with open(file_path, "r") as f:
        file_content = f.read()

    file_content = _replace_docker_images(file_content, new_docker_images)

    with open(file_path, "w") as f:
        f.write(file_content)

    display_message(
        f"Docker images in {file_path} successfully updated.", component="reana"
    )


def _replace_docker_images(content: str, images: List[str]) -> str:
    """Replace docker images in the given string.

    Find the provided docker images in the given string
    by docker image name and replace it with the given images (name + tag).
    """
    for image in images:
        image_name, _ = image.split(":")
        if image_name in content:
            content = re.sub(f"{image_name}:\\S*", image, content, count=1)
    return content


helm_commands_list = list(helm_commands.commands.values())
