# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023, 2024, 2025, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s git commands."""

import datetime
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import click
import yaml

from reana.config import (
    COMPONENTS_USING_SHARED_MODULE_COMMONS,
    COMPONENTS_USING_SHARED_MODULE_DB,
    DOCKER_VERSION_FILE,
    GIT_DEFAULT_BASE_BRANCH,
    HELM_VERSION_FILE,
    JAVASCRIPT_VERSION_FILE,
    OPENAPI_VERSION_FILE,
    PYTHON_REQUIREMENTS_FILE,
    PYTHON_VERSION_FILE,
    RELEASE_COMMIT_REGEX,
    REPO_LIST_ALL,
    REPO_LIST_CLUSTER_INFRASTRUCTURE,
    REPO_LIST_CLUSTER_RUNTIME_BATCH,
    REPO_LIST_PYTHON_FIRST,
    REPO_LIST_PYTHON_REQUIREMENTS,
    REPO_LIST_SHARED,
)
from reana.reana_dev.utils import (
    bump_component_version,
    bump_pep440_version,
    bump_semver2_version,
    click_add_git_base_branch_option,
    display_message,
    exclude_components_from_selection,
    fetch_latest_pypi_version,
    get_component_version_files,
    get_current_component_version_from_source_files,
    get_srcdir,
    is_feature_branch,
    parse_pep440_version,
    run_command,
    select_components,
    translate_pep440_to_semver2,
    update_module_in_cluster_components,
    upgrade_requirements,
    validate_directory,
    get_commit_pr_suffix,
    find_standard_component_name,
)


def get_all_branches(srcdir):
    """Return all local and remote Git branch names in the given directory.

    :param srcdir: source code directory
    :type srcdir: str

    :return: checkout out branch in the component source code directory
    :rtype: str
    """
    return (
        subprocess.check_output(
            ["git", "branch", "-a"],
            cwd=srcdir,
            stderr=subprocess.DEVNULL,
        )
        .decode()
        .split()
    )


def remote_ref_exists(srcdir, branch):
    """Return whether ``refs/remotes/<branch>`` exists in the given repo.

    Cheaper than scanning ``git branch -a`` output: a single ``git show-ref``
    call with no shell pipeline.
    """
    return (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/{branch}"],
            cwd=srcdir,
        ).returncode
        == 0
    )


def branch_exists(component, branch):
    """Check whether a local branch exists on a given component.

    Uses ``git show-ref --verify --quiet refs/heads/<branch>`` rather than
    scanning ``git branch -a`` output — one cheap process, no shell, and no
    false positives on remote-tracking ref aliases (e.g. ``origin/master``
    appearing tokenised in ``remotes/origin/HEAD -> origin/master``).

    :param component: Component in which check whether the branch exists.
    :param branch: Name of the local branch.
    :return: Whether the branch exists in components git repo.
    :rtype: bool
    """
    return (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=get_srcdir(component),
        ).returncode
        == 0
    )


def get_current_branch(srcdir):
    """Return current Git branch name checked out in the given directory.

    Returns ``"HEAD"`` when the working tree is in a detached-HEAD state;
    callers in the ``git-status`` hot path detect that and skip the
    branch-comparison logic.

    :param srcdir: source code directory
    :type srcdir: str

    :return: checkout out branch in the component source code directory
    :rtype: str
    """
    return (
        subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=srcdir,
        )
        .decode()
        .rstrip("\r\n")
    )


def get_current_commit(srcdir):
    """Return information about git commit checked out in the given directory.

    :param srcdir: source code directory
    :type srcdir: str

    :return: commit information composed of brief SHA1 and subject
    :rtype: str
    """
    return (
        subprocess.check_output(
            ["git", "log", "--pretty=format:%h %s", "-n", "1"],
            cwd=srcdir,
        )
        .decode()
        .rstrip("\r\n")
    )


def git_is_current_version_tagged(component):
    """Determine whether the current version in source code is present as a git tag."""
    current_version = get_current_component_version_from_source_files(component)
    is_version_tagged = int(
        run_command(
            f"git tag --list {current_version} | wc -l",
            component,
            display=False,
            return_output=True,
        )
    )
    return bool(is_version_tagged)


def git_create_release_branch(component: str, next_version: Optional[str]):
    """Create a feature branch for a new release."""
    version_files = get_component_version_files(component)
    if not next_version:
        # bump current version depending on whether it is semver2 or pep440
        current_version = get_current_component_version_from_source_files(component)
        if (
            version_files.get(DOCKER_VERSION_FILE)
            and component not in REPO_LIST_PYTHON_FIRST
        ):
            next_version = bump_semver2_version(current_version)
        elif version_files.get(HELM_VERSION_FILE):
            next_version = bump_semver2_version(current_version)
        elif version_files.get(PYTHON_VERSION_FILE):
            next_version = bump_pep440_version(current_version)
        elif version_files.get(JAVASCRIPT_VERSION_FILE):
            next_version = bump_semver2_version(current_version)
        elif version_files.get(OPENAPI_VERSION_FILE):
            next_version = bump_pep440_version(current_version)
    else:
        # provided next_version is always in pep440 version
        if (
            DOCKER_VERSION_FILE in version_files
            and component not in REPO_LIST_PYTHON_FIRST
            or HELM_VERSION_FILE in version_files
            or JAVASCRIPT_VERSION_FILE in version_files
        ):
            next_version = translate_pep440_to_semver2(next_version)
        else:
            next_version = str(parse_pep440_version(next_version))
    if not next_version:
        display_message("Could not generate next version.", component)
        sys.exit(1)
    run_command(f"git checkout -b release-{next_version}", component)
    display_message(f"Release branch 'release-{next_version}' created.", component)


def git_create_release_commit(
    component: str,
    base: str = GIT_DEFAULT_BASE_BRANCH,
    next_version: Optional[str] = None,
) -> bool:
    """Create a release commit for the given component."""
    if is_last_commit_release_commit(component):
        display_message("Nothing to do, last commit is a release commit.", component)
        return False

    current_version = get_current_component_version_from_source_files(component)
    if not current_version and not next_version:
        display_message(
            "Version cannot be autodiscovered from source files.", component
        )
        sys.exit(1)
    elif not git_is_current_version_tagged(component) and not next_version:
        display_message(
            f"Current version ({current_version}) "
            "not present as a git tag, please release it and add a tag.",
            component,
        )
        sys.exit(1)

    next_version, modified_files = bump_component_version(
        component, next_version=next_version
    )

    if (
        run_command(
            "git branch --show-current",
            component,
            display=False,
            return_output=True,
        )
        == base
    ):
        run_command(f"git checkout -b release-{next_version}", component)

    if modified_files:
        run_command(f"git add {' '.join(modified_files)}", component)

    commit_msg = (
        f"chore({base}): release {next_version}{get_commit_pr_suffix(component)}"
    )
    run_command(
        f"git commit -m '{commit_msg}' {'--allow-empty' if not modified_files else ''}",
        component,
    )
    return True


def compare_branches(srcdir, branch_to_compare, current_branch):
    """Compare two branches with ``git rev-list``.

    Runs entirely in ``srcdir`` via ``cwd=`` — no global ``os.chdir`` side
    effect and no shell pipeline, which keeps per-component overhead low on
    platforms where ``fork``/``exec`` is slow (notably macOS).
    """
    if not remote_ref_exists(srcdir, branch_to_compare):
        click.secho(
            "ERROR: Branch {} does not exist.".format(branch_to_compare), fg="red"
        )
        return 0, 0
    output = subprocess.check_output(
        [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            "{0}...{1}".format(branch_to_compare, current_branch),
        ],
        cwd=srcdir,
    ).decode()
    behind, ahead = [int(x) for x in output.split()]
    return behind, ahead


def is_component_behind_branch(
    component,
    branch_to_compare,
    current_branch=None,
):
    """Report to stdout the differences between two branches."""
    srcdir = get_srcdir(component)
    current_branch = current_branch or get_current_branch(srcdir)
    behind, _ = compare_branches(srcdir, branch_to_compare, current_branch)
    return bool(behind)


def print_branch_difference_report(
    component,
    branch_to_compare,
    current_branch=None,
    base=GIT_DEFAULT_BASE_BRANCH,
    commit=None,
    short=False,
    srcdir=None,
):
    """Report to stdout the differences between two branches.

    When ``branch_to_compare`` is ``None`` (e.g. detached HEAD), the
    ahead/behind comparison is skipped entirely, but ``short=True`` still
    prints ``git status --short`` so the report stays useful.
    """
    # detect how far it is ahead/behind from pr/origin/upstream
    srcdir = srcdir or get_srcdir(component)
    current_branch = current_branch or get_current_branch(srcdir)
    commit = commit or get_current_commit(srcdir)
    report = ""
    if branch_to_compare is not None:
        behind, ahead = compare_branches(srcdir, branch_to_compare, current_branch)
        if ahead or behind:
            report += "("
            if ahead:
                report += "{0} AHEAD ".format(ahead)
            if behind:
                report += "{0} BEHIND ".format(behind)
            report += branch_to_compare + ")"
        # detect rebase needs for local branches and PRs
        if branch_to_compare != "upstream/{}".format(base):
            branch_to_compare = "upstream/{}".format(base)
            behind, ahead = compare_branches(srcdir, branch_to_compare, current_branch)
            if behind:
                report += "(STEMS FROM "
                if behind:
                    report += "{0} BEHIND ".format(behind)
                report += branch_to_compare + ")"

    click.secho("{0}".format(component), nl=False, bold=True)
    click.secho(" @ ", nl=False, dim=True)
    if current_branch == base:
        click.secho("{0}".format(current_branch), nl=False)
    else:
        click.secho("{0}".format(current_branch), nl=False, fg="green")
    if report:
        click.secho(" {0}".format(report), nl=False, fg="red")
    click.secho(" @ ", nl=False, dim=True)
    click.secho("{0}".format(commit))
    # optionally, display also short status
    if short:
        cmd = "git status --short"
        run_command(cmd, component, display=False)


def is_last_commit_release_commit(package):
    """Check whether the last commit is a release commit."""
    current_commit = get_current_commit(get_srcdir(package))
    commit_msg = current_commit.split(maxsplit=1)[1]
    return RELEASE_COMMIT_REGEX.match(commit_msg)


