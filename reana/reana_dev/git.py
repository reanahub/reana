# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s git commands."""

import datetime
import os
import sys
import subprocess

import click

from reana.config import (
    COMPONENTS_USING_SHARED_MODULE_COMMONS,
    COMPONENTS_USING_SHARED_MODULE_DB,
    REPO_LIST_ALL,
    REPO_LIST_SHARED,
)
from reana.reana_dev.utils import (
    display_message,
    get_srcdir,
    run_command,
    select_components,
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
    "--browser", "-b", default="firefox", help="Which browser to use? [firefox]"
)
@git_commands.command(name="git-fork")
def git_fork(component, browser):  # noqa: D301
    """Display commands to fork REANA source code repositories on GitHub.

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
    :param browser: The web browser to use. [default=firefox]
    :type component: str
    :type browser: str
    """
    components = select_components(component)
    if components:
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
        cmd = "{0} https://github.com/reanahub/{1}/fork;".format(browser, component)
        click.echo(cmd)
    click.echo(
        'echo "Please continue the fork process in the opened' ' browser windows."'
    )


@click.option("--user", "-u", default="anonymous", help="GitHub user name [anonymous]")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@git_commands.command(name="git-clone")
def git_clone(user, component):  # noqa: D301
    """Clone REANA source repositories from GitHub.

    If the ``user`` argument is provided, the ``origin`` will be cloned from
    the user repository on GitHub and the ``upstream`` will be set to
    ``reanahub`` organisation. Useful for setting up personal REANA development
    environment,

    If the ``user`` argument is not provided, the cloning will be done in
    anonymous manner from ``reanahub`` organisation. Also, the clone will be
    shallow to save disk space and CPU time. Useful for CI purposes.

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
    :param user: The GitHub user name. [default=anonymous]
    :type component: str
    :type user: str

    """
    components = select_components(component)
    for component in components:
        os.chdir(get_srcdir())
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
                run_command(cmd, component)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--short",
    "-s",
    is_flag=True,
    default=False,
    help="Show git status short format details?",
)
@git_commands.command(name="git-status")
def git_status(component, short):  # noqa: D301
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
    :param verbose: Show git status details? [default=False]
    :type component: str
    """
    components = select_components(component)
    for component in components:
        # detect current branch and commit
        branch = get_current_branch(get_srcdir(component))
        commit = get_current_commit(get_srcdir(component))
        # detect all local and remote branches
        all_branches = get_all_branches(get_srcdir(component))
        # detect branch to compare against
        if branch == "master":  # master
            branch_to_compare = "upstream/master"
        elif branch.startswith("pr-"):  # other people's PR
            branch_to_compare = "upstream/" + branch.replace("pr-", "pr/")
        else:
            branch_to_compare = "origin/" + branch  # my PR
            if "remotes/" + branch_to_compare not in all_branches:
                branch_to_compare = "origin/master"  # local unpushed branch
        # detect how far it is ahead/behind from pr/origin/upstream
        report = ""
        cmd = "git rev-list --left-right --count {0}...{1}".format(
            branch_to_compare, branch
        )
        behind, ahead = [
            int(x) for x in run_command(cmd, display=False, return_output=True).split()
        ]
        if ahead or behind:
            report += "("
            if ahead:
                report += "{0} AHEAD ".format(ahead)
            if behind:
                report += "{0} BEHIND ".format(behind)
            report += branch_to_compare + ")"
        # detect rebase needs for local branches and PRs
        if branch_to_compare != "upstream/master":
            branch_to_compare = "upstream/master"
            cmd = "git rev-list --left-right --count {0}...{1}".format(
                branch_to_compare, branch
            )
            behind, ahead = [
                int(x)
                for x in run_command(cmd, display=False, return_output=True).split()
            ]
            if behind:
                report += "(STEMS FROM "
                if behind:
                    report += "{0} BEHIND ".format(behind)
                report += branch_to_compare + ")"
        # print branch information
        click.secho("{0}".format(component), nl=False, bold=True)
        click.secho(" @ ", nl=False, dim=True)
        if branch == "master":
            click.secho("{0}".format(branch), nl=False)
        else:
            click.secho("{0}".format(branch), nl=False, fg="green")
        if report:
            click.secho(" {0}".format(report), nl=False, fg="red")
        click.secho(" @ ", nl=False, dim=True)
        click.secho("{0}".format(commit))
        # optionally, display also short status
        if short:
            cmd = "git status --short"
            run_command(cmd, component, display=False)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@git_commands.command(name="git-clean")
def git_clean(component):  # noqa: D301
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
    :type component: str
    """
    components = select_components(component)
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
@git_commands.command(name="git-branch")
def git_branch(component):  # noqa: D301
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
    :type component: str
    """
    for component in select_components(component):
        cmd = "git branch -vv"
        run_command(cmd, component)


@click.option(
    "--branch", "-b", nargs=2, multiple=True, help="Which PR? [number component]"
)
@click.option("--fetch", is_flag=True, default=False)
@git_commands.command(name="git-checkout")
def git_checkout(branch, fetch):  # noqa: D301
    """Check out local branch corresponding to a component pull request.

    The ``-b`` option can be repetitive to check out several pull requests in
    several repositories at the same time.

    \b
    :param branch: The option ``branch`` can be repeated. The value consist of
                   two strings specifying the component name and the pull
                   request number. For example, ``-b reana-workflow-controler
                   72`` will create a local branch called ``pr-72`` in the
                   reana-workflow-controller source code directory.
    :param fetch: Should we fetch latest upstream first? [default=False]
    :type component: str
    :type fetch: bool
    """
    for cpr in branch:
        component, pull_request = cpr
        component = select_components([component,])[0]
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
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@git_commands.command(name="git-fetch")
def git_fetch(component):  # noqa: D301
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
    :type component: str
    """
    for component in select_components(component):
        cmd = "git fetch upstream"
        run_command(cmd, component)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@git_commands.command(name="git-upgrade")
