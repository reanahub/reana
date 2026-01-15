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
)


def get_all_branches(srcdir):
    """Return all local and remote Git branch names in the given directory.

    :param srcdir: source code directory
    :type srcdir: str

    :return: checkout out branch in the component source code directory
    :rtype: str
    """
    os.chdir(srcdir)
    return (
        subprocess.check_output("git branch -a 2>/dev/null", shell=True)
        .decode()
        .split()
    )


def branch_exists(component, branch):
    """Check whether a branch exists on a given component.

    :param component: Component in which check whether the branch exists.
    :param branch: Name of the branch.
    :return: Whether the branch exists in components git repo.
    :rtype: bool
    """
    return branch in get_all_branches(get_srcdir(component))


def get_current_branch(srcdir):
    """Return current Git branch name checked out in the given directory.

    :param srcdir: source code directory
    :type srcdir: str

    :return: checkout out branch in the component source code directory
    :rtype: str
    """
    os.chdir(srcdir)
    return (
        subprocess.check_output(
            'git branch 2>/dev/null | grep "^*" | colrm 1 2', shell=True
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
    os.chdir(srcdir)
    return (
        subprocess.check_output('git log --pretty=format:"%h %s" -n 1', shell=True)
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
        if version_files.get(DOCKER_VERSION_FILE):
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


def compare_branches(branch_to_compare, current_branch):
    """Compare two branches with ``git rev-list``."""
    cmd = "git branch -a | grep -c remotes/{}".format(branch_to_compare)
    try:
        check = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError:
        check = 0
    if check == 0:
        click.secho(
            "ERROR: Branch {} does not exist.".format(branch_to_compare), fg="red"
        )
        return 0, 0

    cmd = "git rev-list --left-right --count {0}...{1}".format(
        branch_to_compare, current_branch
    )
    behind, ahead = [
        int(x) for x in run_command(cmd, display=False, return_output=True).split()
    ]
    return behind, ahead


def is_component_behind_branch(
    component,
    branch_to_compare,
    current_branch=None,
):
    """Report to stdout the differences between two branches."""
    current_branch = current_branch or get_current_branch(get_srcdir(component))
    behind, _ = compare_branches(branch_to_compare, current_branch)
    return bool(behind)


def print_branch_difference_report(
    component,
    branch_to_compare,
    current_branch=None,
    base=GIT_DEFAULT_BASE_BRANCH,
    commit=None,
    short=False,
):
    """Report to stdout the differences between two branches."""
    # detect how far it is ahead/behind from pr/origin/upstream
    current_branch = current_branch or get_current_branch(get_srcdir(component))
    commit = commit or get_current_commit(get_srcdir(component))
    report = ""
    behind, ahead = compare_branches(branch_to_compare, current_branch)
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
        behind, ahead = compare_branches(branch_to_compare, current_branch)
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
        current_branch = get_current_branch(get_srcdir(component))
        # detect all local and remote branches
        all_branches = get_all_branches(get_srcdir(component))
        # detect branch to compare against
        if current_branch == base:  # base branch
            branch_to_compare = "upstream/" + base
        elif current_branch.startswith("pr-"):  # other people's PR
            branch_to_compare = "upstream/" + current_branch.replace("pr-", "pr/")
        else:
            branch_to_compare = "origin/" + current_branch  # my PR
            if "remotes/" + branch_to_compare not in all_branches:
                branch_to_compare = "origin/" + base  # local unpushed branch
        print_branch_difference_report(
            component, branch_to_compare, base=base, short=short
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


@click.option(
    "--branch", "-b", nargs=2, multiple=True, help="Which PR? [component PR#]"
)
@click.option("--fetch", is_flag=True, default=False)
@git_commands.command(name="git-checkout-pr")
def git_checkout_pr(branch, fetch):  # noqa: D301
    """Check out local branch corresponding to a component pull request.

    The ``-b`` option can be repetitive to check out several pull requests in
    several repositories at the same time.

    \b
    :param branch: The option ``branch`` can be repeated. The value consist of
                   two strings specifying the component name and the pull
                   request number. For example, ``-b reana-workflow-controller
                   72`` will create a local branch called ``pr-72`` in the
                   reana-workflow-controller source code directory.
    :param fetch: Should we fetch latest upstream first? [default=False]
    :type branch: list
    :type fetch: bool
    """
    for cpr in branch:
        component, pull_request = cpr
        component = select_components(
            [
                component,
            ]
        )[0]
        if component in REPO_LIST_ALL:
            if fetch:
                cmd = "git fetch upstream"
                run_command(cmd, component)
            cmd = "git checkout -b pr-{0} upstream/pr/{0}".format(pull_request)
            run_command(cmd, component)
        else:
            msg = "Ignoring unknown component."
            display_message(msg, component)


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
@git_commands.command(name="git-fetch")
def git_fetch(component, exclude_components):  # noqa: D301
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
    :type component: str
    :type exclude_components: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    for component in select_components(component, exclude_components):
        cmd = "git fetch upstream"
        run_command(cmd, component)


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
@git_commands.command(name="git-upgrade")
@click_add_git_base_branch_option
def git_upgrade(component, exclude_components, base):  # noqa: D301
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
    :param base: Against which git base branch are we working on? [default=master]
    :type component: str
    :type exclude_components: str
    :type base: str
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        if not branch_exists(component, base):
            display_message(
                "Missing branch {}, skipping.".format(base), component=component
            )
            continue
        for cmd in [
            "git fetch upstream",
            "git checkout {0}".format(base),
            "git merge --ff-only upstream/{0}".format(base),
            "git push origin {0}".format(base),
            "git checkout -",
        ]:
            run_command(cmd, component)


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


def generate_changelog_with_cog(
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
def get_aggregate_changelog(
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


git_commands_list = list(git_commands.commands.values())
