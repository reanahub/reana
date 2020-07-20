# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018, 2019, 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Helper scripts for REANA developers. Run `reana-dev --help` for help."""

import base64
import datetime
import json
import logging
import os
import platform
import subprocess
import sys
import time
import traceback
import yaml

import click

from reana.k8s_utils import (
    exec_into_component,
    get_prefixed_component_name,
)

REPO_LIST_DEMO = [
    "reana-demo-helloworld",
    "reana-demo-root6-roofit",
    "reana-demo-worldpopulation",
    "reana-demo-atlas-recast",
]

REPO_LIST_ALL = [
    "docs.reana.io",
    "reana",
    "reana-auth-krb5",
    "reana-auth-vomsproxy",
    "reana-client",
    "reana-commons",
    "reana-db",
    "reana-demo-alice-lego-train-test-run",
    "reana-demo-alice-pt-analysis",
    "reana-demo-bsm-search",
    "reana-demo-cdci-crab-pulsar-integral-verification",
    "reana-demo-cdci-integral-data-reduction",
    "reana-demo-cms-dimuon-mass-spectrum",
    "reana-demo-cms-h4l",
    "reana-demo-cms-reco",
    "reana-demo-lhcb-d2pimumu",
    "reana-env-aliphysics",
    "reana-env-jupyter",
    "reana-env-root6",
    "reana-job-controller",
    "pytest-reana",
    "reana-message-broker",
    "reana-server",
    "reana-ui",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
    "reana-workflow-monitor",
    "www.reana.io",
] + REPO_LIST_DEMO

REPO_LIST_CLIENT = [
    # shared utils
    "pytest-reana",
    "reana-commons",
    "reana-db",
    # client
    "reana-client",
]

REPO_LIST_CLUSTER = [
    # shared utils
    "pytest-reana",
    "reana-commons",
    "reana-db",
    # cluster helpers
    "reana-auth-krb5",
    "reana-auth-vomsproxy",
    # cluster components
    "reana-ui",
    "reana-job-controller",
    "reana-message-broker",
    "reana-server",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
]

REPO_LIST_SHARED = [
    "reana-db",
    "reana-commons",
]

WORKFLOW_ENGINE_LIST_ALL = ["cwl", "serial", "yadage"]

COMPONENT_PODS = {
    "reana-db": "reana-db",
    "reana-message-broker": "reana-message-broker",
    "reana-server": "reana-server",
    "reana-workflow-controller": "reana-workflow-controller",
    "reana-ui": "reana-ui",
}

EXAMPLE_OUTPUT_FILENAMES = {
    "reana-demo-helloworld": ("greetings.txt",),
    "reana-demo-bsm-search": ("prefit.pdf", "postfit.pdf"),
    "reana-demo-alice-lego-train-test-run": ("plot.pdf",),
    "reana-demo-alice-pt-analysis": ("plot_eta.pdf", "plot_pt.pdf"),
    "reana-demo-atlas-recast": ("pre.png", "limit.png", "limit_data.json"),
    "reana-demo-cms-dimuon-mass-spectrum": ("DoubleMu.root",),
    "*": ("plot.png",),
}

EXAMPLE_LOG_MESSAGES = {
    "reana-demo-helloworld": ("Parameters: inputfile=",),
    "reana-demo-root6-roofit": (
        "gendata.C",
        "RooChebychev::bkg",
        "fitdata.C",
        "MIGRAD MINIMIZATION HAS CONVERGED",
    ),
    "reana-demo-worldpopulation": ("Input Notebook", "Output Notebook",),
    "reana-demo-atlas-recast": (
        "MC channel Number",
        "MIGRAD MINIMIZATION HAS CONVERGED",
    ),
    "*": ("job:",),
}

COMPONENTS_USING_SHARED_MODULE_COMMONS = [
    "reana-job-controller",
    "reana-server",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
]

COMPONENTS_USING_SHARED_MODULE_DB = [
    "reana-job-controller",
    "reana-server",
    "reana-workflow-controller",
]

DOCKER_PREFETCH_IMAGES = {
    "reana": [
        "postgres:9.6.2",
        "kozea/wdb:3.2.5",
        "maildev/maildev:1.1.0",
        "redis:5.0.5",
    ],
    "reana-demo-helloworld": ["python:2.7-slim",],
    "reana-demo-worldpopulation": ["reanahub/reana-env-jupyter:1.0.0",],
    "reana-demo-root6-roofit": ["reanahub/reana-env-root6:6.18.04",],
    "reana-demo-atlas-recast": [
        "reanahub/reana-demo-atlas-recast-eventselection:1.0",
        "reanahub/reana-demo-atlas-recast-statanalysis:1.0",
    ],
}

TIMECHECK = 5

TIMEOUT = 300


