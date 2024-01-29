# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""`reana-dev`'s Python related commands."""

import os
import platform

import click

from reana.config import (
    COMPONENTS_USING_SHARED_MODULE_DB,
    REPO_LIST_CLUSTER,
    PYTHON_EXECUTABLE_NAME,
)
from reana.reana_dev.utils import (
    display_message,
    get_srcdir,
    run_command,
    select_components,
)


def does_component_need_db(component):
    """Return whether the component needs DB to run tests.

    Useful to determine which components need a Postgres DB container to run the tests.

    :param component: standard component name
    :type component: str

    :return: True/False whether the component needs DB
    :rtype: bool
    """
    return component in (COMPONENTS_USING_SHARED_MODULE_DB + ["reana-db"])


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


@click.group()
def python_commands():
    """Python commands group."""


@python_commands.command(name="python-install-eggs")
def python_install_eggs():
    """Create eggs-info/ in all REANA infrastructure and runtime components."""
    for component in REPO_LIST_CLUSTER:
        if is_component_python_package(component):
            for cmd in [
                "python setup.py bdist_egg",
            ]:
                run_command(cmd, component)


@python_commands.command(name="python-unit-tests")
@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["ALL"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude? [c1,c2,c3]",
)
@click.option(
    "--keep-virtual-environment",
    "-k",
    is_flag=True,
    help="Whether to keep or not virtual environment after tests are finished",
)
def python_unit_tests(
    component: str, exclude_components: str, keep_virtual_environment: bool
):  # noqa: D301
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
    :param exclude_components: List of components to exclude from command.
    :type exclude_components: str
    :param keep_virtual_environment: flag, whether to keep or not virtual environment
                                    after tests are finished
    :type keep_virtual_environment: bool
    """
    if exclude_components:
        exclude_components = exclude_components.split(",")
    components = select_components(component, exclude_components)
    for component in components:
        if component == "reana-job-controller" and platform.system() == "Darwin":
            msg = (
                f"Ignoring component {component} that cannot be tested"
                " on a macOS platform yet."
            )
            display_message(msg, component)
        elif is_component_python_package(component):
            cmd_activate_venv = f"source  ~/.virtualenvs/_{component}/bin/activate"
            if does_component_need_db(component):
                run_command(
                    f"docker stop postgres__{component}\n"
                    f"docker run --rm --name postgres__{component} -p 5432:5432 "
                    "-e POSTGRES_PASSWORD=mysecretpassword -d docker.io/library/postgres:12.13"
                )

            env_pytestarg = ""
            if os.getenv("PYTEST_ADDOPTS", ""):
                env_pytestarg = 'PYTEST_ADDOPTS="{}"'.format(
                    os.getenv("PYTEST_ADDOPTS", "")
                )

            for cmd in [
                "virtualenv ~/.virtualenvs/_{} -p {}".format(
                    component, PYTHON_EXECUTABLE_NAME
                ),
                "{} && which python".format(cmd_activate_venv),
                "{} && pip install pip --upgrade".format(cmd_activate_venv),
                "{} && cd ../pytest-reana && "
                " pip install . --upgrade".format(cmd_activate_venv),
                "{} && cd ../reana-commons && "
                " pip install . --upgrade".format(cmd_activate_venv),
                "{} && cd ../reana-db && "
                " pip install . --upgrade".format(cmd_activate_venv),
                "git clean -d -ff -x",
                # Fix installation of r-w-e-snakemake test dependencies for macOS/brew
                (
                    '{} && GRAPHVIZ_DIR="$(brew --prefix graphviz)" pip install pygraphviz==1.7 --global-option=build_ext --global-option="-I$GRAPHVIZ_DIR/include" --global-option="-L$GRAPHVIZ_DIR/lib"'.format(
                        cmd_activate_venv
                    )
                    if component == "reana-workflow-engine-snakemake"
                    and platform.system() == "Darwin"
                    else ""
                ),
                # Fix installation of r-commons test dependencies
                (
                    '{} && pip install ".[cwl,snakemake,yadage]" --upgrade'.format(
                        cmd_activate_venv
                    )
                    if component == "reana-commons"
                    else ""
                ),
                # Now we can call installing regular test dependencies
                '{} && pip install ".[tests]" --upgrade'.format(cmd_activate_venv),
                "{} && {} ./run-tests.sh --check-pytest".format(
                    cmd_activate_venv, env_pytestarg
                ),
            ]:
                run_command(cmd, component)

            if not keep_virtual_environment:
                run_command(f"rm -rf ~/.virtualenvs/_{component}")

        else:
            msg = (
                "Ignoring this component that does not contain"
                " a Python setup.py file."
            )
            display_message(msg, component)


python_commands_list = list(python_commands.commands.values())
