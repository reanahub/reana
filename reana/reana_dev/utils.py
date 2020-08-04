# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev` related utils."""

import datetime
import os
import subprocess
import sys

import click

from reana.config import (
    REPO_LIST_ALL,
    REPO_LIST_CLIENT,
    REPO_LIST_CLUSTER,
    REPO_LIST_DEMO,
)

INSTANCE_NAME = os.path.basename(os.environ["VIRTUAL_ENV"])


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


def get_prefixed_component_name(component):
    """Get prefixed component name.

    :param component: String representing the component name.

    :return: Prefixed name.
    """
    return "-".join([INSTANCE_NAME, component])