@click.group()
def cli():  # noqa: D301
    """Run REANA development and integration commands.

    How to prepare your environment:

    .. code-block:: console

        \b
        $ # prepare directory that will hold sources
        $ mkdir -p ~/project/reana/src
        $ cd ~/project/reana/src
        $ # create new virtual environment
        $ virtualenv ~/.virtualenvs/reana
        $ source ~/.virtualenvs/reana/bin/activate
        $ # install reana-dev developer helper script
        $ pip install git+git://github.com/reanahub/reana.git#egg=reana
        $ # run ssh-agent locally to simplify GitHub interaction
        $ eval "$(ssh-agent -s)"
        $ ssh-add ~/.ssh/id_rsa

    How to fork and clone all REANA repositories:

    .. code-block:: console

        \b
        $ reana-dev git-fork -c ALL
        $ eval "$(reana-dev git-fork -c ALL)"
        $ reana-dev git-clone -c ALL -u tiborsimko

    How to run CI tests:

    .. code-block:: console

        \b
        $ # example (a): fast, CLI mode only, fast example
        $ reana-dev cluster-delete
        $ reana-dev run-ci -m /var/reana:/var/reana -c r-d-helloworld --exclude-components=r-ui,r-a-vomsproxy
        $ # example (b): slow, CLI and Web modes, all examples
        $ reana-dev cluster-delete
        $ reana-dev run-ci

    How to create REANA cluster:

    .. code-block:: console

        \b
        $ # example (a): simple cluster creation
        $ reana-dev cluster-create
        $ # example (b): mount sharing /var/reana with host
        $ reana-dev cluster-create -m /var/reana:/var/reana
        $ # example (c): mount sharing /var/reana with host and /cvmfs for jobs
        $ reana-dev cluster-create -m /var/reana:/var/reana -j /cvmfs:/cvmfs
        $ # example (d): debug mode with code sharing as well
        $ reana-dev cluster-create -m /var/reana:/var/reana --mode debug

    How to set up your shell environment variables:

    .. code-block:: console

        \b
        $ eval $(reana-dev client-setup-environment)

    How to run full REANA example using a given workflow engine:

    .. code-block:: console

        \b
        $ reana-dev run-example -c reana-demo-root6-roofit -w serial

    How to run Python unit tests in independent virtual environments:

    .. code-block:: console

        \b
        $ reana-dev python-unit-tests -c r-server -c r-w-controller
        $ reana-dev python-unit-tests -c CLUSTER
        $ reana-dev python-unit-tests -c ALL

    How to test one component pull request:

    .. code-block:: console

        \b
        $ cd reana-workflow-controller
        $ reana-dev git-checkout -b . 72 --fetch
        $ reana-dev docker-build -c .
        $ reana-dev kind-load-docker-image -c .
        $ reana-dev kubectl-delete-pod -c .

    How to test multiple component branches:

    .. code-block:: console

        \b
        $ reana-dev git-checkout -b reana-server 72
        $ reana-dev git-checkout -b reana-workflow-controller 98
        $ reana-dev git-status
        $ reana-dev docker-build
        $ reana-dev kind-load-docker-image -c reana-server
        $ reana-dev kubectl-delete-pod -c reana-server
        $ reana-dev kind-load-docker-image -c reana-workflow-controller
        $ reana-dev kubectl-delete-pod -c reana-workflow-controller

    How to test multiple component branches with commits to shared modules:

    .. code-block:: console

        \b
        $ reana-dev git-checkout -b reana-commons 72
        $ reana-dev git-checkout -b reana-db 73
        $ reana-dev git-checkout -b reana-workflow-controller 98
        $ reana-dev git-checkout -b reana-server 112
        $ reana-dev run-ci [using same old options]

    How to release and push cluster component images:

    .. code-block:: console

        \b
        $ reana-dev git-clean
        $ reana-dev docker-build --no-cache
        $ # we should now run one more test with non-cached ``latest``
        $ # once it works, we can tag and push
        $ reana-dev docker-build -t 0.3.0.dev20180625
        $ reana-dev docker-push -t 0.3.0.dev20180625
        $ # we should now publish stable helm charts for tag via chartpress

    """
    pass


def shorten_component_name(component):
    """Return canonical short version of the component name.

    Example: reana-workflow-controller -> r-w-controller

    :param component: standard component name
    :type component: str

    :return: short component name
    :rtype: str
    """
    short_name = ""
    parts = component.split("-")
    for part in parts[:-1]:
        short_name += part[0] + "-"
    short_name += parts[-1]
    return short_name


def find_standard_component_name(component_name):
    """Return standard component name corresponding to the component name.

    Note this is an idempotent operation, if ``component_name`` is already
    standard it will return it as it is.

    Example: r-w-controller -> reana-workflow-controller
             reana-ui       -> reana-ui

    :param component_name: component name
    :type component: str

    :return: standard component name
    :rtype: str

    :raise: exception in case more than one is found
    """

    def _is_standard_name(component_name):
        """Detect whether the provided component name is already standard."""
        prefixes = component_name.split("-")[:-1]
        return all([len(n) > 1 for n in prefixes])

    if _is_standard_name(component_name):
        standard_component_name = component_name
    else:
        output = []
        for component in REPO_LIST_ALL:
            component_short_name = shorten_component_name(component)
            if component_short_name == component_name:
                output.append(component)
        if len(output) == 1:
            standard_component_name = output[0]
        else:
            raise Exception(
                "Component name {0} cannot be uniquely "
                "mapped.".format(component_name)
            )

    return standard_component_name


def find_reana_srcdir():
    """Find directory where REANA sources are checked out.

    Try to go up from the current directory until you find the first parent
    directory where REANA cluster repositories are checked out.

    :return: source code directory for given component
    :rtype: str

    :raise: exception in case it is not found
    """
    # first, try current working directory:
    srcdir = os.getcwd()
    if os.path.exists(srcdir + os.sep + "reana" + os.sep + ".git" + os.sep + "config"):
        return srcdir
    # second, try from the parent of git toplevel:
    toplevel = (
        subprocess.check_output("git rev-parse --show-toplevel", shell=True)
        .decode()
        .rstrip("\r\n")
    )
    srcdir = toplevel.rsplit(os.sep, 1)[0]
    if os.path.exists(srcdir + os.sep + "reana" + os.sep + ".git" + os.sep + "config"):
        return srcdir
    # fail if not found
    raise Exception(
        "Cannot find REANA component source directory " "in {0}.".format(srcdir)
    )


