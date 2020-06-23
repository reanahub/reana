# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""REANA Kubernetes cluster utils."""

import json
import os
import subprocess

INSTANCE_NAME = os.path.basename(os.environ["VIRTUAL_ENV"])


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


def get_prefixed_component_name(component):
    """Get prefixed component name.

    :param component: String representing the component name.

    :return: Prefixed name.
    """
    return "-".join([INSTANCE_NAME, component])
