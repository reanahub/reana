# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s Helm commands."""

import os
import re
import sys

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
    """Upgrade REANA Helm dependencies."""

    def _update_values_yaml(new_docker_images):
        """Update all images in ``values.yaml``, skipping the ones up to date."""
        values_yaml_relative_path = "helm/reana/values.yaml"
        values_yaml_abs_path = os.path.join(
            get_srcdir("reana"), values_yaml_relative_path
        )
        values_yaml = ""

        with open(values_yaml_abs_path) as f:
            values_yaml = f.read()
            for docker_image in new_docker_images:
                image_name, _ = docker_image.split(":")
                if image_name in values_yaml:
                    values_yaml = re.sub(
                        f"{image_name}:.*", lambda _: docker_image, values_yaml, count=1
                    )

        with open(values_yaml_abs_path, "w") as f:
            f.write(values_yaml)

        display_message(
            f"{values_yaml_relative_path} successfully updated.", component="reana"
        )

    remaining_docker_releases = []
    new_docker_images = []
    for component in REPO_LIST_CLUSTER:
        if not is_component_dockerised(component):
            continue
        if not git_is_current_version_tagged(component):
            remaining_docker_releases.append(component)
        else:
            new_docker_images.append(f"{user}/{component}:{get_docker_tag(component)}")

    if remaining_docker_releases:
        line_by_line_missing_releases = "\n".join(remaining_docker_releases)
        click.secho(
            "The following components are missing to be released:\n"
            f"{line_by_line_missing_releases}",
            fg="red",
        )
        sys.exit(1)

    _update_values_yaml(new_docker_images)
    ctx.invoke(git_diff, component=["reana"])
    if push:
        git_push_to_origin(["reana"])


helm_commands_list = list(helm_commands.commands.values())