def get_srcdir(component=""):
    """Return source code directory of the given REANA component.

    :param component: standard component name
    :type component: str

    :return: source code directory for given component
    :rtype: str
    """
    reana_srcdir = find_reana_srcdir()
    if component:
        return reana_srcdir + os.sep + component
    else:
        return reana_srcdir


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


def select_components(components, exclude_components=None):
    """Return expanded and unified component name list based on input values.

    :param components: A list of component name that may consist of:
                          * (1) standard component names such as
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
    :param exclude_components: A list of components to exclude.
    :type components: list
    :type exclude_components: list

    :return: Unique standard component names.
    :rtype: list

    """
    short_component_names = [shorten_component_name(name) for name in REPO_LIST_ALL]
    output = set([])
    for component in components:
        if component == "ALL":
            for repo in REPO_LIST_ALL:
                output.add(repo)
        elif component == "DEMO":
            for repo in REPO_LIST_DEMO:
                output.add(repo)
        elif component == "CLIENT":
            for repo in REPO_LIST_CLIENT:
                output.add(repo)
        elif component == "CLUSTER":
            for repo in REPO_LIST_CLUSTER:
                output.add(repo)
        elif component == ".":
            cwd = os.path.basename(os.getcwd())
            output.add(cwd)
        elif component in REPO_LIST_ALL:
            output.add(component)
        elif component in short_component_names:
            component_standard_name = find_standard_component_name(component)
            output.add(component_standard_name)
        else:
            display_message("Ignoring unknown component {0}.".format(component))

    if exclude_components:
        output = exclude_components_from_selection(output, exclude_components)

    return list(output)


def exclude_components_from_selection(selection, exclude_components):
    """Exclude list of components from list of selections.

    :param selection: List of selected components in standard naming form.
    :param exclude_components: List of components to exclude, either in short
        or standard naming form.
    :type selection: set
    :type exclude_components: list

    :return: Set of selected components without ``exclude_components``, all in
        standard naming form.
    :rtype: set
    """
    standard_named_exclude_components = [
        find_standard_component_name(c) for c in exclude_components
    ]
    non_existing_exclude_components = set(standard_named_exclude_components).difference(
        selection
    )
    if non_existing_exclude_components:
        display_message(
            "Unknown component(s) to exclude: {}".format(
                non_existing_exclude_components
            )
        )
        sys.exit(1)

    click.secho(
        "Excluding component(s) {}".format(standard_named_exclude_components),
        fg="yellow",
    )
    return selection.difference(standard_named_exclude_components)


def select_workflow_engines(workflow_engines):
    """Return known workflow engine names that REANA supports.

    :param workflow_engines: A list of workflow engine names such as 'cwl'.
    :type components: list

    :return: Unique workflow engine names.
    :rtype: list

    """
    output = set([])
    for workflow_engine in workflow_engines:
        if workflow_engine in WORKFLOW_ENGINE_LIST_ALL:
            output.add(workflow_engine)
        else:
            display_message(
                "Ignoring unknown workflow engine {0}.".format(workflow_engine)
            )
    return list(output)


def is_component_python_package(component):
    """Return whether the component is a Python package.

    Useful to skip running wide unit test commands for those components that
    are not concerned.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component is a Python package
    :rtype: bool
    """
    if os.path.exists(get_srcdir(component) + os.sep + "setup.py"):
        return True
    return False


def is_component_dockerised(component):
    """Return whether the component contains Dockerfile.

    Useful to skip some docker-related commands for those components that are
    not concerned, such as building Docker images for `reana-commons` that does
    not provide any.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component is dockerisable
    :rtype: bool
    """
    if os.path.exists(get_srcdir(component) + os.sep + "Dockerfile"):
        return True
    return False


def is_component_runnable_example(component):
    """Return whether the component contains reana.yaml.

    Useful for safety check when using some run-example commands for those
    components that are not REANA examples.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component is a REANA example
    :rtype: bool

    """
    if os.path.exists(get_srcdir(component) + os.sep + "reana.yaml"):
        return True
    return False


def does_component_need_db(component):
    """Return whether the component needs DB to run tests.

    Useful to determine which components need a Postgres DB container to run the tests.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component needs DB
    :rtype: bool
    """
    return component in (COMPONENTS_USING_SHARED_MODULE_DB + ["reana-db"])


def construct_workflow_name(example, workflow_engine):
    """Construct suitable workflow name for given REANA example.

    :param example: REANA example (e.g. reana-demo-root6-roofit)
    :param workflow_engine: workflow engine to use (cwl, serial, yadage)
    :type example: str
    :type workflow_engine: str
    """
    output = "{0}-{1}".format(example.replace("reana-demo-", ""), workflow_engine)
    return output


def run_command(cmd, component="", display=True, return_output=False):
    """Run given command in the given component source directory.

    Exit in case of troubles.

    :param cmd: shell command to run
    :param component: standard component name
    :param display: should we display command to run?
    :param return_output: shall the output of the command be returned?
    :type cmd: str
    :type component: str
    :type display: bool
    :type return_output: bool
    """
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if display:
        click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
        click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
        click.secho("{0}".format(cmd), bold=True)
    if component:
        os.chdir(get_srcdir(component))
    try:
        if return_output:
            result = subprocess.check_output(cmd, shell=True)
            return result.decode().rstrip("\r\n")
        else:
            subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as err:
        if display:
            click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
            click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
            click.secho("{0}".format(err), bold=True, fg="red")
        sys.exit(err.returncode)


