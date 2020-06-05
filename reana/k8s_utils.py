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


def get_external_url(insecure=False):
    """Get external IP and port to access REANA API.

    :param insecure: Whether the URL should be insecure (http) or secure
        (https).
    :return: Returns a string which represents the full URL to access REANA.
    """
    minikube_ip = (
        subprocess.check_output(["minikube", "ip", "--profile", INSTANCE_NAME])
        .strip()
        .decode("UTF-8")
    )
    # get service ports
    traefik_name = get_prefixed_component_name("traefik")
    server_name = get_prefixed_component_name("server")
    external_ips, external_ports = get_service_ips_and_ports(traefik_name)
    if not external_ports:
        external_ips, external_ports = get_service_ips_and_ports(server_name)
    if external_ports.get("https") and not insecure:
        scheme = "https"
    else:
        scheme = "http"
    return "{scheme}://{host}:{port}".format(
        scheme=scheme,
        host=minikube_ip or external_ips[0],
        port=external_ports.get(scheme),
    )


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