def git_push_to_origin(components):
    """Push current branch to origin."""
    for component in components:
        branch = run_command("git branch --show-current", component, return_output=True)
        run_command(
            f"git push --force origin {branch}",
            component,
        )


@click.group()
def git_commands():
    """Git commands group."""


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--browser", "-b", default="firefox", help="Which browser to use? [firefox]"
)
@click.option(
    "--automatic",
    is_flag=True,
    default=False,
    help="Use GitHub CLI for automatic forking.",
)
@git_commands.command(name="git-fork")
def git_fork(component, exclude_components, browser, automatic):  # noqa: D301
    """Display the commands to fork REANA source code repositories.

    By default, the command will display the commands to fork the selected REANA
    components, and prompt you to complete the process in the browser.
    You can also use the ``--automatic`` flag to use GitHub CLI for automatic
    forking, skipping the browser step.
    Note that this command does not clone the forked repositories: to do that,
    use the ``reana-dev git-clone`` command.

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
    :param exclude_components: List of components to exclude.
    :param browser: The web browser to use. [default=firefox]
    :param automatic: Use GitHub CLI for automatic forking. [default=False]
    :type component: str
    :type exclude_components: str
    :type browser: str
    :type automatic: bool
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)

    if components and not automatic:
        click.echo("# Fork REANA repositories on GitHub using your browser.")
        click.echo(
            "# Run the following eval and then complete the fork"
            " process in your browser."
        )
        click.echo("#")
        click.echo(
            '# eval "$(reana-dev git-fork -b {0} {1})"'.format(
                browser, "".join([" -c {0}".format(c) for c in component])
            )
        )

    for component in components:
        if automatic:
            cmd = f"gh repo fork reanahub/{component} --clone=false"
            run_command(cmd)
            display_message(
                f"Repository {component} forked successfully using GitHub CLI.",
                component,
            )
        else:
            click.echo(f"{browser} https://github.com/reanahub/{component}/fork;")

    if components:
        if not automatic:
            click.echo(
                'echo "Please continue the fork process in the opened browser windows."'
            )
        else:
            click.echo(
                "All repositories forked successfully. You can clone them locally with reana-dev git-clone."
            )


@click.option("--user", "-u", default="anonymous", help="GitHub user name [anonymous]")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--target-directory",
    default=".",
    callback=validate_directory,
    help="In which directory to clone?[.]",
)
@git_commands.command(name="git-clone")
def git_clone(user, component, exclude_components, target_directory):  # noqa: D301
    """Clone REANA source repositories from GitHub.

    If the ``user`` argument is provided, the ``origin`` will be cloned from
    the user repository on GitHub and the ``upstream`` will be set to
    ``reanahub`` organisation. Useful for setting up personal REANA development
    environment,

    If the ``user`` argument is not provided, the cloning will be done in
    anonymous manner from ``reanahub`` organisation. Also, the clone will be
    shallow to save disk space and CPU time. Useful for CI purposes.

    \b
    :param user: The GitHub user name. [default=anonymous]
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
    :param exclude_components: List of components to exclude.
    :param user: The GitHub user name. [default=anonymous]
    :type component: str
    :type exclude_components: str
    :type user: str
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)

    for component in components:
        os.chdir(target_directory)
        if os.path.exists("{0}/.git/config".format(component)):
            msg = "Component seems already cloned. Skipping."
            display_message(msg, component)
        elif user == "anonymous":
            cmd = "git clone https://github.com/reanahub/{0} --depth 1".format(
                component
            )
            run_command(cmd)
        else:
            cmd = "git clone git@github.com:{0}/{1}".format(user, component)
            run_command(cmd)
            for cmd in [
                "git remote add upstream"
                ' "git@github.com:reanahub/{0}"'.format(component),
                "git config --add remote.upstream.fetch"
                ' "+refs/pull/*/head:refs/remotes/upstream/pr/*"',
            ]:
                run_command(cmd, component, directory=target_directory)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--short",
    "-s",
    is_flag=True,
    default=False,
    help="Show git status short format details?",
)
@git_commands.command(name="git-status")
@click_add_git_base_branch_option
def git_status(component, exclude_components, short, base):  # noqa: D301
    """Report status of REANA source repositories.

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
    :param exclude_components: List of components to exclude.
    :param base: Against which git base branch are we working? [default=master]
    :param verbose: Show git status details? [default=False]
    :type component: str
    :type exclude_components: str
    :type base: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        srcdir = get_srcdir(component)
        current_branch = get_current_branch(srcdir)
        commit = get_current_commit(srcdir)
        # detect branch to compare against
        if current_branch == "HEAD":  # detached HEAD
            branch_to_compare = None
            current_branch = "(detached HEAD)"
        elif current_branch == base:  # base branch
            branch_to_compare = "upstream/" + base
        elif current_branch.startswith("pr-"):  # other people's PR
            branch_to_compare = "upstream/" + current_branch.replace("pr-", "pr/")
        else:
            branch_to_compare = "origin/" + current_branch  # my PR
            if not remote_ref_exists(srcdir, branch_to_compare):
                branch_to_compare = "origin/" + base  # local unpushed branch
        print_branch_difference_report(
            component,
            branch_to_compare,
            current_branch=current_branch,
            commit=commit,
            base=base,
            short=short,
            srcdir=srcdir,
        )


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@git_commands.command(name="git-clean")
def git_clean(component, exclude_components):  # noqa: D301
    """Clean REANA source repository code tree.

    Removes all non-source-controlled files in the component source code
    repository. Useful to run before building container images.

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
    :param exclude_components: List of components to exclude.
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        for cmd in [
            "git clean -d -ff -x",
        ]:
            run_command(cmd, component)


@click.option(
    "--update", is_flag=True, help="Update shared modules everywhere?", default=False
)
@click.option(
    "--status",
    is_flag=True,
    help="Show status of shared modules everywhere.",
    default=False,
)
@click.option(
    "--delete", is_flag=True, help="Delete shared modules everywhere?", default=False
)
@git_commands.command(name="git-submodule")
def git_submodule(update=False, status=False, delete=False):  # noqa: D301
    """Sync REANA shared modules across all the repositories.

    Take currently checked-out reana-commons and reana-db modules and sync them
    across REANA components. Useful for building container images with
    not-yet-released shared modules.

    The option ``--update`` propagates the shared modules across the code base
    as necessary. Useful before running local docker image building.

    The option ``--status`` shows the information about shared modules.

    The option ``--delete`` removes the shared modules from everywhere. Useful
    for clean up after testing.
    """
    if update:
        for component in COMPONENTS_USING_SHARED_MODULE_COMMONS:
            for cmd in [
                "rsync -az --delete --exclude='.git' --exclude='.mise.toml' ../reana-commons modules",
            ]:
                run_command(cmd, component)
        for component in COMPONENTS_USING_SHARED_MODULE_DB:
            for cmd in [
                "rsync -az --delete --exclude='.git' --exclude='.mise.toml' ../reana-db modules",
            ]:
                run_command(cmd, component)
    elif delete:
        for component in set(
            COMPONENTS_USING_SHARED_MODULE_COMMONS + COMPONENTS_USING_SHARED_MODULE_DB
        ):
            for cmd in [
                "rm -rf ./modules/",
            ]:
                run_command(cmd, component)
    elif status:
        for component in COMPONENTS_USING_SHARED_MODULE_COMMONS:
            for cmd in [
                "git status -s",
            ]:
                run_command(cmd, component)
        for component in COMPONENTS_USING_SHARED_MODULE_DB:
            for cmd in [
                "git status -s",
            ]:
                run_command(cmd, component)
    else:
        click.echo(
            "Unknown action. Please specify `--update`, `--status` "
            " or `--delete`. Exiting."
        )
        sys.exit(1)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@git_commands.command(name="git-branch")
def git_branch(component, exclude_components):  # noqa: D301
    """Display information about locally checked-out branches.

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
    :param exclude_components: List of components to exclude.
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    for component in select_components(component, exclude_components):
        cmd = "git branch -vv"
        run_command(cmd, component)


@click.argument(
    "branch",
)
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option("--fetch", is_flag=True, default=False)
@git_commands.command(name="git-checkout")
def git_checkout(branch, component, exclude_components, fetch):  # noqa: D301
    """Check out given local branch in desired components.

    \b
    :param branch: Do you want to checkout some existing branch? [e.g. maint-0.7]
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
    :param exclude_components: List of components to exclude.
    :param fetch: Should we fetch latest upstream first? [default=False]
    :type branch: str
    :type component: list
    :type exclude_components: str
    :type fetch: bool
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    for component in select_components(component, exclude_components):
        if fetch:
            run_command("git fetch upstream", component)
        if branch_exists(component, branch):
            run_command("git checkout {}".format(branch), component)
        else:
            click.secho(
                "No branch {} in component {}, staying on current one.".format(
                    branch, component
                ),
                fg="red",
            )


def _get_prs_from_issue(repo, issue_number):
    """Return (component, pr_number) pairs for all PRs linked to a GitHub issue."""
    # Use the issue timeline API to get all events for this issue
    output = run_command(
        f"gh api repos/reanahub/{repo}/issues/{issue_number}/timeline --paginate",
        display=False,
        return_output=True,
    )

    try:
        events = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        click.secho("Failed to parse GitHub API results.", fg="red")
        sys.exit(1)

    # Extract PRs from cross-referenced events
    prs = set()
    for event in events:
        if event.get("event") != "cross-referenced":
            # We're only looking for cross-referencing events (not e.g. comments)
            continue

        source_issue = event.get("source", {}).get("issue", {})
        if not source_issue.get("pull_request"):
            # We're only looking for events mentioning PRs
            continue

        component = source_issue.get("repository", {}).get("name", "")
        pr_number = str(source_issue["number"])
        prs.add((component, pr_number))

    prs = list(prs)

    if not prs:
        click.secho(
            f"No PRs found linked to reanahub/{repo}#{issue_number}.",
            fg="yellow",
        )

    return prs