def display_message(msg, component=""):
    """Display message in a similar style as run_command().

    :param msg: message to display
    :param component: standard component name
    :type msg: str
    :type component: str
    """
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    click.secho("[{0}] ".format(now), bold=True, nl=False, fg="green")
    click.secho("{0}: ".format(component), bold=True, nl=False, fg="yellow")
    click.secho("{0}".format(msg), bold=True)


def get_expected_output_filenames_for_example(example):
    """Return expected output file names for given example.

    :param example: name of the component
    :return: Tuple with output file name(s)
    """
    try:
        output = EXAMPLE_OUTPUT_FILENAMES[example]
    except KeyError:
        output = EXAMPLE_OUTPUT_FILENAMES["*"]
    return output


def get_expected_log_messages_for_example(example):
    """Return expected log messages for given example.

    :param example: name of the component
    :return: Tuple with output log messages(s)
    """
    try:
        output = EXAMPLE_LOG_MESSAGES[example]
    except KeyError:
        output = EXAMPLE_LOG_MESSAGES["*"]
    return output


def get_current_version(component, dirty=False):
    """Return the current version of a component.

    :param component: standard component name
    :param dirty: wheter the ``dirty`` flag is used when calling
        ``git describe``
    :type component: str
    :type dirty: bool
    """
    cmd = "git describe"
    if dirty:
        cmd += " --dirty --always"
    tag = run_command(cmd, component, return_output=True)
    # Remove starting `v` we use for Python/Git versioning
    return tag[1:]


def volume_mounts_to_list(ctx, param, value):
    """Convert tuple params to dictionary. e.g `(foo:bar)` to `{'foo': 'bar'}`.

    :param options: A tuple with CLI options.
    :returns: A list with all parsed mounts.
    """
    try:
        return [
            {"hostPath": op.split(":")[0], "containerPath": op.split(":")[1]}
            for op in value
        ]
    except ValueError:
        click.secho(
            '[ERROR] Option "{0}" is not valid. '
            'It must follow format "param=value".'.format(" ".join(value)),
            err=True,
            fg="red",
        ),
        sys.exit(1)


def is_cluster_created():
    """Return True/False based on whether there is a cluster created already."""
    cmd = "kind get clusters"
    output = run_command(cmd, "reana", return_output=True)
    if "kind" in output:
        return True
    return False


@cli.command()
def version():
    """Show version."""
    from reana.version import __version__

    click.echo(__version__)


@cli.command()
def help():
    """Display usage help tips and tricks."""
    click.echo(cli.__doc__)


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
@cli.command(name="git-fork")
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
@cli.command(name="git-clone")
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
@cli.command(name="git-status")
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
@cli.command(name="git-clean")
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
@cli.command(name="git-submodule")
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
@cli.command(name="git-branch")
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
@cli.command(name="git-checkout")
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
@cli.command(name="git-fetch")
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
@cli.command(name="git-upgrade")
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
@cli.command(name="git-log")
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
@cli.command(name="git-diff")
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
@cli.command(name="git-push")
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


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@click.option(
    "--tag",
    "-t",
    default="latest",
    help="Image tag to generate. Default 'latest'. "
    "Use 'auto' to generate git-tag-based value such as "
    "'0.5.1-3-g75ae5ce'",
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
    default="",
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
@cli.command(name="docker-build")
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
        generate git-tag-based value such as '0.5.1-3-g75ae5ce'.
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
    for component in components:
        component_tag = tag
        if is_component_dockerised(component):
            cmd = "docker build"
            if tag == "auto":
                component_tag = get_current_version(component, dirty=True)
            for arg in build_arg:
                cmd += " --build-arg {0}".format(arg)
            if no_cache:
                cmd += " --no-cache"
            if quiet:
                cmd += " --quiet"
            component_version_tag = "{0}/{1}:{2}".format(user, component, component_tag)
            cmd += " -t {0} .".format(component_version_tag)
            run_command(cmd, component)
            built_components_versions_tags.append(component_version_tag)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)

    if output_component_versions:
        output_component_versions.write(
            "\n".join(built_components_versions_tags) + "\n"
        )


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
@cli.command(name="docker-images")
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
@cli.command(name="docker-rmi")
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
    "'0.5.1-3-g75ae5ce'",
)
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["CLUSTER"],
    help="Which components? [name|CLUSTER]",
)
@cli.command(name="docker-push")
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
        push git-tag-based value such as '0.5.1-3-g75ae5ce'.
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
                component_tag = get_current_version(component, dirty=True)
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
@cli.command(name="docker-pull")
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


@cli.command(name="client-install")
def client_install():  # noqa: D301
    """Install latest REANA client and its dependencies."""
    for component in REPO_LIST_CLIENT:
        for cmd in [
            "pip install . --upgrade",
        ]:
            run_command(cmd, component)
    run_command("pip check", "reana")


@cli.command(name="client-uninstall")
def client_uninstall():  # noqa: D301
    """Uninstall REANA client and its dependencies."""
    cmd = "pip uninstall -y " + " ".join(REPO_LIST_CLIENT)
    run_command(cmd, "reana")
    run_command("pip check", "reana")


