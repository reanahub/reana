# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s run commands."""

import os
import sys
import time

import click

from reana.config import (
    EXAMPLE_LOG_MESSAGES,
    EXAMPLE_OUTPUT_FILENAMES,
    TIMECHECK,
    TIMEOUT,
    WORKFLOW_ENGINE_LIST_ALL,
)
from reana.reana_dev.utils import (
    display_message,
    get_srcdir,
    run_command,
    select_components,
    validate_mode_option,
)


def is_cluster_created():
    """Return True/False based on whether there is a cluster created already."""
    cmd = "kind get clusters"
    output = run_command(cmd, "reana", return_output=True)
    if "kind" in output:
        return True
    return False


def construct_workflow_name(example, workflow_engine):
    """Construct suitable workflow name for given REANA example.

    :param example: REANA example (e.g. reana-demo-root6-roofit)
    :param workflow_engine: workflow engine to use (cwl, serial, yadage)
    :type example: str
    :type workflow_engine: str
    """
    output = "{0}-{1}".format(example.replace("reana-demo-", ""), workflow_engine)
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


@click.group()
def run_commands():
    """Run commands group."""


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
    callback=validate_mode_option,
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
@click.option(
    "--admin-email", required=True, help="Admin user email address",
)
@click.option(
    "--admin-password", required=True, help="Admin user password",
)
@run_commands.command(name="run-ci")
def run_ci(
    build_arg,
    mode,
    exclude_components,
    mounts,
    job_mounts,
    no_cache,
    component,
    admin_email,
    admin_password,
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
       $ reana-dev run-ci -m /var/reana:/var/reana
                           -m /usr/share/local/mydata:/mydata
                           -j /mydata:/mydata
                           -c r-d-helloworld
                           --exclude-components=r-ui,r-a-vomsproxy
                           --mode debug
                           --admin-email john.doe@example.org
                           --admin-password mysecretpassword

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
    cmd = (
        f"reana-dev cluster-deploy --mode {mode}"
        f" --admin-email {admin_email} --admin-password {admin_password}"
    )
    if exclude_components:
        cmd += " --exclude-components {}".format(exclude_components)
    for job_mount in job_mounts:
        cmd += " -j {}".format(job_mount)
    run_command(cmd, "reana")
    # run demo examples
    cmd = "eval $(reana-dev client-setup-environment) && reana-dev run-example"
    for component in components:
        cmd += " -c {}".format(component)
    run_command(cmd, "reana")


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
    help="Additional operational options for the workflow execution. "
    "E.g. CACHE=off.",
)
@run_commands.command(name="run-example")
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
    :param options: Additional operational options for the workflow execution.
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


run_commands_list = list(run_commands.commands.values())