def _collect_prs_to_checkout(branch, issue):
    """Return a deduplicated, conflict-checked list of (component, pr_number) pairs.

    :raises: SystemExit on conflict.
    """
    prs = []

    for component, pull_request in branch:
        component = select_components([component])[0]
        if component not in REPO_LIST_ALL:
            display_message("Ignoring unknown component.", component)
            continue
        prs.append((component, pull_request))

    if issue is not None:
        repo, issue_number = issue

        try:
            repo = find_standard_component_name(repo)
        except Exception:
            click.secho(
                f"Component name {repo} cannot be uniquely mapped — "
                "pass the full repository name.",
                fg="red",
            )
            sys.exit(1)

        for component, pull_request in _get_prs_from_issue(repo, issue_number):
            if component not in REPO_LIST_ALL:
                click.secho(
                    f"Skipping PR #{pull_request} in {component} (not a known REANA component).",
                    fg="yellow",
                )
                continue
            prs.append((component, pull_request))

    # Detect conflicts (whether from -b repetition or -b vs -i) where the user
    # is trying to check out two different PRs from the same component.
    # Same (component, PR#) pair appearing twice is harmless and silently deduped.
    by_component = {}
    for component, pr in prs:
        if component in by_component and by_component[component] != pr:
            click.secho(
                f"Conflict for {component}: asked to check out both "
                f"pr-{by_component[component]} and pr-{pr}. "
                "Remove the duplicate from -b/-i.",
                fg="red",
            )
            sys.exit(1)
        by_component[component] = pr
    return list(by_component.items())


def _checkout_pr_branch(component, pull_request, fetch, pull, reset):
    """Fetch and check out a single PR branch."""
    if fetch or pull or reset:
        run_command("git fetch upstream", component)

    if not branch_exists(component, f"pr-{pull_request}"):
        run_command(
            f"git checkout -b pr-{pull_request} upstream/pr/{pull_request}",
            component,
        )
        return

    run_command(f"git checkout pr-{pull_request}", component)

    if reset:
        run_command(f"git reset --hard upstream/pr/{pull_request}", component)
    elif pull:
        _pull_pr_branch(component, pull_request)


def _pull_pr_branch(component, pull_request):
    """Fast-forward an existing PR branch, refusing if dirty or non-fast-forwardable."""
    # `git status --porcelain` also lists untracked files. We intentionally
    # treat them as "dirty" — refusing to ff-merge is safer than ff'ing
    # over scratch state the user may want to preserve.
    dirty = run_command(
        "git status --porcelain", component, display=False, return_output=True
    )

    if dirty:
        click.secho(
            f"{component}: skipping update of pr-{pull_request}: "
            "working tree has local modifications (use --reset to override).",
            fg="yellow",
        )
        return

    try:
        run_command(
            f"git merge --ff-only upstream/pr/{pull_request}",
            component,
            exit_on_error=False,
        )
    except subprocess.CalledProcessError:
        click.secho(
            f"{component}: cannot fast-forward pr-{pull_request}: "
            "branch has local commits (use --reset to override).",
            fg="yellow",
        )


@click.option(
    "--branch", "-b", nargs=2, multiple=True, help="Which PR? [component PR#]"
)
@click.option(
    "--issue",
    "-i",
    nargs=2,
    default=None,
    help="Derive PRs from a GitHub issue. [repo issue#]",
)
@click.option(
    "--fetch",
    is_flag=True,
    default=False,
    help="Fetch latest upstream before checking out?",
)
@click.option(
    "--pull",
    is_flag=True,
    default=False,
    help="Fetch and fast-forward existing local PR branches?",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help="Fetch and hard-reset existing local PR branches?",
)
@git_commands.command(name="git-checkout-pr")
def git_checkout_pr(branch, issue, fetch, pull, reset):  # noqa: D301
    """Check out local branches corresponding to pull requests.

    The ``-b`` option can be repeated to check out several pull requests
    across several repositories at the same time. Use ``-i`` to automatically
    derive the set of PRs from a GitHub issue's linked PRs instead.

    For existing local PR branches, the default behaviour is to switch to them
    without modifying their state. Use ``--pull`` to fetch and fast-forward
    them (refusing if the branch is dirty or has local commits), or ``--reset``
    to fetch and hard-reset them unconditionally.

    \b
    :param branch: The option ``branch`` can be repeated. The value consists of
                   two strings specifying the component name and the pull
                   request number. For example, ``-b reana-workflow-controller
                   72`` will create a local branch called ``pr-72`` in the
                   reana-workflow-controller source code directory.
    :param issue: Derive PRs to check out from the cross-references of a GitHub
                  issue. The value consists of two strings: the reanahub
                  repository name and the issue number. For example,
                  ``-i reana-commons 123`` will check out all PRs that
                  reference the reana-commons#123 issue.
    :param fetch: Fetch latest upstream before checking out? [default=False]
    :param pull: Fetch and fast-forward existing local PR branches? [default=False]
    :param reset: Fetch and hard-reset existing local PR branches? [default=False]
    :type branch: list
    :type issue: Optional[tuple]
    :type fetch: bool
    :type pull: bool
    :type reset: bool
    """
    if not branch and issue is None:
        click.secho("Please specify -b/--branch or -i/--issue.", fg="red")
        sys.exit(1)

    for component, pull_request in _collect_prs_to_checkout(branch, issue):
        _checkout_pr_branch(component, pull_request, fetch, pull, reset)


@click.option(
    "--branch", "-b", nargs=2, multiple=True, help="Which PR? [component PR#]"
)
@click.option(
    "--push", is_flag=True, default=False, help="Should we push to origin and upstream?"
)
@git_commands.command(name="git-merge")
@click_add_git_base_branch_option
def git_merge(branch, base, push):  # noqa: D301
    """Merge a component pull request to local base branch.

    The ``-b`` option can be repetitive to merge several pull requests in
    several repositories at the same time.

    \b
    :param branch: The option ``branch`` can be repeated. The value consist of
                   two strings specifying the component name and the pull
                   request number. For example, ``-b reana-workflow-controller
                   72`` will merge a local branch called ``pr-72`` from the
                   reana-workflow-controller to the base branch.
    :param base: Against which git base branch are we working on? [default=master]
    :param push: Should we push to origin and upstream? [default=False]
    :type base: str
    :type branch: list
    :type push: bool
    """
    for cpr in branch:
        component, pull_request = cpr
        component = select_components(
            [
                component,
            ]
        )[0]
        if component in REPO_LIST_ALL:
            for cmd in [
                "git fetch upstream",
                "git diff pr-{0}..upstream/pr/{0} --exit-code".format(pull_request),
                "git checkout {0}".format(base),
                "git merge --ff-only upstream/{0}".format(base),
                "git merge --ff-only upstream/pr/{0}".format(pull_request),
                "git branch -d pr-{0}".format(pull_request),
            ]:
                run_command(cmd, component)

            if push:
                for cmd in [
                    "git push origin {0}".format(base),
                    "git push upstream {0}".format(base),
                ]:
                    run_command(cmd, component)
        else:
            msg = "Ignoring unknown component."
            display_message(msg, component)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--parallel",
    "-p",
    default=8,
    type=click.IntRange(min=1),
    help="Number of components to fetch in parallel. [default=8]",
)
@git_commands.command(name="git-fetch")
def git_fetch(component, exclude_components, parallel):  # noqa: D301
    """Fetch REANA upstream source code repositories without upgrade.

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
    :param exclude_components: List of components to exclude.
    :param parallel: How many components to fetch in parallel. [default=8]
    :type component: str
    :type exclude_components: str
    :type parallel: int
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    if parallel == 1 or len(components) <= 1:
        for component in components:
            run_command("git fetch upstream", component)
        return
    # Pre-warm: fetch the first component serially before spinning up the
    # parallel pool. If the user's ssh config enables `ControlMaster`,
    # this lets the first connection establish the shared master socket
    # so the parallel workers reuse it instead of racing to create it
    # (and printing "ControlSocket already exists, disabling
    # multiplexing" warnings as they lose the race). For users without
    # `ControlMaster`, the pre-warm is harmless — the first component
    # was going to be fetched anyway.
    failed = []
    prewarm = components[0]
    try:
        run_command("git fetch upstream", prewarm, exit_on_error=False)
    except subprocess.CalledProcessError:
        # `run_command` already logged the failure with a component prefix.
        failed.append(prewarm)
    # Concurrent fetches for the remaining components: each worker
    # captures both stdout and stderr (`git fetch` writes progress and
    # SSH ControlMaster warnings to stderr) and returns them to the
    # parent, which prints every component's block atomically in
    # completion order. Failures are collected and surfaced via a
    # non-zero exit at the end so the parallel path keeps the same
    # exit-status semantics as the serial path.
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        future_to_component = {
            executor.submit(_fetch_upstream_capture, component): component
            for component in components[1:]
        }
        for future in as_completed(future_to_component):
            component = future_to_component[future]
            output, returncode = future.result()
            # Match the serial `run_command` display: a timestamped header
            # per component, followed by the captured output verbatim.
            # With `as_completed` each component appears as a contiguous
            # block, so the captured lines do not need a per-line prefix
            # to stay attributable.
            now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            click.secho(f"[{now}] ", bold=True, nl=False, fg="green")
            click.secho(f"{component}: ", bold=True, nl=False, fg="yellow")
            click.secho("git fetch upstream", bold=True)
            for line in output.splitlines():
                click.echo(line)
            if returncode != 0:
                failed.append(component)
                click.secho(f"[{now}] ", bold=True, nl=False, fg="green")
                click.secho(f"{component}: ", bold=True, nl=False, fg="yellow")
                click.secho(
                    f"git fetch failed (exit {returncode})", bold=True, fg="red"
                )
    if failed:
        display_message(
            f"git fetch failed for {len(failed)} component(s): " f"{', '.join(failed)}",
            component="reana",
        )
        sys.exit(1)


def _fetch_upstream_capture(component):
    """Run ``git fetch upstream`` for one component, capturing all output.

    Returns ``(combined_output, returncode)`` rather than raising, so the
    parent can prefix every line per component, collect failures across
    all components and exit non-zero at the end. ``stderr`` is merged
    into ``stdout`` because ``git fetch`` writes its progress lines, its
    error messages and any SSH ``ControlMaster`` warnings to stderr —
    leaving stderr uncaptured would interleave that traffic between
    concurrent workers and lose the per-component attribution.
    """
    result = subprocess.run(
        ["git", "fetch", "upstream"],
        cwd=get_srcdir(component),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.stdout, result.returncode


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--create-branch",
    is_flag=True,
    default=False,
    help="Should the branch be created if it does not exist? [default=False]",
)
@git_commands.command(name="git-upgrade")
@click_add_git_base_branch_option
def git_upgrade(component, exclude_components, create_branch, base):  # noqa: D301
    """Upgrade REANA local source code repositories and push to GitHub origin.

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
    :param exclude_components: List of components to exclude.
    :param create_branch: Should the branch be created if it does not exist?
    :param base: Against which git base branch are we working on? [default=master]
    :type component: str
    :type exclude_components: str
    :type create_branch: bool
    :type base: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")

    components = select_components(component, exclude_components)
    for component in components:
        if not branch_exists(component, base):
            if create_branch:
                # Check if upstream branch exists before creating local branch
                if not run_command(
                    ["git", "ls-remote", "--heads", "upstream", f"refs/heads/{base}"],
                    component,
                    display=False,
                    return_output=True,
                ):
                    display_message(
                        f"Branch {base} does not exist in upstream, skipping.",
                        component=component,
                    )
                    continue

                run_command(["git", "fetch", "upstream"], component)
                run_command(
                    ["git", "checkout", "-b", base, f"upstream/{base}"], component
                )
                try:
                    run_command(["git", "push", "-u", "origin", base], component)
                finally:
                    run_command(["git", "checkout", "-"], component)
                display_message(
                    f"Branch {base} created from upstream and pushed to origin.",
                    component=component,
                )
            else:
                display_message(
                    f"Missing branch {base}, skipping.", component=component
                )

            # Branch was just created fresh or is missing so skip the merge/push upgrade flow
            continue

        run_command(["git", "fetch", "upstream"], component)
        run_command(["git", "checkout", base], component)
        run_command(["git", "merge", "--ff-only", f"upstream/{base}"], component)
        run_command(["git", "push", "origin", base], component)
        run_command(["git", "checkout", "-"], component)