@click.option(
    "--build-arg",
    "-b",
    default="",
    multiple=True,
    help="Any build arguments? (e.g. `-b COMPUTE_BACKENDS=kubernetes,htcondorcern,slurmcern`)",
)
@click.option(
    "--mode",
    default="latest",
    help="In which mode to run REANA cluster? (releasehelm,releasepypi,latest,debug) [default=latest]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude from build? [c1,c2,c3]",
)
@click.option("--no-cache", is_flag=True, help="Do not use Docker image layer cache.")
@cli.command(name="cluster-build")
def cluster_build(
    build_arg, mode, exclude_components, no_cache,
):  # noqa: D301
    """Build REANA cluster.

    \b
    Example:
       $ reana-dev cluster-build --exclude-components=r-ui,r-a-vomsproxy
                                 -b COMPUTE_BACKENDS=kubernetes,htcondorcern,slurmcern
                                 --mode debug
                                 --no-cache
    """
    cmds = []
    # initalise common submodules
    if mode in ("latest", "debug"):
        cmds.append("reana-dev git-submodule --update")
    if mode in ("debug"):
        cmds.append("reana-dev python-install-eggs")
    # build Docker images
    cmd = "reana-dev docker-build"
    if exclude_components:
        cmd += " --exclude-components {}".format(exclude_components)
    for arg in build_arg:
        cmd += " -b {0}".format(arg)
    if mode in ("debug"):
        cmd += " -b DEBUG=1"
    if no_cache:
        cmd += " --no-cache"
    cmds.append(cmd)
    # load built Docker images into cluster
    if mode in ("releasepypi", "latest", "debug"):
        cmd = "reana-dev kind-load-docker-image -c CLUSTER"
        if exclude_components:
            cmd += " --exclude-components {}".format(exclude_components)
        cmds.append(cmd)
    # execute commands
    for cmd in cmds:
        run_command(cmd, "reana")


@cli.command(name="cluster-deploy")
@click.option(
    "--namespace", "-n", default="default", help="Kubernetes namespace [default]"
)
@click.option(
    "-j",
    "--job-mounts",
    multiple=True,
    callback=volume_mounts_to_list,
    help="Which directories from the Kubernetes nodes to mount inside the job pods? "
    "cluster_node_path:job_pod_mountpath, e.g /var/reana/mydata:/mydata",
)
@click.option(
    "--mode",
    default="latest",
    help="In which mode to run REANA cluster? (releasehelm,releasepypi,latest,debug) [default=latest]",
)
@click.option(
    "-v",
    "--values",
    default="helm/configurations/values-dev.yaml",
    help="Which Helm configuration values file to use? [default=helm/configurations/values-dev.yaml]",
)
def cluster_deploy(namespace, job_mounts, mode, values):  # noqa: D301
    """Deploy REANA cluster."""

    def job_mounts_to_config(job_mounts):
        job_mount_list = []
        for mount in job_mounts:
            job_mount_list.append(
                {
                    "name": mount["containerPath"].replace("/", "-")[1:],
                    "hostPath": mount["hostPath"],
                    "mountPath": mount["containerPath"],
                }
            )

        job_mount_config = ""
        if job_mount_list:
            job_mount_config = json.dumps(job_mount_list)
        else:
            job_mount_config = ""

        return job_mount_config

    if mode in ("releasehelm") and values == "helm/configurations/values-dev.yaml":
        values = "helm/reana/values.yaml"

    values_dict = {}
    with open(os.path.join(get_srcdir("reana"), values)) as f:
        values_dict = yaml.safe_load(f.read())

    job_mount_config = job_mounts_to_config(job_mounts)
    if job_mount_config:
        values_dict.setdefault("components", {}).setdefault(
            "reana_workflow_controller", {}
        ).setdefault("environment", {})["REANA_JOB_HOSTPATH_MOUNTS"] = job_mount_config

    if mode in ("debug"):
        values_dict.setdefault("debug", {})["enabled"] = True

    helm_install = "cat <<EOF | helm install reana helm/reana -n {namespace} --create-namespace --wait -f -\n{values}\nEOF".format(
        namespace=namespace, values=values_dict and yaml.dump(values_dict) or "",
    )
    cmds = [
        "helm dep update helm/reana",
        helm_install,
        "kubectl config set-context --current --namespace={}".format(namespace),
        os.path.join(get_srcdir("reana"), "scripts/create-admin-user.sh"),
    ]
    if mode in ("latest", "debug"):
        cmds.append("reana-dev git-submodule --update")
    if mode in ("debug"):
        cmds.append("reana-dev python-install-eggs")
    for cmd in cmds:
        run_command(cmd, "reana")


@cli.command(name="cluster-undeploy")
def cluster_undeploy():  # noqa: D301
    """Undeploy REANA cluster."""
    is_deployed = run_command("helm ls", "reana", return_output=True)
    if "reana" in is_deployed:
        for cmd in [
            "helm uninstall reana -n default",
            "kubectl get secrets -o custom-columns=':metadata.name' | grep reana | xargs kubectl delete secret",
            "docker exec -i -t kind-control-plane sh -c '/bin/rm -rf /var/reana/*'",
        ]:
            run_command(cmd, "reana")
    else:
        msg = "No REANA cluster to undeploy."
        display_message(msg, "reana")


