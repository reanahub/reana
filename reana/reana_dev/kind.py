# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2023, 2025, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s kind commands."""

import os
import tempfile

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


def _kind_load_image(image, nodes, component):
    """Load a Docker image into the local kind cluster.

    Goes via a platform-pinned ``docker image save`` plus
    ``kind load image-archive``, rather than ``kind load docker-image``.
    The latter shells out to ``docker save`` without a platform filter,
    which on daemons that use the containerd image store (default on
    Docker Desktop and progressively rolling out on Docker CE) exports
    the full multi-arch index even when only one platform was pulled.
    The subsequent ``ctr import --all-platforms --digests`` inside the
    kind node then aborts on the first sibling-manifest digest whose
    content is not in the archive. Saving with ``--platform`` produces
    a single-manifest tarball that imports cleanly.

    The platform is read from the local image record (not from the
    daemon platform), because single-platform upstream images may have
    been pulled under emulation — e.g. an amd64-only image on an arm64
    daemon. ``docker image save --platform <daemon>`` would then fail
    with ``no suitable export target found``.

    This is a workaround for a Kind issue tracked upstream at
    https://github.com/kubernetes-sigs/kind/issues/3795.
    """
    platform = run_command(
        "docker image inspect --format '{{.Os}}/{{.Architecture}}' " + image,
        display=False,
        return_output=True,
    )
    fd, archive = tempfile.mkstemp(suffix=".tar", prefix="reana-kind-load-")
    os.close(fd)
    try:
        run_command(
            "docker image save --platform {0} -o {1} {2}".format(
                platform, archive, image
            ),
            component,
        )
        cmd = "kind load image-archive {0}".format(archive)
        if nodes:
            cmd = "{0} --nodes {1}".format(cmd, ",".join(nodes))
        run_command(cmd, component)
    finally:
        try:
            os.unlink(archive)
        except FileNotFoundError:
            pass


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option("--tag", "-t", default="latest", help="Image tag [latest]")
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
def kind_load_docker_image(
    user, tag, component, node, exclude_components
):  # noqa: D301
    """Load Docker images to the cluster.

    \b
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. [default=latest]
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
    :type tag: str
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    for component in select_components(component, exclude_components):
        if component in DOCKER_PREFETCH_IMAGES:
            for image in DOCKER_PREFETCH_IMAGES[component]:
                _kind_load_image(image, node, component)
        elif is_component_dockerised(component):
            # Always pass an explicit tag: with Docker's containerd
            # image store, a bare repo name can match multiple tagged
            # images (e.g. a fresh local build plus older `:0.9.x`
            # pulls), and `docker image save` may pick the wrong one.
            image = "docker.io/{0}/{1}:{2}".format(user, component, tag)
            _kind_load_image(image, node, component)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)


kind_commands_list = list(kind_commands.commands.values())