@click.argument("range", default="")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude from command? [c1,c2,c3]",
)
@click.option("--number", "-n", default=10, help="Number of commits to output [10]")
@click.option("--graph", is_flag=True, default=False, help="Show log graph?")
@click.option("--oneline", is_flag=True, default=False, help="Show one-line format?")
@click.option("--stat", is_flag=True, default=False, help="Show diff stat?")
@click.option("--patch", "-p", is_flag=True, default=False, help="Show diff patch?")
@click.option("--all", is_flag=True, default=False, help="Show all references?")
@click.option("--paginate", is_flag=True, default=False, help="Paginate output?")
@git_commands.command(name="git-log")
def git_log(
    range,
    component,
    exclude_components,
    number,
    graph,
    oneline,
    stat,
    patch,
    all,
    paginate,
):  # noqa: D301
    """Show commit logs in given component repositories.

    \b
    :param range: The commit log range to operate on.
    :param component: The option ``component`` can be repeated. The value may
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
    :param exclude_components: List of components to exclude from command.
    :param number: The number of commits to output. [10]
    :param graph: Show log graph?
    :param oneline: Show one-line format?
    :param patch: Show diff patch?
    :param all: Show all references?
    :param paginate: Paginate output?
    :type range: str
    :type component: str
    :type exclude_components: str
    :type number: int
    :type graph: bool
    :type oneline: bool
    :type stat: bool
    :type patch: bool
    :type all: bool
    :type paginate: bool
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        if paginate:
            cmd = "git --paginate log"
        else:
            cmd = "git --no-pager log"
        if number:
            cmd += " -n {}".format(number)
        if graph:
            cmd += (
                " --graph --decorate"
                ' --pretty=format:"%C(blue)%d%Creset'
                " %C(yellow)%h%Creset %s, %C(bold green)%an%Creset,"
                ' %C(green)%cd%Creset" --date=relative'
            )
        if oneline or graph or all:
            cmd += " --oneline"
        if stat:
            cmd += " --stat"
        if patch:
            cmd += " --patch"
        if all:
            cmd += " --all"
        if range:
            cmd += " {}".format(range)
        msg = cmd[0 : cmd.find("--pretty")] + "..."
        display_message(msg, component)
        run_command(cmd, component, display=False)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@git_commands.command(name="git-diff")
@click_add_git_base_branch_option
def git_diff(component, exclude_components, base):  # noqa: D301
    """Diff checked-out REANA local source code repositories.

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
    :param exclude_components: List of components to exclude.
    :param base: Against which git base branch are we working on? [default=master]
    :type component: str
    :type exclude_components: str
    :type base: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        for cmd in [
            "git diff {}".format(base),
        ]:
            run_command(cmd, component)


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
    help="Which components to exclude? [c1,c2,c3]",
)
@git_commands.command(name="git-push")
@click_add_git_base_branch_option
def git_push(component, exclude_components, base):  # noqa: D301
    """Push REANA local repositories to GitHub origin.

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
    :param exclude_components: List of components to exclude.
    :param base: Against which git base branch are we working on? [default=master]
    :type component: str
    :type exclude_components: str
    :type base: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        for cmd in ["git push origin {}".format(base)]:
            run_command(cmd, component)


@click.option(
    "--component",
    "-c",
    required=True,
    multiple=True,
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--version",
    "-v",
    help="Shall we manually specify component's next version?",
)
@git_commands.command(name="git-create-release-branch")
def git_create_release_branch_command(
    component, exclude_components, version
):  # noqa: D301
    """Create a release branch for the specified components.

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
    :param exclude_components: List of components to exclude.
    :param version: Manually specifies the version for the component. If not provided,
        the last version will be auto-incremented.
    :type component: str
    :type exclude_components: str
    :type version: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        git_create_release_branch(component, next_version=version)


@git_commands.command(name="git-upgrade-shared-modules")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER", "CLIENT"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--use-latest-known-tag",
    is_flag=True,
    default=False,
    help="Should the upgrade use the latest known tag of the shared modules?"
    " If so, the latest known tag of the shared modules will be used to upgrade the"
    " provided components. Else, the upgrade will only occur if the latest commit of the"
    " shared modules points at a tag, in other case, the command will be aborted.",
)
@click.option(
    "--amend",
    is_flag=True,
    default=False,
    help="Should the changes be integrated as part of the latest commit of each component?",
)
@click.option(
    "--push",
    is_flag=True,
    default=False,
    help="Should the feature branches with the upgrades be pushed to origin?",
)
@click.pass_context
def git_upgrade_shared_modules(
    ctx, component, exclude_components, use_latest_known_tag, amend, push
):  # noqa: D301
    """Upgrade selected components to latest REANA-Commons/DB version.

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
    :param exclude_components: List of components to exclude.
    :type component: str
    :type exclude_components: str
    """

    def _create_commit_or_amend(components):
        today = datetime.date.today().isoformat()
        for c in components:
            commit_cmd = f'git commit -m "chore(master): bump shared REANA packages as of {today}{get_commit_pr_suffix(c)}"'
            if amend:
                commit_cmd = "git commit --amend --no-edit"

            files_to_commit = []
            if os.path.exists(get_srcdir(c) + os.sep + "setup.py"):
                files_to_commit.append("setup.py")
            if os.path.exists(get_srcdir(c) + os.sep + "pyproject.toml"):
                files_to_commit.append("pyproject.toml")
            if os.path.exists(get_srcdir(c) + os.sep + "requirements.txt"):
                files_to_commit.append("requirements.txt")
            run_command(
                f"git add {' '.join(files_to_commit)} && {commit_cmd}",
                c,
            )

    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)

    for module in REPO_LIST_SHARED:
        last_version = fetch_latest_pypi_version(module)
        update_module_in_cluster_components(
            module,
            last_version,
            components_to_update=components,
            use_latest_known_tag=use_latest_known_tag,
            force_feature_branch=True,
        )

    _create_commit_or_amend(components)
    ctx.invoke(git_diff, component=component)
    if push:
        git_push_to_origin(components)


@git_commands.command(name="git-upgrade-requirements")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.pass_context
def git_upgrade_requirements(ctx, component, exclude_components):  # noqa: D301
    """Upgrade Python dependencies for selected components.

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
    :param exclude_components: List of components to exclude.
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    components = sorted(set(components).intersection(REPO_LIST_PYTHON_REQUIREMENTS))

    for component in components:
        if not is_feature_branch(component):
            display_message(
                f"Current branch is {GIT_DEFAULT_BASE_BRANCH}. "
                "Please switch to a feature branch.",
                component,
            )
            sys.exit(1)
        if upgrade_requirements(component):
            run_command(f"git add {PYTHON_REQUIREMENTS_FILE}", component)
            today = datetime.date.today().isoformat()
            run_command(
                f'git commit -m "chore(master): bump all required packages as of {today}{get_commit_pr_suffix(component)}"',
                component,
            )


@click.option(
    "--component",
    "-c",
    required=True,
    multiple=True,
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--version",
    "-v",
    help="Shall we manually specify component's next version?",
)
@git_commands.command(name="git-create-release-commit")
def git_create_release_commit_command(
    component, exclude_components, version
):  # noqa: D301
    """Create a release commit for the specified components.

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
    :param exclude_components: List of components to exclude.
    :param version: Manually specifies the version for the component. If not provided,
        the last version will be auto-incremented..
    :type component: str
    :type exclude_components: str
    :type version: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        if git_create_release_commit(component, next_version=version):
            display_message("Release commit created.", component)


