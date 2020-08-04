# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s kubectl commands."""

import json
import subprocess

import click

from reana.config import COMPONENT_PODS
from reana.reana_dev.utils import run_command, select_components


def exec_into_component(component_name, command):
    """Execute a command inside a component.

    :param component_name: Name of the component where the command will be
        executed.
    :param command: String which represents the command to execute inside
        the component.
    :return: Returns a string which represents the output of the command.
    """
    component_pod_name = (
        subprocess.check_output(
            [
                "kubectl",
                "get",
                "pods",
                "-l=app={component_name}".format(component_name=component_name),
                "-o",
                'jsonpath="{.items[0].metadata.name}"',
            ]
        )
        .decode("UTF-8")
        .replace('"', "")
    )

    component_shell = ["kubectl", "exec", "-t", component_pod_name, "--"]

    command_inside_component = []
    command_inside_component.extend(component_shell)
    command_inside_component.extend(command)

    output = subprocess.check_output(command_inside_component)
    return output.decode("UTF-8")


def get_service_ips_and_ports(component_name):
    """Get external IPs and ports for a given component service.

    :param componenet_name: Which REANA component to fetch externals IPs and
        ports from.
    :return: Returns a tuple, being the first element the list of external IPs
        and the second element the available ports.
    """
    try:
        get_service_cmd = ["kubectl", "get", "service", component_name, "-o", "json"]
        service_spec = subprocess.check_output(get_service_cmd).strip().decode("UTF-8")
        spec = json.loads(service_spec)
        external_ips = spec["spec"].get("externalIPs", [])
        ports_spec = spec["spec"]["ports"]
        ports = {}
        for port in ports_spec:
            ports[port["name"]] = port.get("nodePort", port.get("port"))
        return external_ips, ports
    except subprocess.CalledProcessError:
        return ()


@click.group()
def kubectl_commands():
    """Kubectl commands group."""


@click.option(
    "--component",
    "-c",
    multiple=True,
    default=["ALL"],
    help="Which components? [shortname|name|.|CLUSTER|ALL]",
)
@kubectl_commands.command(name="kubectl-delete-pod")
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


kubectl_commands_list = list(kubectl_commands.commands.values())
