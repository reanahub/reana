# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s run commands."""

import os
import subprocess
import sys
import time

import click

from reana.config import (
    COMPUTE_BACKEND_LIST_ALL,
    EXAMPLE_LOG_MESSAGES,
    EXAMPLE_NON_STANDARD_REANA_YAML_FILENAME,
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


def construct_workflow_name(example, workflow_engine, compute_backend):
    """Construct suitable workflow name for given REANA example.

    :param example: REANA example (e.g. reana-demo-root6-roofit)
    :param workflow_engine: workflow engine to use (cwl, serial, yadage, snakemake)
    :param compute_backend: compute backend to use (kubernetes, htcondorcern, slurmcern)
    :type example: str
    :type workflow_engine: str
    :type compute_backend: str
    """
    output = "{0}-{1}-{2}".format(
        example.replace("reana-demo-", ""), workflow_engine, compute_backend
    )
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


def select_compute_backends(compute_backends):
    """Return known compute backends names that REANA supports.

    :param workflow_engines: A list of compute backends names such as 'slurmcern'.
    :type components: list

    :return: Unique compute backend names.
    :rtype: list

    """

    def _has_cern_secrets():
        """Check whether the test user has the correct CERN secrets?."""
        output = subprocess.check_output(["reana-client", "secrets-list"]).decode(
            "UTF-8"
        )
        required_cern_secrets = [
            "CERN_KEYTAB",
            "CERN_USER",
        ]
        return all(sec in output for sec in required_cern_secrets)

    output = set([])
    has_selected_cern_compute_backend = False
    for compute_backend in compute_backends:
        if compute_backend in COMPUTE_BACKEND_LIST_ALL:
            if "cern" in compute_backend:
                has_selected_cern_compute_backend = True
            output.add(compute_backend)
        elif compute_backend.upper() == "ALL":
            output = COMPUTE_BACKEND_LIST_ALL
            has_selected_cern_compute_backend = True
            break
        else:
            display_message(
                "Ignoring unknown compute backend {0}.".format(compute_backend)
            )

    if has_selected_cern_compute_backend and not _has_cern_secrets():
        click.secho(
            "You are trying to use a CERN compute backend but you don't have "
            "the correct secrets setup.\nPlease follow "
            "http://docs.reana.io/advanced-usage/access-control/kerberos/#uploading-secrets."
        )
        sys.exit(1)
    return list(output)


def get_example_reana_yaml_file_path(example, workflow_engine, compute_backend):
    """Get absolute path to ``reana.yaml`` file for the specified example, workflow engine and compute backend.

    :param example: Example where find the ``reana.yaml`` file (one of ``reana.config.REPO_LIST_DEMO``).
    :param workflow_engine: Workflow engine used by the example (one of ``reana.config.WORKFLOW_ENGINE_LIST_ALL``).
    :param components: Compute backend used by the example (one of ``reana.config.COMPUTE_BACKEND_LIST_ALL``).
    :return: Absolute path to ``reana.yaml`` that fulfills the specified characteristics. Empty string otherwise.
    :type example: str
    :type workflow_engine: str
    :type compute_backend: str
    :rtype: str

    """
    reana_yaml_filename = (
        EXAMPLE_NON_STANDARD_REANA_YAML_FILENAME.get(example, {})
        .get(workflow_engine, {})
        .get(compute_backend, {})
    )
    if not reana_yaml_filename:
        reana_yaml_filename = "reana{workflow_engine}{compute_backend}.yaml".format(
            workflow_engine=""
            if workflow_engine == "serial"
            else "-{}".format(workflow_engine),
            compute_backend=""
            if compute_backend == "kubernetes"
            else "-{}".format(compute_backend),
        )
    reana_yaml_filename_path = get_srcdir(example) + os.sep + reana_yaml_filename
    try:
        # check whether example contains recipe for given engine
        subprocess.check_output(
            [
                "grep",
                "-q",
                "type: {}".format(workflow_engine),
                reana_yaml_filename_path,
            ],
            stderr=subprocess.DEVNULL,
        )
        return reana_yaml_filename_path
    except subprocess.CalledProcessError:
        return ""


@click.group()
def run_commands():
    """Run commands group."""


@click.option(
    "--build-arg",
    "-b",
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
    "--admin-email",
    required=True,
    help="Admin user email address",
)
@click.option(
    "--admin-password",
    required=True,
    help="Admin user password",
)
@click.option(
    "--workflow-engine",
    "-w",
    multiple=True,
    default=WORKFLOW_ENGINE_LIST_ALL,
    help="Which workflow engine to run? [default={}]".format(
        ",".join(WORKFLOW_ENGINE_LIST_ALL)
    ),
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
    workflow_engine,
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
    for a_workflow_engine in workflow_engine:
        cmd += " -w {}".format(a_workflow_engine)
    run_command(cmd, "reana")


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["DEMO"],
    help="Which examples to run? [default=DEMO]",
)
@click.option(
    "--workflow-engine",
    "-w",
    multiple=True,
    default=WORKFLOW_ENGINE_LIST_ALL,
    help="Which workflow engine to run? [default={}]".format(
        ",".join(WORKFLOW_ENGINE_LIST_ALL)
    ),
)
@click.option(
    "--compute-backend",
    "-b",
    multiple=True,
    default=["kubernetes"],
    help="Which compute backend to run? specify ALL if you want to select "
    "all compute backends ({}) [default=kubernetes]".format(
        ",".join(COMPUTE_BACKEND_LIST_ALL)
    ),
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
@click.option(
    "--submit-only", is_flag=True, help="Do not wait for workflows to finish."
)
@click.option(
    "--check-only", is_flag=True, help="Wait for previously submitted workflows."
)
@run_commands.command(name="run-example")
def run_example(
    component,
    workflow_engine,
    compute_backend,
    file,
    timecheck,
    timeout,
    parameters,
    options,
    submit_only,
    check_only,
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
                            example. [default=cwl,serial,yadage,snakemake]
    :param compute_backend: The option ``compute_backend`` can be repeated. The
                            value is the compute backend to use to run the
                            example. [default=kubernetes,htcondorcern,slurmcern]
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
    :param submit_only: Do not wait for workflows to finish.
    :param check_only: Wait for previously submitted workflows.

    :type component: str
    :type workflow_engine: list
    :type compute_backend: list
    :type file: list
    :type timecheck: int
    :type timeout: int
    :type parameters: list
    :type options: list
    :type submit_only: bool
    :type check_only: bool
    """
    if submit_only and check_only:
        click.secho(
            "[ERROR] Options --submit-only and --check-only are mutually exclusive. Choose only one."
        )
        sys.exit(1)
    components = select_components(component)
    workflow_engines = select_workflow_engines(workflow_engine)
    compute_backends = select_compute_backends(compute_backend)

    display_message(
        "Running the following matrix:\n"
        "Demos: {}\n"
        "Workflow engines: {}\n"
        "Compute backends: {}".format(
            ",".join(components), ",".join(workflow_engines), ",".join(compute_backends)
        )
    )
    for component in components:
        for workflow_engine in workflow_engines:
            for compute_backend in compute_backends:
                reana_yaml_file_path = get_example_reana_yaml_file_path(
                    component, workflow_engine, compute_backend
                )
                if not reana_yaml_file_path:
                    msg = "Skipping example {0} with workflow engine {1} and compute backend {2}.".format(
                        component, workflow_engine, compute_backend
                    )
                    display_message(msg, component)
                    continue
                workflow_name = construct_workflow_name(
                    component, workflow_engine, compute_backend
                )
                if not check_only:
                    # create workflow:
                    for cmd in [
                        "reana-client create -f {0} -n {1}".format(
                            reana_yaml_file_path,
                            workflow_name,
                        ),
                    ]:
                        run_command(cmd, component)
                    # upload inputs
                    for cmd in [
                        "reana-client upload -w {0}".format(workflow_name),
                    ]:
                        run_command(cmd, component)
                    # run workflow
                    input_parameters = " ".join(
                        ["-p " + parameter for parameter in parameters]
                    )
                    operational_options = " ".join(
                        ["-o " + option for option in options]
                    )
                    for cmd in [
                        "reana-client start -w {0} {1} {2}".format(
                            workflow_name, input_parameters, operational_options
                        ),
                    ]:
                        run_command(cmd, component)
                if not submit_only:
                    # verify whether job finished within time limits
                    time_start = time.time()
                    while time.time() - time_start <= timeout:
                        time.sleep(timecheck)
                        cmd = "reana-client status -w {0}".format(workflow_name)
                        status = run_command(cmd, component, return_output=True)
                        click.secho(status)
                        if (
                            "finished" in status
                            or "failed" in status
                            or "stopped" in status
                        ):
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
