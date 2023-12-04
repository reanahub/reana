# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s git commands."""

import os
import subprocess
import sys
from typing import Optional

import click

from reana.config import (
    COMPONENTS_USING_SHARED_MODULE_COMMONS,
    COMPONENTS_USING_SHARED_MODULE_DB,
    GIT_DEFAULT_BASE_BRANCH,
    HELM_VERSION_FILE,
    JAVASCRIPT_VERSION_FILE,
    OPENAPI_VERSION_FILE,
    PYTHON_REQUIREMENTS_FILE,
    PYTHON_VERSION_FILE,
    REPO_LIST_ALL,
    REPO_LIST_PYTHON_REQUIREMENTS,
    REPO_LIST_SHARED,
)
from reana.reana_dev.utils import (
    bump_component_version,
    bump_pep440_version,
    bump_semver2_version,
    click_add_git_base_branch_option,
    display_message,
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
        if version_files.get(HELM_VERSION_FILE):
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
            HELM_VERSION_FILE in version_files
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
    if "release:" in get_current_commit(get_srcdir(component)):
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

    run_command(
        f"git commit -m 'release: {next_version}' {'--allow-empty' if not modified_files else ''}",
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
    return current_commit.split()[1] == "release:"


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
                "rsync -az ../reana-commons modules",
            ]:
                run_command(cmd, component)
        for component in COMPONENTS_USING_SHARED_MODULE_DB:
            for cmd in [
                "rsync -az ../reana-db modules",
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
        for c in components:
            commit_cmd = 'git commit -m "installation: bump shared modules"'
            if amend:
                commit_cmd = "git commit --amend --no-edit"

            files_to_commit = ["setup.py"]
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
            run_command(
                'git commit -m "installation: bump all dependencies"', component
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


git_commands_list = list(git_commands.commands.values())
