# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s release commands."""

import json
import os
import sys
import tempfile
from shutil import which
from time import sleep

import click

from reana.reana_dev.docker import docker_push
from reana.reana_dev.git import (
    get_current_commit,
    git_clean,
    git_is_current_version_tagged,
    is_last_commit_release_commit,
)
from reana.reana_dev.utils import (
    display_message,
    fetch_latest_pypi_version,
    get_current_component_version_from_source_files,
    get_docker_tag,
    get_srcdir,
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
@click.option(
    "--registry",
    "-r",
    default="docker.io",
    help="Registry to use in the image tag [default=docker.io]",
)
@click.option(
    "--platform",
    multiple=True,
    help="Platforms for multi-arch images [default=current architecture]",
)
@click.option("--tags-only", is_flag=True, help="Only print the Docker image tags")
@release_commands.command(name="release-docker")
@click.pass_context
def release_docker(
    ctx, component, user, image_name, registry, platform, tags_only
):  # noqa: D301
    """Release a component on a Docker image registry.

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
    :param user: Organisation or user name. [default=reanahub]
    :param image_name: Custom name of the local Docker image.
    :param registry: Registry to use in the image tag. [default=docker.io]
    :param platform: Platforms for multi-arch images. [default=current architecture]
    :param tags_only: Only print the Docker image tags.
    :type component: str
    :type user: str
    :type image_name: str
    :type registry: str
    :type platform: list
    :type tags_only: bool
    """
    components = select_components(component)

    if image_name and len(components) > 1:
        click.secho("Cannot use custom image name with multiple components.", fg="red")
        sys.exit(1)

    is_multi_arch = len(platform) > 1
    if is_multi_arch and not tags_only:
        # check whether podman is installed
        run_command("podman version", display=False, return_output=True)
    # platforms are in the format OS/ARCH[/VARIANT], we are only interested in ARCH
    expected_arch = sorted([p.split("/")[1] for p in platform])

    cannot_release_on_dockerhub = []
    for component_ in components:
        if not is_component_dockerised(component_):
            cannot_release_on_dockerhub.append(component_)
        is_component_releasable(component_, exit_code=True, display=True)
        # source_image_name is the name used by docker-build
        source_image_name = f"docker.io/{user}/{component_}"
        target_image_name = f"{registry}/{user}/{image_name or component_}"
        docker_tag = get_docker_tag(component_)

        if tags_only:
            click.echo(f"{target_image_name}:{docker_tag}")
            continue

        if is_multi_arch:
            manifest = json.loads(
                run_command(
                    f"podman manifest inspect {source_image_name}:latest",
                    component=component_,
                    return_output=True,
                )
            )
            manifest_arch = sorted(
                [m["platform"]["architecture"] for m in manifest["manifests"]]
            )
            if manifest_arch != expected_arch:
                display_message(
                    f"Expected multi-arch image {source_image_name} with {expected_arch} variants, "
                    f"found {manifest_arch}.",
                    component=component_,
                )
                sys.exit(1)
            run_command(
                f"podman tag {source_image_name}:latest {target_image_name}:{docker_tag}",
                component_,
            )
            run_command(
                f"podman manifest push --all {target_image_name}:{docker_tag} "
                f"docker://{target_image_name}:{docker_tag}",
                component_,
            )
        else:
            run_command(
                f"docker tag {source_image_name}:latest {target_image_name}:{docker_tag}",
                component_,
            )
            ctx.invoke(
                docker_push,
                component=[component_],
                registry=registry,
                user=user,
                image_name=image_name,
                tag=docker_tag,
            )

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


@click.option(
    "--user", "-u", default="reanahub", help="DockerHub user name [default=reanahub]"
)
@click.option(
    "--cr-commit",
    is_flag=True,
    default=False,
    help="Specify target commit for release? [default=False]",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Display the command without executing it. [default=False]",
)
@release_commands.command(name="release-helm")
@click.pass_context
def release_helm(ctx, user: str, cr_commit: bool, dry_run: bool) -> None:  # noqa: D301
    """Release REANA as a Helm chart.

    Note that ``--cr-commit`` command line option should be used for releasing
    non-master branches such as ``maint-0.9`` or ``next`` to specify the correct
    target commit.
    """
    component = "reana"
    version = get_current_component_version_from_source_files(component)
    is_chart_releaser_installed = which("cr")
    github_pages_branch = "gh-pages"
    package_path = ".cr-release-packages"
    index_path = ".cr-index"
    repository = f"https://{user}.github.io/{component}"

    is_component_releasable(component, exit_code=True, display=True)
    if not is_chart_releaser_installed:
        click.secho(
            "Please install chart-releaser to be able to do a Helm release",
            fg="red",
        )
        sys.exit(1)

    if not os.getenv("CR_TOKEN"):
        click.secho(
            "Please provide your GitHub token as CR_TOKEN environment variable",
            fg="red",
        )
        sys.exit(1)

    commit = ""
    if cr_commit:
        current_commit_sha = get_current_commit(get_srcdir(component)).split(" ")[0]
        commit = f"--commit {current_commit_sha}"

    for cmd in [
        f"rm -rf {package_path}",
        f"mkdir {package_path}",
        f"rm -rf {index_path}",
        f"mkdir {index_path}",
        f"helm package helm/reana --destination {package_path} --dependency-update",
        f"cr upload -o {user} -r {component} --release-name-template '{{{{ .Version }}}}' {commit}",
        f"cr index -o {user} -r {component} -c {repository} --release-name-template '{{{{ .Version }}}}'",
    ]:
        run_command(cmd, component, dry_run=dry_run)

    with tempfile.TemporaryDirectory() as gh_pages_worktree:
        run_command(
            f"git worktree add '{gh_pages_worktree}' gh-pages && "
            f"cd {gh_pages_worktree} && "
            f"cp -f {get_srcdir(component) + os.sep + index_path}/index.yaml {gh_pages_worktree}/index.yaml && "
            f"git add index.yaml && "
            f"git commit -m 'index.yaml: {version}' && "
            f"git push origin {github_pages_branch} && "
            f"cd - && "
            f"git worktree remove '{gh_pages_worktree}'",
            dry_run=dry_run,
        )


release_commands_list = list(release_commands.commands.values())