@click.option(
    "--build-arg",
    "-b",
    default="",
    multiple=True,
    help="Any build arguments? (e.g. `-b COMPUTE_BACKENDS=kubernetes,htcondorcern,slurmcern`)",
)
@click.option(
    "--mode",
    default="latest",
    help="In which mode to run REANA cluster? (releasehelm,releasepypi,latest,debug) [default=latest]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude from build? [c1,c2,c3]",
)
@click.option(
    "-m",
    "--mount",
    "mounts",
    multiple=True,
    help="Which local directories to mount in the cluster nodes? [local_path:cluster_node_path]",
)
@click.option(
    "-j",
    "--job-mounts",
    multiple=True,
    help="Which directories from the Kubernetes nodes to mount inside the job pods? "
    "cluster_node_path:job_pod_mountpath, e.g /var/reana/mydata:/mydata",
)
@click.option("--no-cache", is_flag=True, help="Do not use Docker image layer cache.")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["DEMO"],
    help="Which examples to run? [default=DEMO]",
)
@cli.command(name="run-ci")
def run_ci(
    build_arg, mode, exclude_components, mounts, job_mounts, no_cache, component,
):  # noqa: D301
    """Run CI build.

    Builds and installs REANA and runs a demo example.

    \b
    Basically it runs the following sequence of commands:
       $ reana-dev client-install
       $ reana-dev cluster-undeploy
       $ reana-dev cluster-build
       $ reana-dev cluster-deploy
       $ eval "$(reana-dev client-setup-environment)" && reana-dev run-example

    in the appropriate order and with the appropriate mounting or debugging
    arguments.

    \b
    Example:
       $ reana-dev run-cli -m /var/reana:/var/reana
                           -m /usr/share/local/mydata:/mydata
                           -j /mydata:/mydata
                           -c r-d-helloworld
                           --exclude-components=r-ui,r-a-vomsproxy
                           --mode debug
    """
    # parse arguments
    components = select_components(component)
    # create cluster if needed
    if not is_cluster_created():
        cmd = "reana-dev cluster-create --mode {}".format(mode)
        for mount in mounts:
            cmd += " -m {}".format(mount)
        run_command(cmd, "reana")
    # prefetch and load images for selected demo examples
    if mode in ("releasepypi", "latest", "debug"):
        for component in components:
            for cmd in [
                "reana-dev docker-pull -c {}".format(component),
                "reana-dev kind-load-docker-image -c {}".format(component),
            ]:
                run_command(cmd, "reana")
    # undeploy cluster and install latest client
    for cmd in [
        "reana-dev cluster-undeploy",
        "reana-dev client-install",
    ]:
        run_command(cmd, "reana")
    # build cluster
    if mode in ("releasepypi", "latest", "debug"):
        cmd = "reana-dev cluster-build --mode {}".format(mode)
        if exclude_components:
            cmd += " --exclude-components {}".format(exclude_components)
        for arg in build_arg:
            cmd += " -b {0}".format(arg)
        if no_cache:
            cmd += " --no-cache"
        run_command(cmd, "reana")
    # deploy cluster
    cmd = "reana-dev cluster-deploy --mode {}".format(mode)
    for job_mount in job_mounts:
        cmd += " -j {}".format(job_mount)
    run_command(cmd, "reana")
    # run demo examples
    cmd = "eval $(reana-dev client-setup-environment) && reana-dev run-example"
    for component in components:
        cmd += " -c {}".format(component)
    run_command(cmd, "reana")