def git_upgrade(component):  # noqa: D301
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
    :type component: str
    """
    for component in select_components(component):
        for cmd in [
            "git fetch upstream",
            "git checkout master",
            "git merge --ff-only upstream/master",
            "git push origin master",
            "git checkout -",
        ]:
            run_command(cmd, component)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option("--number", "-n", default=6, help="Number of commits to output [6]")
@click.option("--all", is_flag=True, default=False, help="Show all references?")
@git_commands.command(name="git-log")
def git_log(component, number, all):  # noqa: D301
    """Show commit logs in given component repositories.

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
    :param number: The number of commits to output. [6]
    :param all: Show all references? [6]
    :type component: str
    :type number: int
    :type all: bool
    """
    for component in select_components(component):
        cmd = (
            "git log -n {0} --graph --decorate"
            ' --pretty=format:"%C(blue)%d%Creset'
            " %C(yellow)%h%Creset %s, %C(bold green)%an%Creset,"
            ' %C(green)%cd%Creset" --date=relative'.format(number)
        )
        if all:
            cmd += " --all"
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
@git_commands.command(name="git-diff")
def git_diff(component):  # noqa: D301
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
    :type component: str
    """
    for component in select_components(component):
        for cmd in [
            "git diff master",
        ]:
            run_command(cmd, component)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER]",
)
@git_commands.command(name="git-push")
def git_push(component):  # noqa: D301
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
    :type component: str
    """
    components = select_components(component)
    for component in components:
        for cmd in ["git push origin master"]:
            run_command(cmd, component)


@git_commands.command(name="git-shared-modules-upgrade")
@click.option(
    "--commit-and-publish",
    is_flag=True,
    default=False,
    help="Should the changes be committed and pull requests created?"
    " If so, a commit and a PR with"
    ' "installation: shared packages version bump" message will'
    " be created for all affected CLUSTER components.",
)
def git_shared_modules_upgrade(commit_and_publish):
    """Upgrade all cluster components to latest REANA-Commons version."""

    def _fetch_latest_pypi_version(package):
        """Fetch latest released version of a package."""
        import requests

        pypi_rc_info = requests.get(
            "https://pypi.python.org/pypi/{}/json".format(package)
        )
        return sorted(pypi_rc_info.json()["releases"].keys())[-1]

    def _update_module_in_cluster_components(module, new_version):
        """Update the specified module version in all affected components."""
        components_to_update = {
            "reana-commons": COMPONENTS_USING_SHARED_MODULE_COMMONS,
            "reana-db": COMPONENTS_USING_SHARED_MODULE_DB,
        }
        for component in components_to_update[module]:
            update_setup_py_dep_cmd = (
                'LN=`cat setup.py | grep -n -e "{module}.*>=" | cut -f1 -d: `'
                '&& sed -i.bk "`echo $LN`s/>=.*,</>={new_version},</" '
                "setup.py && rm setup.py.bk".format(
                    module=module, new_version=new_version
                )
            )
            run_command(update_setup_py_dep_cmd, component)

    def _commit_and_publish_version_bumps(components):
        """Create commit and version bump PRs for all specified components."""
        for component in components:
            has_changes = run_command(
                "git status --porcelain --untracked-files=no | "
                "grep setup.py || echo",
                component=component,
                return_output=True,
            )
            if has_changes:
                branch_name = datetime.datetime.now().strftime("version-bump-%Y%m%d")
                create_branch = "git checkout -b {}".format(branch_name)
                run_command(create_branch, component)
                create_commit = (
                    "git add setup.py && "
                    "git commit "
                    '-m "installation: shared packages version bump"'
                )
                run_command(create_commit, component)
                create_pr = "hub pull-request -p --no-edit && hub pr list -L 1"
                run_command(create_pr, component)
            else:
                click.echo("{} has no changes, skipping.".format(component))

    cluster_components_with_shared_modules = set(
        COMPONENTS_USING_SHARED_MODULE_DB
    ).union(set(COMPONENTS_USING_SHARED_MODULE_COMMONS))

    for module in REPO_LIST_SHARED:
        last_version = _fetch_latest_pypi_version(module)
        _update_module_in_cluster_components(module, last_version)
        click.secho(
            "✅ {module} updated to: {last_version}".format(
                module=module, last_version=last_version
            ),
            bold=True,
            fg="green",
        )

    if commit_and_publish:
        click.secho("Creating version bump commits and pull requests...")
        _commit_and_publish_version_bumps(cluster_components_with_shared_modules)
        click.secho(
            "\nVersion bump commits and pull requests created ✨", bold=True, fg="green"
        )
        click.secho(
            "PR list 👉  https://github.com/search?q="
            "org%3Areanahub+is%3Apr+is%3Aopen&"
            "unscoped_q=is%3Apr+is%3Aopen",
            fg="green",
        )


git_commands_list = list(git_commands.commands.values())
