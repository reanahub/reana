# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2023 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s Docker commands."""

import click

from reana.config import DOCKER_PREFETCH_IMAGES
from reana.reana_dev import utils
from reana.reana_dev.utils import (
    display_message,
    get_docker_tag,
    is_component_dockerised,
    run_command,
    execute_parallel,
    select_components,
)


@click.group()
def docker_commands():
    """Docker commands group."""


def _run_command_prefix_output(cmd, component):
    """Run given command, showing the component's name before each output line.

    :param cmd: Command to be executed.
    :param component: Name of the REANA component.
    """
    output = run_command(cmd, component, return_output=True)
    for line in output.splitlines():
        click.echo(click.style(f"[{component}] ", bold=True) + line)


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option(
    "--tag",
    "-t",
    default="latest",
    help="Image tag to generate. Default 'latest'. "
    "Use 'auto' to generate git-tag-based value such as "
    "'0.7.0-alpha.3'",
)
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude from build? [c1,c2,c3]",
)
@click.option(
    "--build-arg",
    "-b",
    multiple=True,
    help="Any build arguments? (e.g. `-b DEBUG=1`)",
)
@click.option("--no-cache", is_flag=True)
@click.option(
    "--output-component-versions",
    "-o",
    type=click.File("w"),
    help="Where to write the list of built image tags.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Suppress the build output and print image ID on success",
)
@click.option(
    "--parallel",
    "-p",
    default=1,
    type=click.IntRange(min=1),
    help="Number of docker images to build in parallel.",
)
@docker_commands.command(name="docker-build")
@click.pass_context
def docker_build(
    ctx,
    user,
    tag,
    component,
    build_arg,
    no_cache,
    output_component_versions,
    quiet,
    exclude_components,
    parallel,
):  # noqa: D301
    """Build REANA component images.

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
    :param exclude_components: List of components to exclude from the build.
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker image tag to generate. Default 'latest'.  Use 'auto' to
        generate git-tag-based value such as '0.7.0-alpha.3'.
    :param build_arg: Optional docker build argument. (e.g. DEBUG=1)
    :param no_cache: Flag instructing to avoid using cache. [default=False]
    :param output_component_versions: File where to write the built images
        tags. Useful when using `--tag auto` since every REANA component
        will have a different tag.
    :type component: str
    :type exclude_components: str
    :type user: str
    :type tag: str
    :type build_arg: str
    :type no_cache: bool
    :type output_component_versions: File
    :type quiet: bool
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    built_components_versions_tags = []

    # show the component's name before each output line of `docker build` if there
    # are multiple parallel builds at the same time, as in this case build logs
    # from different components are mixed together
    _run_command = run_command if parallel == 1 else _run_command_prefix_output

    commands = []
    for component in components:
        component_tag = tag
        if is_component_dockerised(component):
            cmd = "docker build"
            if tag == "auto":
                component_tag = get_docker_tag(component)
            for arg in build_arg:
                cmd += " --build-arg {0}".format(arg)
            if no_cache:
                cmd += " --no-cache"
            if quiet or parallel > 1:
                cmd += " --quiet"
            component_version_tag = "{0}/{1}:{2}".format(user, component, component_tag)
            cmd += " -t {0} .".format(component_version_tag)
            commands.append((_run_command, (cmd, component)))
            built_components_versions_tags.append(component_version_tag)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)

    execute_parallel(
        commands,
        processes=parallel,
        progress_callback=lambda status: display_message(
            f"{status.remaining}/{status.total} images remaining to be built "
            f"({status.cancelled} cancelled, {status.failed} failed)",
            component="reana",
        ),
    )

    if output_component_versions:
        output_component_versions.write(
            "\n".join(built_components_versions_tags) + "\n"
        )


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@docker_commands.command(name="docker-images")
def docker_images(user):  # noqa: D301
    """List REANA component images.

    :param user: DockerHub user name. [default=reanahub]
    :type user: str
    """
    cmd = "docker images | grep {0}".format(user)
    run_command(cmd)


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option("--tag", "-t", default="latest", help="Image tag [latest]")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER]",
)
@docker_commands.command(name="docker-rmi")
def docker_rmi(user, tag, component):  # noqa: D301
    """Remove REANA component images.

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
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. [default=latest]
    :type component: str
    :type user: str
    :type tag: str
    """
    components = select_components(component)
    for component in components:
        if is_component_dockerised(component):
            cmd = "docker rmi {0}/{1}:{2}".format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option(
    "--tag",
    "-t",
    default="latest",
    help="Image tag to push. Default 'latest'. "
    "Use 'auto' to push git-tag-based value such as "
    "'0.7.0-alpha.3'",
)
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER]",
)
@docker_commands.command(name="docker-push")
def docker_push(user, tag, component):  # noqa: D301
    """Push REANA component images to DockerHub.

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
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker image tag to push. Default 'latest'.  Use 'auto' to
        push git-tag-based value such as '0.7.0-alpha.3'.
    :param tag: Docker tag to use. [default=latest]
    :type component: str
    :type user: str
    :type tag: str
    """
    components = select_components(component)
    for component in components:
        component_tag = tag
        if is_component_dockerised(component):
            if tag == "auto":
                component_tag = get_docker_tag(component)
            cmd = "docker push {0}/{1}:{2}".format(user, component, component_tag)
            run_command(cmd, component)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option("--tag", "-t", default="latest", help="Image tag [latest]")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER|DEMO]",
)
@docker_commands.command(name="docker-pull")
def docker_pull(user, tag, component):  # noqa: D301
    """Pull REANA component images from DockerHub.

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
                         * (6) special value 'DEMO' that will expand to
                               cover all REANA demo example images;
                         * (7) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param user: DockerHub organisation or user name. [default=reanahub]
    :param tag: Docker tag to use. [default=latest]
    :type component: str
    :type user: str
    :type tag: str
    """
    components = select_components(component)
    for component in components:
        if component in DOCKER_PREFETCH_IMAGES:
            for image in DOCKER_PREFETCH_IMAGES[component]:
                cmd = "docker pull {0}".format(image)
                run_command(cmd, component)
        elif is_component_dockerised(component):
            cmd = "docker pull {0}/{1}:{2}".format(user, component, tag)
            run_command(cmd, component)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)


docker_commands_list = list(docker_commands.commands.values())