@click.option(
    "--component",
    "-c",
    required=True,
    multiple=True,
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--fill",
    "-f",
    is_flag=True,
    default=False,
    help="Do not prompt for title/body but use commit info",
)
@click.option(
    "--web",
    "-w",
    is_flag=True,
    default=False,
    help="Open the web browser to create a pull request",
)
@git_commands.command(name="git-create-pr")
@click_add_git_base_branch_option
def git_create_pr_command(component, exclude_components, base, fill, web):  # noqa: D301
    """Create a GitHub pull request for each selected component.

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
    :param exclude_components: List of components to exclude.
    :param base: Against which git base branch are we working on? [default=master]
    :param fill: Whether to use commit info as title/body or prompt for it
    :param web: Whether to open the web browser to create a pull request
    :type component: str
    :type exclude_components: str
    :type base: str
    :type fill: bool
    :type web: bool
    """

    def _git_create_pr(comp, fill, web):
        """Create a pull request for the provided component."""
        extra_args = ""
        if fill:
            extra_args += " --fill"
        if web:
            extra_args += " --web"
        for cmd in [
            "git push --set-upstream origin HEAD",
            "gh pr create -R reanahub/{} --base {} {}".format(comp, base, extra_args),
            "gh pr list",
        ]:
            run_command(cmd, component)

    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        if not is_feature_branch(
            component, base
        ):  # replace with is_feature_branch from #371
            display_message(
                "You are trying to create PR but the current branch is base branch {}, please "
                "switch to the wanted feature branch.".format(base),
                component,
            )
            sys.exit(1)
        else:
            if is_component_behind_branch(component, "upstream/{}".format(base)):
                print_branch_difference_report(component, "upstream/{}".format(base))
                display_message(
                    "Error: please rebase your feature branch against latest base branch {}.".format(
                        base
                    ),
                    component,
                )
                sys.exit(1)

            _git_create_pr(component, fill, web)