@cli.command(name="client-setup-environment")
@click.option("--server-hostname", help="Set customized REANA Server hostname.")
@click.option("--insecure-url", is_flag=True, help="REANA Server URL with HTTP.")
def client_setup_environment(server_hostname, insecure_url):  # noqa: D301
    """Display commands to set up shell environment for local cluster.

    Display commands how to set up REANA_SERVER_URL and REANA_ACCESS_TOKEN
    suitable for current local REANA cluster deployment. The output should be
    passed to eval.
    """
    try:
        export_lines = []
        component_export_line = "export {env_var_name}={env_var_value}"
        export_lines.append(
            component_export_line.format(
                env_var_name="REANA_SERVER_URL",
                env_var_value=server_hostname or "https://localhost:30443",
            )
        )
        get_access_token_cmd = "kubectl get secret -o json reana-admin-access-token"
        secret_json = json.loads(
            subprocess.check_output(get_access_token_cmd, shell=True).decode()
        )
        admin_access_token_b64 = secret_json["data"]["ADMIN_ACCESS_TOKEN"]
        admin_access_token = base64.b64decode(admin_access_token_b64).decode()
        export_lines.append(
            component_export_line.format(
                env_var_name="REANA_ACCESS_TOKEN", env_var_value=admin_access_token
            )
        )

        click.echo("\n".join(export_lines))
    except Exception as e:
        logging.debug(traceback.format_exc())
        logging.debug(str(e))
        click.echo(
            click.style(
                "Environment variables could not be generated: \n{}".format(str(e)),
                fg="red",
            ),
            err=True,
        )


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["DEMO"],
    help="Which examples to run? [default=DEMO]",
)
@click.option(
    "--workflow_engine",
    "-w",
    multiple=True,
    default=["cwl", "serial", "yadage"],
    help="Which workflow engine to run? [cwl,serial,yadage]",
)
@click.option("--file", "-f", multiple=True, help="Expected output file?")
@click.option(
    "--timecheck",
    default=TIMECHECK,
    help="Checking frequency in seconds for results? [{0}]".format(TIMECHECK),
)
@click.option(
    "--timeout",
    default=TIMEOUT,
    help="Maximum timeout to wait for results? [{0}]".format(TIMEOUT),
)
@click.option(
    "--parameter",
    "-p",
    "parameters",
    multiple=True,
    help="Additional input parameters to override "
    "original ones from reana.yaml. "
    "E.g. -p myparam1=myval1 -p myparam2=myval2.",
)
@click.option(
    "-o",
    "--option",
    "options",
    multiple=True,
    help="Additional operatioal options for the workflow execution. " "E.g. CACHE=off.",
)
@cli.command(name="run-example")
def run_example(
    component, workflow_engine, file, timecheck, timeout, parameters, options
):  # noqa: D301
    """Run given REANA example with given workflow engine.

    \b
    Example:
       $ reana-dev run-example -c r-d-r-roofit

    \b
    :param component: The option ``component`` can be repeated. The value is
                      the repository name of the example. The special value `DEMO`
                      will run all examples.
                      [default=reana-demo-root6-roofit]
    :param workflow_engine: The option ``workflow_engine`` can be repeated. The
                            value is the workflow engine to use to run the
                            example. [default=cwl,serial,yadage]
    :param file: The option ``file`` can be repeated. The value is the expected
                 output file the workflow should produce. [default=plot.png]
    :param timecheck: Checking frequency in seconds for results.
                      [default=5 (TIMECHECK)]
    :param timeout: Maximum timeout to wait for results.
                    [default=300 (TIMEOUT)]
    :param parameters: Additional input parameters to override original ones
                       from reana.yaml.
                       E.g. -p myparam1=myval1 -p myparam2=myval2.
    :param options: Additional operatioal options for the workflow execution.
                    E.g. CACHE=off.

    :type component: str
    :type workflow_engine: str
    :type sleep: int
    """
    components = select_components(component)
    workflow_engines = select_workflow_engines(workflow_engine)
    reana_yaml = {
        "cwl": "reana-cwl.yaml",
        "serial": "reana.yaml",
        "yadage": "reana-yadage.yaml",
    }
    for component in components:
        for workflow_engine in workflow_engines:
            workflow_name = construct_workflow_name(component, workflow_engine)
            # check whether example contains recipe for given engine
            if not os.path.exists(
                get_srcdir(component) + os.sep + reana_yaml[workflow_engine]
            ):
                msg = "Skipping example with workflow engine {0}.".format(
                    workflow_engine
                )
                display_message(msg, component)
                continue
            # create workflow:
            for cmd in [
                "reana-client create -f {0} -n {1}".format(
                    reana_yaml[workflow_engine], workflow_name
                ),
            ]:
                run_command(cmd, component)
            # upload inputs
            for cmd in [
                "reana-client upload -w {0}".format(workflow_name),
            ]:
                run_command(cmd, component)
            # run workflow
            input_parameters = " ".join(["-p " + parameter for parameter in parameters])
            operational_options = " ".join(["-o " + option for option in options])
            for cmd in [
                "reana-client start -w {0} {1} {2}".format(
                    workflow_name, input_parameters, operational_options
                ),
            ]:
                run_command(cmd, component)
            # verify whether job finished within time limits
            time_start = time.time()
            while time.time() - time_start <= timeout:
                time.sleep(timecheck)
                cmd = "reana-client status -w {0}".format(workflow_name)
                status = run_command(cmd, component, return_output=True)
                click.secho(status)
                if "finished" in status or "failed" in status or "stopped" in status:
                    break
            # verify logs message presence
            for log_message in get_expected_log_messages_for_example(component):
                cmd = "reana-client logs -w {0} | grep -c '{1}'".format(
                    workflow_name, log_message
                )
                run_command(cmd, component)
            # verify output file presence
            cmd = "reana-client ls -w {0}".format(workflow_name)
            listing = run_command(cmd, component, return_output=True)
            click.secho(listing)
            expected_files = file or get_expected_output_filenames_for_example(
                component
            )
            for expected_file in expected_files:
                if expected_file not in listing:
                    click.secho(
                        "[ERROR] Expected output file {0} not found. "
                        "Exiting.".format(expected_file)
                    )
                    sys.exit(1)
    # report that everything was OK
    run_command("echo OK", component)


