# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s kind commands."""

import click

from reana.config import DOCKER_PREFETCH_IMAGES
from reana.reana_dev.utils import (
    display_message,
    is_component_dockerised,
    run_command,
    select_components,
)


@click.group()
def kind_commands():
    """Kind commands group."""


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER]",
)
@click.option(
    "--node",
    "-n",
    multiple=True,
    help="Which nodes to load the images to? [`kubectl get nodes` to see available ones]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude from build? [c1,c2,c3]",
)
@kind_commands.command(name="kind-load-docker-image")
def kind_load_docker_image(user, component, node, exclude_components):  # noqa: D301
    """Load Docker images to the cluster.

    \b
    :param user: DockerHub organisation or user name. [default=reanahub]
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
    :param exclude_components: List of components to exclude from the build.
    :type user: str
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    for component in select_components(component, exclude_components):
        if component in DOCKER_PREFETCH_IMAGES:
            for image in DOCKER_PREFETCH_IMAGES[component]:
                cmd = "kind load docker-image {0}".format(image)
                if node:
                    cmd = f"{cmd} --nodes {','.join(node)}"
                run_command(cmd, component)
        elif is_component_dockerised(component):
            cmd = "kind load docker-image {0}/{1}".format(user, component)
            if node:
                cmd = f"{cmd} --nodes {','.join(node)}"
            run_command(cmd, component)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)


kind_commands_list = list(kind_commands.commands.values())