@click.option(
    "--component",
    "-c",
    required=True,
    multiple=True,
    help="Which components? [name|CLUSTER]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@git_commands.command(name="git-tag")
def git_tag(component, exclude_components):  # noqa: D301
    """Create the corresponding git tag for components with release commits.

    \b
    :param components: The option ``component`` can be repeated. The value may
                       consist of:
                         * (1) standard component name such as
                               'reana-workflow-controller';
                         * (2) short component name such as 'r-w-controller';
                         * (3) special value '.' indicating component of the
                               current working directory;
                         * (4) special value 'CLUSTER' that will expand to
                               cover all REANA cluster components;
                         * (5) special value 'CLIENT' that will expand to
                               cover all REANA client components;
                         * (6) special value 'DEMO' that will expand
                               to include several runable REANA demo examples;
                         * (7) special value 'ALL' that will expand to include
                               all REANA repositories.
    :param exclude_components: List of components to exclude.
    :type component: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        if not is_last_commit_release_commit(component):
            click.secho(
                "The last commit is not a release commit. Please use `reana-dev git-create-release-commit`.",
                fg="red",
            )
            sys.exit(1)

        current_version = get_current_component_version_from_source_files(component)
        run_command(f"git tag {current_version}", component=component)


def get_previous_versions_from_release_tag(release_tag, components, override=None):
    """Get the version of each component from a specific REANA release tag.

    Parses the scripts/prefetch-images.sh file from the given release tag to
    extract component versions.

    For new components that were not part of the specified release, the version
    will be set to None.
    """
    if override is None:
        override = {}
    prefetch_script = run_command(
        f"git show {release_tag}:scripts/prefetch-images.sh",
        component="reana",
        return_output=True,
    )

    # Parse component versions from prefetch-images.sh
    # Lines look like: docker.io/reanahub/reana-server:0.95.0-alpha.3 \
    prefetch_versions = {}
    for line in prefetch_script.splitlines():
        match = re.search(r"reanahub/([^:]+):([^\s\\]+)", line)
        if match:
            prefetch_versions[match.group(1)] = match.group(2)

    # Get reana-server version for shared components lookup
    prev_server = prefetch_versions.get("reana-server")

    prev_versions = dict(override)
    for component in components:
        if component in override:
            continue

        if (
            component
            in REPO_LIST_CLUSTER_INFRASTRUCTURE + REPO_LIST_CLUSTER_RUNTIME_BATCH
        ):
            # cluster components: get version from prefetch-images.sh
            prev_version = prefetch_versions.get(component)
        elif component in REPO_LIST_SHARED:
            # shared components: read version from requirements.txt of reana-server
            if prev_server:
                requirement = run_command(
                    f"git show {prev_server}:requirements.txt | grep '^{component}'",
                    component="reana-server",
                    return_output=True,
                )
                version_match = re.search("==([a-zA-Z0-9.-_]+)", requirement)
                prev_version = version_match.group(1) if version_match else None
            else:
                prev_version = None
        elif component == "reana":
            # reana helm chart: use the release tag itself
            prev_version = release_tag
        elif component == "reana-client":
            # reana-client: get version from currently checked out source files
            # (assumes repos are checked out at the correct release commits)
            prev_version = get_current_component_version_from_source_files(component)
        else:
            raise ValueError(f"Not able to find previous version of {component}")
        prev_versions[component] = prev_version

    return prev_versions


def get_previous_versions(components, override=None):
    """Get the version of each component at the time of the previous REANA release.

    For new components that were not part of the previous release, the version
    will be set to None.
    """
    if override is None:
        override = {}
    helm_values = yaml.safe_load(
        run_command(
            "git show HEAD~1:helm/reana/values.yaml",
            component="reana",
            return_output=True,
        )
    )

    prev_versions = dict(override)
    prev_server = helm_values["components"]["reana_server"]["image"].split(":")[1]
    for component in components:
        if component in override:
            continue

        if (
            component
            in REPO_LIST_CLUSTER_INFRASTRUCTURE + REPO_LIST_CLUSTER_RUNTIME_BATCH
        ):
            # cluster components: get version from docker image in
            # Helm values of previous REANA release
            component_key = component.replace("-", "_")
            if component_key not in helm_values["components"]:
                # new component not present in the previous release
                prev_version = None
            else:
                image = helm_values["components"][component_key]["image"]
                prev_version = image.split(":")[1]
        elif component in REPO_LIST_SHARED:
            # shared components: read version from requirements.txt of reana-server
            # of previous REANA release
            requirement = run_command(
                f"git show {prev_server}:requirements.txt | grep '^{component}'",
                component="reana-server",
                return_output=True,
            )
            prev_version = re.search("==([a-zA-Z0-9.-_]+)", requirement).group(1)
        elif component == "reana":
            # reana helm chart: get version from manifest of previous commit
            chart_manifest = yaml.safe_load(
                run_command(
                    "git show HEAD~1:helm/reana/Chart.yaml",
                    component="reana",
                    return_output=True,
                )
            )
            prev_version = chart_manifest["version"]
        else:
            raise ValueError(f"Not able to find previous version of {component}")
        prev_versions[component] = prev_version

    return prev_versions


def generate_changelog_with_cog(  # noqa: C901
    component, prev_version, current_version, commit_types=None
):
    """Generate formatted changelog lines using cog (cocogitto) for a version range.

    This is used as a fallback when CHANGELOG.md doesn't have entries for the
    given versions (e.g., for alpha releases).

    :param component: The component name.
    :param prev_version: The previous version (start of range, exclusive).
    :param current_version: The current version (end of range, inclusive).
    :param commit_types: Optional list of commit types to include (e.g., ["feat", "fix"]).
    :return: Formatted changelog lines.
    :rtype: list
    """
    if prev_version:
        version_range = f"{prev_version}..{current_version}"
    else:
        # new component, generate changelog for all commits up to current version
        version_range = f"..{current_version}"

    # Mapping from commit types to cog section names
    type_to_cog_section = {
        "feat": "Features",
        "fix": "Bug Fixes",
        "perf": "Performance Improvements",
        "refactor": "Refactoring",
        "style": "Style",
        "test": "Tests",
        "ci": "Continuous Integration",
        "docs": "Documentation",
        "build": "Build system",
        "chore": "Miscellaneous Chores",
    }

    # Convert commit_types to allowed cog sections
    allowed_cog_sections = None
    if commit_types:
        allowed_cog_sections = set()
        for ct in commit_types:
            if ct in type_to_cog_section:
                allowed_cog_sections.add(type_to_cog_section[ct])

    # Read release-please config to get section order and hidden sections
    config_path = os.path.join(get_srcdir(component), ".release-please-config.json")
    section_order = []  # ordered list of section names
    hidden_sections = set()

    # Mapping from cog section names to release-please section names
    cog_to_release_please = {
        "Features": "Features",
        "Bug Fixes": "Bug fixes",
        "Performance Improvements": "Performance improvements",
        "Refactoring": "Code refactoring",
        "Style": "Code style",
        "Tests": "Test suite",
        "Continuous Integration": "Continuous integration",
        "Documentation": "Documentation",
        "Build system": "Build",
        "Miscellaneous Chores": "Chores",
    }

    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            changelog_sections = (
                config.get("packages", {}).get(".", {}).get("changelog-sections", [])
            )
            for section in changelog_sections:
                section_name = section.get("section")
                hidden = section.get("hidden", False)
                if section_name:
                    section_order.append(section_name)
                    if hidden:
                        hidden_sections.add(section_name)
        except (json.JSONDecodeError, KeyError):
            pass

    cog_output = run_command(
        f"cog changelog {version_range}",
        component,
        return_output=True,
    )

    if not cog_output.strip():
        return []

    # Collect entries by section
    entries_by_section = defaultdict(list)
    header_line = ""
    current_section = ""

    # Build header using current_version (not from cog output which might show intermediate versions)
    today = datetime.date.today().strftime("%Y-%m-%d")
    if prev_version:
        compare_link = f"https://github.com/reanahub/{component}/compare/{prev_version}...{current_version}"
        header_line = (
            f"#### {component} [{current_version}]({compare_link}) ({today})\n"
        )
    else:
        header_line = f"#### {component} [{current_version}] ({today})\n"

    current_cog_section = ""  # track cog section for filtering
    for line in cog_output.splitlines():
        if line.startswith("## "):
            # skip cog's header, we use our own
            pass
        elif line.startswith("#### "):
            # section header, e.g. "#### Features", "#### Continuous Integration"
            current_cog_section = line[5:].strip()
            # map to release-please section name
            current_section = cog_to_release_please.get(
                current_cog_section, current_cog_section
            )
        elif line.startswith("- "):
            # skip if section is not in allowed types
            if allowed_cog_sections and current_cog_section not in allowed_cog_sections:
                continue
            # bullet point entry
            # cog format: "- (**scope**) message (#123) - (abcdef1) - Author Name"
            # we want:    "**scope:** message ([#123](link)) ([abcdef1](link))"
            entry = line[2:]  # remove "- "

            # check for BREAKING marker (HTML format from cog)
            # e.g. <span style="...">BREAKING</span>(**scope**) message
            is_breaking = bool(re.search(r"<span[^>]*>BREAKING</span>", entry))
            # remove HTML breaking marker
            entry = re.sub(r"<span[^>]*>BREAKING</span>\s*", "", entry)

            # extract components using regex
            # pattern: (**scope**) message (#PR) - (sha) - Author
            match = re.match(
                r"\(\*\*([^*]+)\*\*\)\s+(.+?)\s+\(#(\d+)\)\s+-\s+\(([a-f0-9]+)\)\s+-\s+.+$",
                entry,
            )
            if match:
                scope = match.group(1)
                message = match.group(2)
                pr_number = match.group(3)
                sha = match.group(4)
                # format with GitHub links
                pr_link = f"[#{pr_number}](https://github.com/reanahub/{component}/issues/{pr_number})"
                commit_link = (
                    f"[{sha}](https://github.com/reanahub/{component}/commit/{sha})"
                )
                breaking_prefix = "**BREAKING** " if is_breaking else ""
                entry = f"{breaking_prefix}**{scope}:** {message} ({pr_link}) ({commit_link})"
            else:
                # fallback: just clean up the format without links
                entry = re.sub(r"\(\*\*([^*]+)\*\*\)", r"**\1:**", entry)
                # remove author name
                entry = re.sub(r"\s+-\s+\([a-f0-9]+\)\s+-\s+.+$", "", entry)
                if is_breaking:
                    entry = "**BREAKING** " + entry

            entries_by_section[current_section].append(
                f"* [{current_section}] {entry}\n"
            )

    # Build output in release-please order
    formatted_lines = []
    if header_line:
        formatted_lines.append(header_line)
        formatted_lines.append("\n")

    # Output sections in the order defined by release-please config
    for section_name in section_order:
        if section_name in hidden_sections:
            continue
        if section_name in entries_by_section:
            formatted_lines.extend(entries_by_section[section_name])

    # Add any sections not in the config (shouldn't happen normally)
    for section_name, entries in entries_by_section.items():
        if section_name not in section_order and section_name not in hidden_sections:
            formatted_lines.extend(entries)

    return formatted_lines


def get_formatted_changelog_lines(component, versions):
    """Read and format the changelog lines of given component and versions.

    The changelog will be reformatted so that:
    - commit types do not create subsections (e.g. `### Build`)
    - the commit type is prepended to each commit message
    - all sections are moved one level down in the hierarchy

    Example:
    ```
    ## [0.9.8](https://github.com/reanahub/reana-commons/compare/0.9.7...0.9.8) (2024-03-01)


    ### Build

    * **python:** change extra names to comply with PEP 685 [...]
    ```

    becomes

    ```
    #### reana-commons [0.9.8](https://github.com/reanahub/reana-commons/compare/0.9.7...0.9.8) (2024-03-01)

    * [Build] **python:** change extra names to comply with PEP 685 [...]
    ```
    """
    changelog_path = os.path.join(get_srcdir(component), "CHANGELOG.md")
    with open(changelog_path) as f:
        changelog_lines = f.readlines()

    formatted_lines = []
    is_version_to_add = False
    current_section = ""
    for line in changelog_lines:
        # check if release in header is part of releases we are interested in
        matches = re.match(r"##\s+\[?([\d.]+)", line)
        if matches:
            is_version_to_add = matches.group(1) in versions
        if not is_version_to_add:
            continue

        if line.startswith("### "):
            # commit type (e.g. fix, feat, ...)
            current_section = line[len("### ") :].strip()
        elif line.startswith("## "):
            # release header
            line = f"#### {component}" + line[len("##") :]
            if formatted_lines:
                # add empty line before previous release changelog
                formatted_lines.append("\n")
            formatted_lines.append(line)
            formatted_lines.append("\n")
        elif line.startswith("*"):
            # release please format, bullet points with '*'
            formatted_lines.append(f"* [{current_section}]" + line[1:])
        elif line.startswith("-"):
            # old changelog format, bullet points with '-'
            formatted_lines.append("*" + line[1:])

    return formatted_lines


def substitute_version_changelog(component, version, new_lines):
    """Substitute the changelog of the provided version.

    If the version doesn't exist in the changelog (e.g., for alpha releases),
    a new section is created at the top of the changelog.
    """
    changelog_path = os.path.join(get_srcdir(component), "CHANGELOG.md")
    with open(changelog_path) as changelog_file:
        changelog_lines = changelog_file.readlines()

    # find the idx of the given release
    idx_begin = None
    for i, line in enumerate(changelog_lines):
        if line.startswith("## ") and version in line:
            idx_begin = i
            break

    if idx_begin is None:
        # version not found, insert new section at the top
        # find the first ## line (first version section) to insert before it
        idx_first_version = None
        for i, line in enumerate(changelog_lines):
            if line.startswith("## "):
                idx_first_version = i
                break

        if idx_first_version is None:
            # no version sections found, append at the end
            new_changelog = changelog_lines + [f"\n## [{version}]\n", "\n"] + new_lines
        else:
            # insert new section before the first existing version
            new_changelog = (
                changelog_lines[:idx_first_version]
                + [f"## [{version}]\n", "\n"]
                + new_lines
                + ["\n"]
                + changelog_lines[idx_first_version:]
            )
    else:
        idx_end = idx_begin + 1
        while idx_end < len(changelog_lines):
            if changelog_lines[idx_end].startswith("## "):
                break
            idx_end += 1

        new_changelog = (
            changelog_lines[: idx_begin + 2]  # let's keep header and blank line
            + new_lines
            + changelog_lines[idx_end:]
        )

    with open(changelog_path, "w") as changelog_file:
        changelog_file.writelines(new_changelog)


def append_after_version_changelog(component, version, new_lines):
    """Append the given lines after the changelog of the provided version."""
    changelog_path = os.path.join(get_srcdir(component), "CHANGELOG.md")
    with open(changelog_path) as changelog_file:
        changelog_lines = changelog_file.readlines()

    # find the idx of the release that follows the given one
    idx_insert = None
    found_given_version = False
    for i, line in enumerate(changelog_lines):
        if line.startswith("## "):
            if version in line:
                found_given_version = True
            elif found_given_version:
                idx_insert = i
                break

    if idx_insert is None:
        raise ValueError(f"Could not find changelog of {component} {version}")

    new_changelog = (
        changelog_lines[:idx_insert] + new_lines + changelog_lines[idx_insert:]
    )

    with open(changelog_path, "w") as changelog_file:
        changelog_file.writelines(new_changelog)


@git_commands.command(name="git-aggregate-changelog")
@click.option(
    "--previous-reana-client",
    help="Which is the version of reana-client that was released "
    "for the last REANA release?",
    required=True,
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--commit-range",
    default="",
    help="REANA release range to generate changelog for (e.g., 0.9.4..0.95.0-alpha.3). "
    "Uses scripts/prefetch-images.sh from the start tag to determine previous component "
    "versions and generates changelog with cog instead of CHANGELOG.md.",
)
@click.option(
    "--commit-types",
    default="",
    help="Filter changelog entries by commit types (e.g., feat,fix). "
    "Only entries matching these types will be included.",
)
def get_aggregate_changelog(  # noqa: C901
    previous_reana_client, exclude_components, commit_range, commit_types
):  # noqa: D301
    """Aggregate the changelog of all REANA components.

    Aggregate the changelog of all REANA components and append it to the main changelog of REANA.
    This is useful for creating the changelog of a new REANA release.

    All the repositories of the cluster components, shared components, `reana-client` and
    `reana` must be checked out at the respective release commits.

    When --commit-range is provided, uses cog to generate changelog entries
    instead of reading from CHANGELOG.md files. This is useful for alpha releases
    where CHANGELOG.md entries are not published.

    :param previous_reana_client: The version of reana-client that was part of the previous REANA release.
    :param exclude_components: List of components to exclude.
    :param commit_range: REANA release range (e.g., 0.9.4..0.95.0-alpha.3).
    :param commit_types: Comma-separated list of commit types to include (e.g., feat,fix).
    :type previous_reana_client: str
    :type exclude_components: str
    :type commit_range: str
    :type commit_types: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    if commit_types:
        commit_types = commit_types.split(",")
    # all the components whose changelogs will be aggregated
    changelog_components = set(
        ["reana", "reana-client"]
        + REPO_LIST_SHARED
        + REPO_LIST_CLUSTER_INFRASTRUCTURE
        + REPO_LIST_CLUSTER_RUNTIME_BATCH
    )
    if exclude_components:
        changelog_components = exclude_components_from_selection(
            changelog_components, exclude_components
        )
    changelog_components = sorted(changelog_components)

    # skip release commit check when using --commit-range (works from tags directly)
    if not commit_range:
        for component in changelog_components:
            if not is_last_commit_release_commit(component):
                click.secho(
                    f"The last commit of {component} is not a release commit. "
                    "Please make sure you have the release commit checked out.",
                    fg="red",
                )
                sys.exit(1)

    # parse commit range if provided
    start_release = None
    end_release = None
    if commit_range:
        if ".." not in commit_range:
            click.secho(
                f"Invalid commit range format: {commit_range}. Expected format: START..END",
                fg="red",
            )
            sys.exit(1)
        start_release, end_release = commit_range.split("..", 1)

    # get all the versions of the components as they were when the previous REANA version was released
    if start_release:
        prev_versions = get_previous_versions_from_release_tag(
            start_release, changelog_components, {"reana-client": previous_reana_client}
        )
    else:
        prev_versions = get_previous_versions(
            changelog_components, {"reana-client": previous_reana_client}
        )

    # get current versions - either from end_release tag or from source files
    if end_release:
        # don't pass override for end release - get actual versions from the tag
        current_versions = get_previous_versions_from_release_tag(
            end_release, changelog_components, {}
        )
    else:
        current_versions = {}
        for component in changelog_components:
            current_versions[component] = (
                get_current_component_version_from_source_files(component)
            )

    aggregated_changelog_lines = []
    for component in changelog_components:
        prev_version = prev_versions[component]
        current_version = current_versions[component]

        # skip components that don't exist in both releases
        if prev_version is None and current_version is None:
            click.secho(
                f"Skipping {component}: not present in the specified release range.",
                fg="yellow",
            )
            continue

        # fallback to source files if current version not in end release
        if current_version is None:
            current_version = get_current_component_version_from_source_files(component)

        if prev_version is None:
            # new component not present in the previous release, get all tags
            versions_to_add = set(
                run_command(
                    "git tag --merged",
                    component,
                    return_output=True,
                ).splitlines()
            )
        else:
            # get all tags reachable from latest release but not part of previous REANA release
            versions_to_add = set(
                run_command(
                    f"git tag --no-merged {prev_version} --merged",
                    component,
                    return_output=True,
                ).splitlines()
            )

        # also add current version, as it might not be tagged yet
        if current_version != prev_version:
            versions_to_add.add(current_version)

        if commit_range:
            # use cog to generate changelog for alpha releases
            changelog_lines = generate_changelog_with_cog(
                component, prev_version, current_version, commit_types
            )
        else:
            # try to get changelog from CHANGELOG.md
            changelog_lines = get_formatted_changelog_lines(component, versions_to_add)
            if not changelog_lines:
                # fallback to cog if CHANGELOG.md doesn't have the versions
                changelog_lines = generate_changelog_with_cog(
                    component, prev_version, current_version, commit_types
                )

        aggregated_changelog_lines += changelog_lines
        aggregated_changelog_lines += ["\n"]

    current_reana_version = current_versions.get(
        "reana"
    ) or get_current_component_version_from_source_files("reana")

    # add headers
    aggregated_changelog_lines = [
        f"### :sparkles: What's new in REANA {current_reana_version}\n",
        "\n",
        "TODO: copy here the blog post introduction + link to blog post\n",
        "\n",
        f"### :zap: Detailed changelog for REANA {current_reana_version} components\n",
        "\n",
    ] + aggregated_changelog_lines

    if commit_range:
        # print to stdout so user can redirect to any file
        click.echo("".join(aggregated_changelog_lines))
    else:
        substitute_version_changelog(
            "reana", current_reana_version, aggregated_changelog_lines
        )


def _run_graphql(query, variables=None):
    """Execute a GitHub GraphQL query via gh CLI and return the response data.

    :param query: GraphQL query or mutation string.
    :param variables: Optional dict of GraphQL variables.
    :raises SystemExit: on API error or non-zero exit code.
    :return: Parsed ``data`` field from the GraphQL response.
    :rtype: dict
    """
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "--input", "-"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        click.secho(f"GitHub GraphQL API error: {err.stderr}", fg="red")
        sys.exit(1)
    data = json.loads(result.stdout)
    if "errors" in data:
        for error in data["errors"]:
            click.secho(f"GraphQL error: {error.get('message', error)}", fg="red")
        sys.exit(1)
    return data["data"]


def _find_project_number_by_name(org, name):
    """Return the project number whose title matches *name* exactly.

    Scans all Projects V2 in *org* to detect ambiguous titles. GitHub allows
    multiple projects to share the same title; in that case the user must
    pass the numeric project number to disambiguate, since picking the first
    match could silently target the wrong project for this destructive
    command.

    :param org: GitHub organisation login.
    :param name: Exact project title to look for.
    :raises SystemExit: when no matching project is found, or when more than
        one project shares the title.
    :return: Project number.
    :rtype: int
    """
    query = """
    query($org: String!, $cursor: String) {
      organization(login: $org) {
        projectsV2(first: 50, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { number title }
        }
      }
    }
    """
    matches = []
    cursor = None
    while True:
        variables = {"org": org}
        if cursor:
            variables["cursor"] = cursor
        data = _run_graphql(query, variables)
        projects = data["organization"]["projectsV2"]
        for project in projects["nodes"]:
            if project["title"] == name:
                matches.append(project["number"])
        if not projects["pageInfo"]["hasNextPage"]:
            break
        cursor = projects["pageInfo"]["endCursor"]
    if not matches:
        click.secho(f"Project '{name}' not found in organisation {org}.", fg="red")
        sys.exit(1)
    if len(matches) > 1:
        numbers = ", ".join(str(n) for n in matches)
        click.secho(
            f"Multiple projects in {org} are titled '{name}' (numbers: {numbers}). "
            f"Re-run with --project NUMBER to disambiguate.",
            fg="red",
        )
        sys.exit(1)
    return matches[0]


def _get_project_info(org, project_number):
    """Return project id and fields for a GitHub Projects V2 project.

    :param org: GitHub organisation login.
    :param project_number: Project number within the organisation.
    :return: Project node with ``id`` and ``fields``.
    :rtype: dict
    """
    query = """
    query($org: String!, $number: Int!) {
      organization(login: $org) {
        projectV2(number: $number) {
          id
          fields(first: 100) {
            nodes {
              ... on ProjectV2Field { id name }
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
              ... on ProjectV2IterationField {
                id
                name
                configuration {
                  iterations { id title startDate duration }
                  completedIterations { id title startDate duration }
                }
              }
            }
          }
        }
      }
    }
    """
    data = _run_graphql(query, {"org": org, "number": project_number})
    project = data["organization"]["projectV2"]
    if not project:
        click.secho(
            f"Project #{project_number} not found in organisation {org}.", fg="red"
        )
        sys.exit(1)
    return project


def _get_project_items_page(project_id, iter_field_name, status_field_name, after=None):
    """Fetch one page of items from a GitHub Projects V2 project.

    Each item node contains ``statusValue`` (the single-select value for
    *status_field_name*) and ``iterValue`` (the iteration value for
    *iter_field_name*), queried by name to avoid fieldValues connection
    truncation. Both field names must match the project's actual casing —
    ``fieldValueByName`` is case-sensitive.

    :param project_id: Node ID of the project.
    :param iter_field_name: Name of the iteration field.
    :param status_field_name: Name of the Status single-select field.
    :param after: Pagination cursor (``endCursor`` from a previous page).
    :return: ``items`` connection dict with ``pageInfo`` and ``nodes``.
    :rtype: dict
    """
    query = """
    query($id: ID!, $iterFieldName: String!, $statusFieldName: String!, $after: String) {
      node(id: $id) {
        ... on ProjectV2 {
          items(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              content {
                ... on Issue {
                  number
                  title
                  repository { name }
                }
                ... on PullRequest {
                  number
                  title
                  repository { name }
                }
              }
              statusValue: fieldValueByName(name: $statusFieldName) {
                ... on ProjectV2ItemFieldSingleSelectValue { optionId }
              }
              iterValue: fieldValueByName(name: $iterFieldName) {
                ... on ProjectV2ItemFieldIterationValue { iterationId }
              }
            }
          }
        }
      }
    }
    """
    variables = {
        "id": project_id,
        "iterFieldName": iter_field_name,
        "statusFieldName": status_field_name,
    }
    if after:
        variables["after"] = after
    data = _run_graphql(query, variables)
    return data["node"]["items"]


def _update_item_iteration(project_id, item_id, field_id, iteration_id):
    """Update the iteration field value of a GitHub Projects V2 item.

    :param project_id: Node ID of the project.
    :param item_id: Node ID of the project item.
    :param field_id: Node ID of the iteration field.
    :param iteration_id: ID of the target iteration.
    """
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $iterationId: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: { iterationId: $iterationId }
      }) {
        projectV2Item { id }
      }
    }
    """
    _run_graphql(
        mutation,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "iterationId": iteration_id,
        },
    )


def _parse_issue_filter(issue):
    """Parse the ``--issue`` option into ``(repo, number)`` components.

    :param issue: Raw option value, must be ``"REPO#NUMBER"`` e.g. ``"reana-server#123"``.
    :return: Tuple of ``(repo_name, issue_number)``, or ``(None, None)`` when *issue* is falsy.
    :rtype: tuple
    :raises click.ClickException: If the value is not in ``REPO#NUMBER`` format.
    """
    if not issue:
        return None, None
    if "#" not in issue:
        raise click.ClickException(
            f"--issue requires REPO#NUMBER format (e.g. reana-server#123), got: {issue!r}"
        )
    repo_part, num_part = issue.split("#", 1)
    repo_part = repo_part.strip()
    num_part = num_part.strip()
    if not repo_part:
        raise click.ClickException(
            f"--issue requires a repository name before '#', got: {issue!r}"
        )
    try:
        return repo_part, int(num_part)
    except ValueError:
        raise click.ClickException(
            f"--issue requires an integer issue number after '#', got: {issue!r}"
        )


def _resolve_project_number(org, project):
    """Return a numeric project number, looking up by name when necessary.

    :param org: GitHub organisation login.
    :param project: Project name or number string.
    :return: Project number.
    :rtype: int
    """
    try:
        return int(project)
    except ValueError:
        return _find_project_number_by_name(org, project)


def _find_iteration_field(fields):
    """Return the first iteration field found in *fields*, or exit.

    :param fields: List of project field nodes from the GraphQL response.
    :return: Iteration field node.
    :rtype: dict
    """
    iteration_field = None
    for field in fields:
        if "configuration" not in field or "iterations" not in field["configuration"]:
            continue
        if iteration_field is None:
            iteration_field = field
        else:
            click.secho(
                f"Warning: multiple iteration fields found, using '{iteration_field['name']}'.",
                fg="yellow",
            )
            break
    if not iteration_field:
        click.secho("No iteration field found in this project.", fg="red")
        sys.exit(1)
    return iteration_field


def _resolve_source_iteration(iteration_field, from_iteration):
    """Return the source iteration node, auto-detecting if *from_iteration* is None.

    Auto-detection picks the most recently completed iteration.

    :param iteration_field: Iteration field node from the GraphQL response.
    :param from_iteration: Explicit iteration title, or ``None`` to auto-detect.
    :return: Iteration node with ``id``, ``title``, and ``startDate``.
    :rtype: dict
    """
    completed = iteration_field["configuration"]["completedIterations"]
    active = iteration_field["configuration"]["iterations"]
    if from_iteration:
        match = next(
            (i for i in completed if i["title"] == from_iteration), None
        ) or next((i for i in active if i["title"] == from_iteration), None)
        if not match:
            click.secho(f"Iteration '{from_iteration}' not found in project.", fg="red")
            sys.exit(1)
        return match
    if not completed:
        click.secho(
            "No completed iterations found. Please specify --from explicitly.",
            fg="red",
        )
        sys.exit(1)
    return max(completed, key=lambda i: i["startDate"])


def _resolve_target_iteration(iteration_field, to_iteration):
    """Return the target iteration node, auto-detecting if *to_iteration* is None.

    Auto-detection picks the earliest active (current) iteration.

    :param iteration_field: Iteration field node from the GraphQL response.
    :param to_iteration: Explicit iteration title, or ``None`` to auto-detect.
    :return: Iteration node with ``id``, ``title``, and ``startDate``.
    :rtype: dict
    """
    active = iteration_field["configuration"]["iterations"]
    if to_iteration:
        match = next((i for i in active if i["title"] == to_iteration), None)
        if not match:
            click.secho(
                f"Iteration '{to_iteration}' not found among active iterations.",
                fg="red",
            )
            sys.exit(1)
        return match
    if not active:
        click.secho(
            "No active iterations found. Please specify --to explicitly.", fg="red"
        )
        sys.exit(1)
    return min(active, key=lambda i: i["startDate"])


def _get_status_field_info(fields):
    """Return the Status field's exact name and its "Done" option IDs.

    Detects the field with a case-insensitive match on ``"status"`` but
    returns the project's actual (case-sensitive) field name, so the per-item
    GraphQL query in :func:`_get_project_items_page` can use the same name
    and avoid casing mismatches against ``fieldValueByName``.

    :param fields: List of project field nodes from the GraphQL response.
    :return: Tuple of ``(status_field_name, done_option_ids)``.
    :rtype: tuple[str, set]
    :raises click.ClickException: If the Status field or its Done option is not found.
    """
    for field in fields:
        if field.get("name", "").lower() == "status" and "options" in field:
            done_ids = {
                opt["id"] for opt in field["options"] if opt["name"].lower() == "done"
            }
            if not done_ids:
                raise click.ClickException(
                    "Project Status field has no 'Done' option. "
                    "Cannot determine which items to skip."
                )
            return field["name"], done_ids
    raise click.ClickException(
        "Project has no 'Status' field with options. "
        "Cannot determine which items are done."
    )


def _fetch_all_project_items(project_id, iter_field_name, status_field_name):
    """Fetch every item in a project, following pagination.

    :param project_id: Node ID of the GitHub Projects V2 project.
    :param iter_field_name: Name of the iteration field, used to query each item's value.
    :param status_field_name: Name of the Status field, used to query each item's value.
    :return: List of item nodes.
    :rtype: list
    """
    click.secho("Loading project items, this may take a moment...", fg="cyan")
    items = []
    cursor = None
    while True:
        page = _get_project_items_page(
            project_id, iter_field_name, status_field_name, cursor
        )
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return items


def _diagnose_issue_filter(
    all_items, issue_repo, issue_number, prev_iter, iteration_title_by_id
):
    """Diagnose a ``--issue`` filter that would yield an empty migration.

    When ``--issue`` is set the user expects a single specific item to be
    rolled over, so silently performing no work and reporting "no items
    found" hides the real failure. This helper inspects *all_items* before
    the migration loop runs and exits non-zero with a specific diagnostic in
    the three corner cases the user is likely to hit (typo, item left
    unassigned, or item in a different iteration). Returns silently when the
    requested item is in the source iteration, in which case the normal
    migration loop handles it (including the Done-skip case).

    :param all_items: List of item nodes from :func:`_fetch_all_project_items`.
    :param issue_repo: Repository name from ``--issue``.
    :param issue_number: Item number from ``--issue``.
    :param prev_iter: Source iteration node.
    :param iteration_title_by_id: Map from iteration ID to iteration title,
        built from the iteration field's ``iterations`` and
        ``completedIterations`` configuration.
    :raises SystemExit: When the item is not in the project, is unassigned to
        any iteration, or is in a different iteration than *prev_iter*.
    """
    matching = None
    for item in all_items:
        content = item.get("content")
        if not content:
            continue
        if (
            content.get("number") == issue_number
            and content.get("repository", {}).get("name", "") == issue_repo
        ):
            matching = item
            break
    if matching is None:
        click.secho(
            f"Item {issue_repo}#{issue_number} is not in this project.", fg="red"
        )
        sys.exit(1)
    item_iter_id = (matching.get("iterValue") or {}).get("iterationId")
    if item_iter_id is None:
        click.secho(
            f"Item {issue_repo}#{issue_number} is not assigned to any iteration.",
            fg="red",
        )
        sys.exit(1)
    if item_iter_id != prev_iter["id"]:
        actual_title = iteration_title_by_id.get(item_iter_id, "(unknown)")
        click.secho(
            f"Item {issue_repo}#{issue_number} is in iteration '{actual_title}', "
            f"not '{prev_iter['title']}'. Use --from '{actual_title}' to roll it over.",
            fg="red",
        )
        sys.exit(1)


def _migrate_items(
    all_items,
    project_id,
    prev_iter,
    curr_iter,
    iteration_field_id,
    done_option_ids,
    issue_number,
    issue_repo,
    dry_run,
):
    """Iterate over *all_items*, moving those in *prev_iter* to *curr_iter*.

    Each item is expected to carry ``statusValue`` and ``iterValue`` keys as
    returned by :func:`_get_project_items_page`. Items whose Status is Done
    are skipped. Returns counts of moved and skipped items.

    :return: ``(moved_count, skipped_count)``
    :rtype: tuple[int, int]
    """
    moved_count = 0
    skipped_count = 0

    for item in all_items:
        content = item.get("content")
        if not content:
            continue

        item_number = content.get("number")
        item_repo = content.get("repository", {}).get("name", "")
        item_title = content.get("title", "")

        if issue_number is not None:
            if item_number != issue_number or item_repo != issue_repo:
                continue

        item_iter_id = (item.get("iterValue") or {}).get("iterationId")
        item_status_option_id = (item.get("statusValue") or {}).get("optionId")

        if item_iter_id != prev_iter["id"]:
            continue

        label = f"{item_repo}#{item_number} — {item_title}"

        if item_status_option_id in done_option_ids:
            click.secho(f"  Skipping (Done): {label}", fg="blue")
            skipped_count += 1
            continue

        if dry_run:
            click.secho(f"  Would move: {label}", fg="yellow")
        else:
            _update_item_iteration(
                project_id, item["id"], iteration_field_id, curr_iter["id"]
            )
            click.secho(f"  Moved: {label}", fg="green")
        moved_count += 1

    return moved_count, skipped_count


@git_commands.command(name="git-iteration-rollover")
@click.option(
    "--project",
    "-p",
    required=True,
    help="GitHub Projects V2 project name or number.",
)
@click.option(
    "--from",
    "from_iteration",
    default=None,
    help="Title of the source iteration to move items from. "
    "Auto-detected as the most recently completed iteration if not provided.",
)
@click.option(
    "--to",
    "to_iteration",
    default=None,
    help="Title of the target iteration to move items to. "
    "Auto-detected as the first active iteration if not provided.",
)
@click.option(
    "--issue",
    "-i",
    default=None,
    help="Move only this specific issue or PR. "
    "Format: REPO#NUMBER (e.g. reana-server#123).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be moved without making any changes.",
)
def git_iteration_rollover(project, from_iteration, to_iteration, issue, dry_run):
    r"""Move issues/PRs from the previous iteration to the current one.

    Fetches all items assigned to the previous GitHub Project iteration and
    reassigns them to the current iteration, preserving each item's Status
    column value (Backlog, Ready for work, In work, etc.). Items in the
    Done column are skipped.

    The source iteration is auto-detected as the most recently completed
    iteration; the target is auto-detected as the first active one.
    Use ``--from`` and ``--to`` to override.

    Use ``--issue`` to move a single specific issue or pull request instead of
    all items.

    \b
    :param project: GitHub Projects V2 project name or number (required).
    :param from_iteration: Source iteration title. [auto-detected]
    :param to_iteration: Target iteration title. [auto-detected]
    :param issue: Move only REPO#NUMBER (e.g. reana-server#123). [all items]
    :param dry_run: Show what would be moved without making changes. [default=False]
    :type project: str
    :type from_iteration: str
    :type to_iteration: str
    :type issue: str
    :type dry_run: bool
    """
    org = "reanahub"
    issue_repo, issue_number = _parse_issue_filter(issue)
    project_number = _resolve_project_number(org, project)
    project_info = _get_project_info(org, project_number)

    fields = project_info["fields"]["nodes"]
    iteration_field = _find_iteration_field(fields)
    prev_iter = _resolve_source_iteration(iteration_field, from_iteration)
    curr_iter = _resolve_target_iteration(iteration_field, to_iteration)

    click.secho(
        f"Source iteration : {prev_iter['title']} (started {prev_iter['startDate']})",
        fg="cyan",
    )
    click.secho(
        f"Target iteration : {curr_iter['title']} (started {curr_iter['startDate']})",
        fg="cyan",
    )
    if dry_run:
        click.secho("Dry run — no changes will be made.", fg="yellow")

    status_field_name, done_option_ids = _get_status_field_info(fields)
    all_items = _fetch_all_project_items(
        project_info["id"], iteration_field["name"], status_field_name
    )

    if issue_number is not None:
        iteration_title_by_id = {
            i["id"]: i["title"]
            for i in iteration_field["configuration"]["iterations"]
            + iteration_field["configuration"]["completedIterations"]
        }
        _diagnose_issue_filter(
            all_items, issue_repo, issue_number, prev_iter, iteration_title_by_id
        )

    moved_count, skipped_count = _migrate_items(
        all_items=all_items,
        project_id=project_info["id"],
        prev_iter=prev_iter,
        curr_iter=curr_iter,
        iteration_field_id=iteration_field["id"],
        done_option_ids=done_option_ids,
        issue_number=issue_number,
        issue_repo=issue_repo,
        dry_run=dry_run,
    )

    if moved_count == 0 and skipped_count == 0:
        click.secho(f"No items found in iteration '{prev_iter['title']}'.", fg="yellow")
    else:
        verb = "Would move" if dry_run else "Moved"
        click.secho(
            f"{verb} {moved_count} item(s) to '{curr_iter['title']}'"
            + (f", skipped {skipped_count} Done item(s)." if skipped_count else "."),
            fg="cyan",
            bold=True,
        )


git_commands_list = list(git_commands.commands.values())