@click.option(
    "-m",
    "--mount",
    "mounts",
    multiple=True,
    callback=volume_mounts_to_list,
    help="Which local directories to mount in the cluster nodes? [local_path:cluster_node_path]",
)
@click.option(
    "--mode",
    default="latest",
    help="In which mode to run REANA cluster? (releasehelm,releasepypi,latest,debug) [default=latest]",
)
@click.option("--worker-nodes", default=0, help="How many worker nodes? [default=0]")
@cli.command(name="cluster-create")
def cluster_create(mounts, mode, worker_nodes):  # noqa: D301
    """Create cluster.

    \b
    Example:
       $ reana-dev cluster-create -m /var/reana:/var/reana
                                  -m /usr/share/local/mydata:/mydata
                                  --mode debug
    """
    import sys

    class literal_str(str):
        pass

    def literal_unicode_str(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

    def add_volume_mounts(node):
        """Add needed volumes mounts to the provided node."""

    yaml.add_representer(literal_str, literal_unicode_str)

    control_plane = {
        "role": "control-plane",
        "kubeadmConfigPatches": [
            literal_str(
                "kind: InitConfiguration\n"
                "nodeRegistration:\n"
                "  kubeletExtraArgs:\n"
                '    node-labels: "ingress-ready=true"\n'
            )
        ],
        "extraPortMappings": [
            {"containerPort": 30080, "hostPort": 30080, "protocol": "TCP"},  # HTTP
            {"containerPort": 30443, "hostPort": 30443, "protocol": "TCP"},  # HTTPS
        ],
    }

    if mode in ("debug"):
        mounts.append({"hostPath": find_reana_srcdir(), "containerPath": "/code"})
        control_plane["extraPortMappings"].extend(
            [
                {"containerPort": 31984, "hostPort": 31984, "protocol": "TCP"},  # wdb
                {
                    "containerPort": 32580,
                    "hostPort": 32580,
                    "protocol": "TCP",
                },  # maildev
            ]
        )

    # check whether we mount shared volume for multi-node deployments:
    if worker_nodes > 0:
        mount_targets = [x["containerPath"].strip("/") for x in mounts]
        if "var/reana" in mount_targets or "var" in mount_targets:
            pass
        else:
            click.echo(
                "[ERROR] For multi-node deployments, one has to use a shared storage volume for cluster nodes."
            )
            click.echo(
                "[ERROR] Example: reana-dev cluster-create -m /var/reana:/var/reana --worker-nodes 2."
            )
            sys.exit(1)

    nodes = [{"role": "worker"} for _ in range(worker_nodes)] + [control_plane]
    for node in nodes:
        node["extraMounts"] = mounts

    cluster_config = {
        "kind": "Cluster",
        "apiVersion": "kind.x-k8s.io/v1alpha4",
        "nodes": nodes,
    }

    cluster_create = "cat <<EOF | kind create cluster --config=-\n{cluster_config}\nEOF"
    cluster_create = cluster_create.format(cluster_config=yaml.dump(cluster_config))

    # create cluster
    run_command(cluster_create, "reana")

    # pull Docker images
    if mode in ("releasepypi", "latest", "debug"):
        for cmd in [
            "reana-dev docker-pull -c reana",
            "reana-dev kind-load-docker-image -c reana",
        ]:
            run_command(cmd, "reana")


@cli.command(name="cluster-pause")
def cluster_pause():
    """Pause cluster."""
    cmd = "docker pause kind-control-plane"
    run_command(cmd, "reana")


@cli.command(name="cluster-unpause")
def cluster_unpause():
    """Unpause cluster."""
    cmd = "docker unpause kind-control-plane"
    run_command(cmd, "reana")


@cli.command(name="cluster-delete")
def cluster_delete():
    """Delete cluster."""
    cmd = "kind delete cluster"
    run_command(cmd, "reana")


@click.option("--user", "-u", default="reanahub", help="DockerHub user name [reanahub]")
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
@cli.command(name="kind-load-docker-image")
def kind_load_docker_image(user, component, exclude_components):  # noqa: D301
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
                run_command(cmd, component)
        elif is_component_dockerised(component):
            cmd = "kind load docker-image {0}/{1}".format(user, component)
            run_command(cmd, component)
        else:
            msg = "Ignoring this component that does not contain" " a Dockerfile."
            display_message(msg, component)


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["ALL"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@cli.command(name="kubectl-delete-pod")
def kubectl_delete_pod(component):  # noqa: D301
    """Delete REANA component's pod.

    If option ``component`` is not used, all pods will be deleted.

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
    if "ALL" in component:
        cmd = "kubectl delete --all pods --wait=false"
        run_command(cmd)
    else:
        components = select_components(component)
        for component in components:
            if component in COMPONENT_PODS:
                cmd = "kubectl delete pod --wait=false -l app={0}".format(
                    COMPONENT_PODS[component]
                )
                run_command(cmd, component)


@cli.command(name="python-install-eggs")
def python_install_eggs():
    """Create eggs-info/ in all REANA infrastructure and runtime components."""
    for component in REPO_LIST_CLUSTER:
        if is_component_python_package(component):
            for cmd in [
                "python setup.py bdist_egg",
            ]:
                run_command(cmd, component)


@cli.command(name="python-unit-tests")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["ALL"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
def python_unit_tests(component):  # noqa: D301
    """Run Python unit tests in independent environments.

    For each component, create a dedicated throw-away virtual environment,
    install latest shared modules (reana-commons, reana-db) that are currently
    checked-out and run the usual component unit tests. Delete the throw-away
    virtual environment afterwards.

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
        if component == "reana-job-controller" and platform.system() == "Darwin":
            msg = (
                "Ignoring component {} that cannot be tested"
                " on a macOS platform yet.".format(component)
            )
            display_message(msg, component)
        elif is_component_python_package(component):
            cmd_activate_venv = "source  ~/.virtualenvs/_{}/bin/activate".format(
                component
            )
            if does_component_need_db(component):
                run_command(
                    f"docker stop postgres__{component}\n"
                    f"docker run --rm --name postgres__{component} -p 5432:5432 "
                    "-e POSTGRES_PASSWORD=mysecretpassword -d postgres:9.6.2"
                )

            for cmd in [
                "virtualenv ~/.virtualenvs/_{}".format(component),
                "{} && which python".format(cmd_activate_venv),
                "{} && cd ../pytest-reana && "
                " pip install . --upgrade".format(cmd_activate_venv),
                "{} && cd ../reana-commons && "
                " pip install . --upgrade".format(cmd_activate_venv),
                "{} && cd ../reana-db && "
                " pip install . --upgrade".format(cmd_activate_venv),
                "git clean -d -ff -x",
                '{} && pip install ".[tests]" --upgrade'.format(cmd_activate_venv),
                "{} && {} python setup.py test".format(
                    cmd_activate_venv,
                    "REANA_SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://postgres:mysecretpassword@localhost/postgres"
                    if does_component_need_db(component)
                    else "",
                ),
                "rm -rf ~/.virtualenvs/_{}".format(component),
            ]:
                run_command(cmd, component)

            if does_component_need_db(component):
                run_command(f"docker stop postgres__{component}")
        else:
            msg = (
                "Ignoring this component that does not contain"
                " a Python setup.py file."
            )
            display_message(msg, component)


@cli.command(name="git-shared-modules-upgrade")
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
