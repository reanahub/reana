# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2025 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s kueue commands."""
import json
import os
import shlex
import subprocess
import time
from typing import Optional, Tuple

import click
import yaml

KUEUE_VERSION = "0.14.4"
KUEUE_RESOURCES_FILE = os.getenv("KUEUE_RESOURCES_FILE") or "kueue-resources.yaml"
KUEUE_SYSTEM_NAMESPACE = "kueue-system"
KUBE_SYSTEM_NAMESPACE = "kube-system"
MULTIKUEUE_CONFIG_NAME = "multikueue-config"
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000000"
BATCH_QUEUE = {
    "name": "batch-queue",
    "flavor": "batch-flavor",
    "resources": {
        "cpu": 2,
        "memory": "3Gi",
    },
}


class KueueFlavor:
    """Kueue flavor representation."""

    def __init__(self, name: str, cpu: str | int, memory: str):
        """Initialize a KueueFlavor object.

        Args:
            name: Name of the flavor (cannot be empty).
            cpu: Number of CPUs (cannot be empty, must be an integer).
            memory: Amount of memory (cannot be empty, must be a valid value, e.g. 1Mi, 3Gi, etc.).

        Raises:
            AssertionError: If any of the arguments are invalid.
        """
        self.name = name.strip()
        self.cpu = str(cpu).strip()
        self.memory = memory.strip()

        assert self.name, "Flavor name cannot be empty."
        assert self.cpu, "Flavor cpu cannot be empty."
        assert self.memory, "Flavor memory cannot be empty."

        # Ensure cpu is an integer
        try:
            int(self.cpu)
        except ValueError:
            raise ValueError(
                f"Flavor {self.name} has invalid cpu value: {self.cpu}. It must be an integer."
            )

        # Ensure memory is a valid value (e.g. 1Mi, 3Gi, etc.)
        try:
            int(self.memory[:-2])
            assert self.memory[-2:] in [
                "Mi",
                "Gi",
                "Ti",
            ], f"Flavor {self.name} has invalid memory value: {self.memory}. It must end with 'Mi', 'Gi' or 'Ti'."
        except ValueError:
            raise ValueError(
                f"Flavor {self.name} has invalid memory value: {self.memory}. It must be a valid value (e.g. 1Mi, 3Gi, etc.)."
            )

    def __eq__(self, other):
        """Check if two KueueFlavor objects are equal.

        Two flavors are considered equal if they have the same name, cpu, and memory.
        """
        return isinstance(other, KueueFlavor) and (
            self.name == other.name
            and self.cpu == other.cpu
            and self.memory == other.memory
        )

    def __hash__(self):
        """Return a hash value for the KueueFlavor object.

        This is necessary to use KueueFlavor objects in sets and dictionaries.
        """
        return hash((self.name, self.cpu, self.memory))

    def __repr__(self):
        """Return a string representation of the KueueFlavor object.

        This is necessary for pretty-printing KueueResources objects.
        """
        return f"  - name: {self.name}\n    cpu: {self.cpu}\n    memory: {self.memory}"


class KueueQueue:
    """Kueue queue representation."""

    def __init__(self, name: str, flavors: list[KueueFlavor]):
        """Initialize a KueueQueue object.

        Args:
            name: Name of the queue (cannot be empty).
            flavors: List of KueueFlavor objects representing the flavors in the queue.
        """
        self.name = name.strip()
        self.flavors = flavors

        assert self.name, "Queue name cannot be empty."
        assert self.flavors, "Queue flavors cannot be empty."

    def __eq__(self, other):
        """Check if two KueueQueue objects are equal.

        Two queues are considered equal if they have the same name and flavors.
        """
        return isinstance(other, KueueQueue) and (
            self.name == other.name
            and frozenset(self.flavors) == frozenset(other.flavors)
        )

    def __hash__(self):
        """Return a hash value for the KueueQueue object.

        This is necessary to use KueueQueue objects in sets and dictionaries.
        """
        return hash((self.name, frozenset(self.flavors)))

    def __repr__(self):
        """Return a string representation of the KueueQueue object.

        This is necessary for pretty-printing KueueResources objects.
        """
        return f"      - name: {self.name}\n        flavors:\n{"\n".join([f"          - {f.name}" for f in self.flavors])}"


class KueueNode:
    """Kueue node representation."""

    def __init__(self, name: str, queues: list[KueueQueue]):
        """Initialize a KueueNode object.

        Args:
            name: Name of the node (cannot be empty).
            queues: List of KueueQueue objects representing the queues in the node.
        """
        self.name = name.strip()
        self.queues = queues

        assert self.name, "Node name cannot be empty."

    def __eq__(self, other):
        """Check if two KueueNode objects are equal.

        Two nodes are considered equal if they have the same name and queues.
        """
        return isinstance(other, KueueNode) and (
            self.name == other.name
            and frozenset(self.queues) == frozenset(other.queues)
        )

    def __hash__(self):
        """Return a hash value for the KueueNode object.

        This is necessary to use KueueNode objects in sets and dictionaries.
        """
        return hash((self.name, frozenset(self.queues)))

    def __repr__(self):
        """Return a string representation of the KueueNode object.

        This is necessary for pretty-printing KueueResources objects.
        """
        return f"  - name: {self.name}\n    queues:\n{"\n".join([repr(q) for q in self.queues])}"


class KueueResources:
    """Kueue resources representation."""

    def __init__(
        self,
        flavors: Optional[list[KueueFlavor]] = None,
        nodes: Optional[list[KueueNode]] = None,
    ):
        """Initialize a KueueResources object.

        Args:
            flavors: List of KueueFlavor objects representing the flavors.
            nodes: List of KueueNode objects representing the nodes.
        """
        if (flavors is None) != (nodes is None):
            raise ValueError(
                "Either both or neither of flavors and nodes must be provided."
            )

        if flavors is not None and nodes is not None:
            assert len(nodes) > 0, "Nodes cannot be empty."

            self.flavors = flavors
            self.nodes = nodes
        else:
            try:
                self.flavors, self.nodes = self._parse_resources_file()

                # Check for duplicate flavors
                duplicate_flavors = find_duplicate_flavors(self)
                assert (
                    not duplicate_flavors
                ), f"Duplicate flavors found: {", ".join(duplicate_flavors.keys())}"
            except AssertionError as e:
                click.secho(f"Invalid {KUEUE_RESOURCES_FILE}: {e}", fg="red")
                raise

    def get_node(self, node_name: str) -> Optional[KueueNode]:
        """Return the KueueNode object with the given name.

        Args:
            node_name: Name of the node to retrieve.

        Returns:
            Optional[KueueNode]: KueueNode object with the given name, or None if not found.
        """
        for node in self.nodes:
            if node.name == node_name:
                return node
        return None

    @staticmethod
    def _parse_resources_file(
        resources_file: str = KUEUE_RESOURCES_FILE,
    ) -> Tuple[list[KueueFlavor], list[KueueNode]]:
        """Parse the resources file and return a KueueResources object.

        Returns:
            Tuple[list[KueueFlavor], list[KueueNode]]: Tuple containing the list of flavors and nodes.
        """
        ensure_kueue_resources_file_exists(resources_file)

        with open(resources_file, "r") as file:
            data = yaml.safe_load(file.read())

            # Validate namespace section
            assert (
                "namespace" in data
            ), "Resources file must specify a 'namespace' to use."

            # Validate flavors section
            assert "flavors" in data, "Resources file must contain 'flavors' section."
            assert isinstance(data["flavors"], list), "Flavors section must be a list."
            assert all(
                [isinstance(flavor, dict) for flavor in data["flavors"]]
            ), "Flavors section must be a list of dictionaries."
            assert all(
                ["name" in flavor for flavor in data["flavors"]]
            ), "Each flavor must contain a 'name' key."
            assert all(
                ["cpu" in flavor for flavor in data["flavors"]]
            ), "Each flavor must contain a 'cpu' key."
            assert all(
                ["memory" in flavor for flavor in data["flavors"]]
            ), "Each flavor must contain a 'memory' key."

            # Validate nodes section
            assert "nodes" in data, "Resources file must contain 'nodes' section."
            assert isinstance(data["nodes"], list), "Nodes section must be a list."
            assert all(
                [isinstance(node, dict) for node in data["nodes"]]
            ), "Nodes section must be a list of dictionaries."
            assert all(
                ["name" in node for node in data["nodes"]]
            ), "Each node must contain a 'name' key."
            assert all(
                ["queues" in node for node in data["nodes"]]
            ), "Each node must contain a 'queues' key."

            # Validate queues sections
            assert all(
                [
                    isinstance(queue, dict)
                    for node in data["nodes"]
                    for queue in node["queues"]
                ]
            ), "Queues section must be a list of dictionaries."
            assert all(
                ["name" in queue for node in data["nodes"] for queue in node["queues"]]
            ), "Each queue must contain a 'name' key."
            assert all(
                [
                    "flavors" in queue
                    for node in data["nodes"]
                    for queue in node["queues"]
                ]
            ), "Each queue must contain a 'flavors' key."

            # Ensure all flavors referenced in the queues are defined in the flavors section
            flavor_names = [flavor["name"] for flavor in data["flavors"]]
            for node in data["nodes"]:
                assert isinstance(
                    node["queues"], list
                ), f"Queues section for node '{node['name']}' must be a list."
                for queue in node["queues"]:
                    assert (
                        "name" in queue
                    ), f"Queue in node '{node['name']}' must contain a 'name' key."
                    assert (
                        "flavors" in queue
                    ), f"Queue '{queue['name']}' in node '{node['name']}' must contain a 'flavors' key."
                    assert isinstance(
                        queue["flavors"], list
                    ), f"Flavors section for queue '{queue['name']}' in node '{node['name']}' must be a list."
                    for flavor in queue["flavors"]:
                        assert (
                            flavor in flavor_names
                        ), f"Flavor '{flavor}' is referenced in the '{node['name']}' node's '{queue['name']}' queue, but is not defined in the flavors section."

            # Check for unreferenced flavors
            referenced_flavors = [
                flavor
                for node in data["nodes"]
                for queue in node["queues"]
                for flavor in queue["flavors"]
            ]
            if set(flavor_names) != set(referenced_flavors):
                click.secho(
                    f"Some flavors defined in {resources_file} are not referenced by any queue: {", ".join(set(flavor_names) - set(referenced_flavors))}",
                    fg="yellow",
                )

            # Convert to KueueFlavor, KueueNode, KueueQueue objects
            kueue_flavors = [
                KueueFlavor(flavor["name"], flavor["cpu"], flavor["memory"])
                for flavor in data["flavors"]
            ]

            return kueue_flavors, [
                KueueNode(
                    node["name"],
                    [
                        KueueQueue(
                            get_job_queue_name(node["name"], queue["name"]),
                            [
                                flavor
                                for flavor in kueue_flavors
                                if flavor.name in queue["flavors"]
                            ],
                        )
                        for queue in node["queues"]
                    ],
                )
                for node in data["nodes"]
            ]

    def get_kubeconfigs(self) -> list[str | None]:
        """Return a list of all kubeconfigs referenced in the resources file.

        Returns:
            list[str | None]: List of kubeconfigs. None represents the local cluster.
        """
        return [
            get_kubeconfig_file(node.name) if node.name != "local" else None
            for node in self.nodes
        ]

    def __eq__(self, other):
        """Check if two KueueResources objects are equal.

        Two KueueResources objects are considered equal if they have the same flavors and nodes.
        """
        return isinstance(other, KueueResources) and (
            frozenset(self.flavors) == frozenset(other.flavors)
            and frozenset(self.nodes) == frozenset(other.nodes)
        )

    def __repr__(self):
        """Return a string representation of the KueueResources object.

        This is necessary for pretty-printing KueueResources objects.
        """
        return f"""
flavors:
{"\n".join([repr(flavor) for flavor in self.flavors])}

nodes:
{"\n".join([repr(node) for node in self.nodes])}
"""


def run_cmd(
    cmd: str, dry_run: bool, check: bool = False, capture_output: bool = False, **kwargs
):
    """
    Run a shell command.

    Args:
        cmd: Command to run.
        dry_run: If True, does not actually run the command.
        check: If True, raises an exception if the command returns a non-zero exit code.
        capture_output: If True, captures and returns the command's output.
        **kwargs: Additional keyword arguments to pass to subprocess functions.

    Returns:
        str: Command's output if capture_output is True.
        int: Command's exit code if capture_output is False.
    """
    if dry_run:
        click.secho(f"$ {cmd}", fg="blue")
        return "" if capture_output else 0

    if capture_output:
        return (
            subprocess.check_output(cmd, shell=True, **kwargs).decode("utf-8").strip()
        )
    elif check:
        return subprocess.check_call(cmd, shell=True, **kwargs)
    else:
        return subprocess.call(cmd, shell=True, **kwargs)


def ensure_kueue_resources_file_exists(resources_file: str = KUEUE_RESOURCES_FILE):
    """Ensure that the resources file exists and is valid.

    Args:
        resources_file: Path to the resources file.

    Raises:
        click.ClickException: If the resources file does not exist or is invalid.
    """
    if not os.path.exists(resources_file):
        raise click.ClickException(
            f"Resources file {resources_file} does not exist in the current directory. Please create it, run the command from a different directory, or use `kueue-generate-resources` to create a template."
        )

    with open(resources_file) as file:
        data = yaml.safe_load(file.read())
        NAMESPACE = data.get("namespace")
        if not NAMESPACE:
            raise click.ClickException(
                f"Namespace is not defined in {resources_file}. Please specify a namespace where Kueue resources should be managed."
            )

        if NAMESPACE == KUEUE_SYSTEM_NAMESPACE:
            raise click.ClickException(
                f"Namespace '{KUEUE_SYSTEM_NAMESPACE}' is reserved for Kueue system resources. Please use a different namespace."
            )

        if NAMESPACE == KUBE_SYSTEM_NAMESPACE:
            raise click.ClickException(
                f"Namespace '{KUBE_SYSTEM_NAMESPACE}' is reserved for Kubernetes system resources. Please use a different namespace."
            )


def get_namespace_from_resources_file() -> str:
    """Extract the namespace from the resources file.

    Returns:
        str: Namespace specified in the resources file.
    """
    ensure_kueue_resources_file_exists()

    with open(KUEUE_RESOURCES_FILE, "r") as file:
        data = yaml.safe_load(file.read())
        return data["namespace"]


def check_namespace_exists(
    dry_run: bool, namespace: str, kubeconfig: Optional[str] = None
):
    """Check if a namespace exists.

    Args:
        dry_run: If True, does not actually check.
        namespace: Name of the namespace to check.
        kubeconfig: Optional path to kubeconfig file. If None, uses default cluster.

    Returns:
        bool: True if the namespace exists, False otherwise.
    """
    try:
        cmd = kubectl(f"get namespace {namespace}", kubeconfig)
        result = run_cmd(cmd, dry_run, capture_output=True).split("\n")
        return len(result) >= 2 and "Active" in result[1]
    except subprocess.CalledProcessError:
        return False


def ensure_namespaces_exist(
    dry_run: bool,
    kueue_resources: KueueResources,
    remote: Optional[str] = None,
    local_only: bool = False,
):
    """Ensure that the namespace specified in the resources file exists.

    Args:
        dry_run: If True, does not actually create the namespace.
        kueue_resources: KueueResources object containing the desired state.
        remote: Optional name of the remote cluster. If None, checks all clusters.
        local_only: If True, only checks the local cluster.
    """
    for kubeconfig in [None, *kueue_resources.get_kubeconfigs()]:
        if local_only and kubeconfig:
            # Skip remote nodes if only checking local namespace
            continue

        if (
            remote
            and kubeconfig
            and get_remote_name_from_kubeconfig_file(kubeconfig) != remote
        ):
            # If the --remote option is given, skip any other nodes
            continue

        # Check if namespace already exists
        namespace = get_namespace_from_resources_file()
        if not check_namespace_exists(dry_run, namespace, kubeconfig):
            # Create namespace
            click.secho(
                f"Namespace '{namespace}' does not yet exist on node '{get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else 'local'}'. Creating...",
                fg="green",
            )
            cmd = kubectl(f"create namespace {namespace}", kubeconfig)
            try:
                run_cmd(cmd, dry_run, check=True)
            except subprocess.CalledProcessError:
                # Namespace already exists
                pass


def get_files_in_current_dir():
    """Return a list of all files (including extension) in the current directory.

    Returns:
        list[str]: List of filenames in the current directory.
    """
    return [os.path.basename(f) for f in os.listdir(".")]


def get_kubeconfig_file(remote: str) -> str:
    """Return the kubeconfig file path for the given remote.

    Args:
        remote: Name of the remote cluster.

    Returns:
        str: Path to the kubeconfig file in the format '{remote}-kubeconfig.yaml'.
    """
    return f"{remote}-kubeconfig.yaml"


def get_remote_name_from_kubeconfig_file(kubeconfig_file: str) -> str:
    """Extract the remote name from a kubeconfig filename.

    Args:
        kubeconfig_file: Kubeconfig filename (e.g., 'my-remote-kubeconfig.yaml').

    Returns:
        str: Remote name extracted from the filename.
    """
    return "-".join(kubeconfig_file.split("-")[:-1])


def get_remotes():
    """Return a list of all remote cluster names in the current directory.

    Discovers remotes by finding all kubeconfig files and extracting their names.

    Returns:
        list[str]: List of remote cluster names.
    """
    return [
        get_remote_name_from_kubeconfig_file(f)
        for f in get_files_in_current_dir()
        if f.endswith("-kubeconfig.yaml")
    ]


def ensure_kubeconfig_exists(kubeconfig: str):
    """Ensure that the given kubeconfig file exists.

    Args:
        kubeconfig: Path to the kubeconfig file.

    Raises:
        click.ClickException: If the kubeconfig file does not exist.
    """
    if not os.path.exists(kubeconfig):
        raise click.ClickException(
            f"Kubeconfig {kubeconfig} does not exist. Available remotes: {get_available_remotes_str()}"
        )


def ensure_remote_reachable(dry_run: bool, kubeconfig: str):
    """Verify that the remote cluster is reachable.

    Attempts to connect to the cluster and retrieve node information.

    Args:
        dry_run: If True, does not actually check connectivity.
        kubeconfig: Path to the kubeconfig file.

    Raises:
        click.ClickException: If the remote cluster is not reachable.
    """
    cmd = kubectl("get nodes --request-timeout=3s", kubeconfig)
    try:
        run_cmd(
            cmd,
            dry_run,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        remote = get_remote_name_from_kubeconfig_file(kubeconfig)
        raise click.ClickException(f"Remote {remote} is not reachable.")


def ensure_kueue_set_up_on_nodes(dry_run: bool, kubeconfigs: list[str | None]):
    """
    Ensure that Kueue is set up on all nodes (local and remote clusters).

    Args:
        dry_run: If True, does not actually check or modify anything.
        kubeconfigs: List of kubeconfig files to check (can include None for local cluster).
    """
    for kubeconfig in kubeconfigs:
        node_name = (
            get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else "local"
        )

        if kubeconfig:
            click.echo(f"Ensuring remote '{node_name}' is reachable...")
            ensure_remote_reachable(dry_run, kubeconfig)
            if not dry_run:
                click.secho(f"Remote '{node_name}' is reachable.", fg="green")
            ensure_secret_store_created(dry_run, kubeconfig)

        click.echo(f"Ensuring Kueue is installed on node '{node_name}'...")
        check_kueue_installed(dry_run, kubeconfig, quiet=True, expect_installed=True)
        if not dry_run:
            click.secho(f"Kueue is installed on node '{node_name}'.\n", fg="green")


def get_available_remotes_str():
    """Return a formatted string listing all available remotes.

    Returns:
        str: Comma-separated list of remote names, or a help message if no remotes exist.
    """
    return (
        ",".join(get_remotes())
        or "(no remotes available; create *-kubeconfig.yaml files in your current directory first to define your remotes)"
    )


def get_resources_file(queue: str) -> str:
    """Return the resources file path for the given queue.

    Args:
        queue: Name of the queue.

    Returns:
        str: Path to the resources file in the format '{queue}-resources.yaml'.
    """
    return f"{queue}-resources.yaml"


def get_resources_files():
    """Return a list of all resources files in the current directory.

    Returns:
        list[str]: List of filenames ending with '-resources.yaml'.
    """
    return [f for f in get_files_in_current_dir() if f.endswith("-resources.yaml")]


def kubectl(
    cmd: str, kubeconfig: Optional[str] = None, namespace: Optional[str] = None
):
    """Run kubectl command with the given kubeconfig.

    :param cmd: kubectl command to run
    :param kubeconfig: kubeconfig file to use
    :param namespace: namespace to use (defaults to the namespace specified in the resources file)
    """
    namespace = namespace or get_namespace_from_resources_file()
    if kubeconfig:
        return f"kubectl --kubeconfig={kubeconfig} --namespace {namespace} {cmd}"
    else:
        return f"kubectl --namespace {namespace} {cmd}"


def helm(cmd: str, kubeconfig: Optional[str] = None):
    """Run helm command with the given kubeconfig.

    :param cmd: helm command to run
    :param kubeconfig: kubeconfig file to use
    """
    if kubeconfig:
        return (
            f"helm --kubeconfig={kubeconfig} --namespace {KUEUE_SYSTEM_NAMESPACE} {cmd}"
        )
    else:
        return f"helm {cmd} --namespace {KUEUE_SYSTEM_NAMESPACE}"


def check_kubernetes_cluster_reachable(dry_run: bool, kubeconfig: Optional[str] = None):
    """Check if Kubernetes cluster is reachable.

    Args:
        dry_run: If True, does not actually check.
        kubeconfig: Path to the kubeconfig file.

    Raises:
        click.ClickException: If the Kubernetes cluster is not reachable.
    """
    cmd = f"{kubectl("get nodes", kubeconfig)}"
    try:
        run_cmd(
            cmd,
            dry_run,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_kueue_installed(
    dry_run: bool,
    kubeconfig: Optional[str] = None,
    quiet: bool = False,
    expect_installed: bool = False,
) -> bool:
    """
    Check if Kueue is installed.

    Args:
        dry_run: If True, does not actually check.
        kubeconfig: Path to the kubeconfig file.
        quiet: If True, does not print any messages.
        expect_installed: If True, raises an exception if Kueue is not installed.
    """
    # Check if Kubernetes cluster is reachable
    if not check_kubernetes_cluster_reachable(dry_run, kubeconfig):
        if not quiet:
            click.secho("Kubernetes cluster is not reachable.", fg="red")
        return False

    # Check if namespace exists
    cmd = f"{helm("list", kubeconfig)} | grep -q kueue"
    namespace_exists = run_cmd(cmd, dry_run) == 0

    # Check version
    cmd = f"{helm("list -o json", kubeconfig)} | jq -r '.[] | select(.name==\"kueue\") | .app_version' 2>/dev/null"
    version = run_cmd(cmd, dry_run, capture_output=True)

    # Check if Kueue CRDs are installed
    crds_installed, _ = check_kueue_crds_installed(dry_run, kubeconfig, quiet=quiet)

    if namespace_exists and version and crds_installed:
        if not quiet:
            click.secho(
                f"Kueue is{'' if expect_installed else ' already'} installed {'locally' if not kubeconfig else f"on remote '{get_remote_name_from_kubeconfig_file(kubeconfig)}'"}. Helm release found (version: {version})",
                fg="green",
            )
        return True

    errors = []
    if not namespace_exists:
        errors.append("namespace does not exist")

    if not version:
        errors.append("Helm release not found or version is unknown")

    if not crds_installed:
        errors.append("some CRDs are missing")

    node_name = (
        "local" if not kubeconfig else get_remote_name_from_kubeconfig_file(kubeconfig)
    )
    error_msg = f"Kueue is not fully installed on node '{node_name}': {'; '.join(errors)}. Run 'reana-dev kueue-install{f' --remote {node_name}' if kubeconfig else ''}' to install."

    if expect_installed:
        raise click.ClickException(error_msg)

    if not quiet:
        click.secho(
            error_msg,
            fg="red",
        )

    return False


def check_kueue_crds_installed(
    dry_run: bool,
    kubeconfig: Optional[str] = None,
    quiet: bool = False,
) -> Tuple[bool, bool]:
    """
    Check if Kueue CRDs are installed.

    Args:
        dry_run: If True, does not actually check.
        kubeconfig: Path to the kubeconfig file.
        quiet: If True, does not print any messages.

    Returns:
        Tuple[bool, bool]: Tuple containing:

            - all_crds_present (bool): True if all expected CRDs are installed.

            - any_crds_present (bool): True if any of the expected CRDs are installed.
    """
    expected_crds = {
        "clusterqueues.kueue.x-k8s.io",
        "localqueues.kueue.x-k8s.io",
        "resourceflavors.kueue.x-k8s.io",
        "workloads.kueue.x-k8s.io",
        "admissionchecks.kueue.x-k8s.io",
        "multikueueconfigs.kueue.x-k8s.io",
        "multikueueclusters.kueue.x-k8s.io",
    }

    all_crds_present = True
    any_crds_present = False
    for crd in expected_crds:
        cmd = kubectl(f"get crd {crd}", kubeconfig)
        crd_missing = run_cmd(
            cmd, dry_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        if dry_run:
            continue

        if crd_missing:
            all_crds_present = False
            if not quiet:
                click.secho(f"Kueue CRD is missing: {crd}", fg="yellow")
        else:
            any_crds_present = True
            if not quiet:
                click.secho(f"Kueue CRD found: {crd}", fg="green")

    if not quiet and not dry_run:
        click.secho(
            f"Kueue CRDs are{' all ' if all_crds_present else ' not '}installed.",
            fg="green" if all_crds_present else "red",
        )

    return all_crds_present, any_crds_present


def ensure_reana_client_working(dry_run: bool):
    """Verify that the REANA client is properly configured and working.

    Args:
        dry_run: If True, does not actually check.

    Raises:
        click.ClickException: If the REANA client cannot connect to the server.
    """
    if run_cmd("reana-client ping", dry_run, check=True):
        raise click.ClickException(
            "REANA client is not working. Please check your REANA access token and server URL."
        )


def get_secret_name(remote: str) -> str:
    """Return the Kubernetes secret name for storing the remote's kubeconfig.

    Args:
        remote: Name of the remote cluster.

    Returns:
        str: Secret name in the format '{remote}-secret'.
    """
    return f"{remote}-secret"


def get_multikueue_cluster_name(remote: str) -> str:
    """Return the MultiKueueCluster resource name for the given remote.

    Args:
        remote: Name of the remote cluster.

    Returns:
        str: MultiKueueCluster name in the format '{remote}-multikueue-cluster'.
    """
    return f"{remote}-multikueue-cluster"


def get_admission_check_name(queue_name: str) -> str:
    """Return the AdmissionCheck resource name for the given queue.

    Args:
        queue_name: Name of the queue.

    Returns:
        str: AdmissionCheck name in the format '{queue_name}-admission-check'.
    """
    return f"{queue_name}-admission-check"


def get_job_queue_name(node_name: str, queue_name: str) -> str:
    """Construct the full job queue name from node and queue names.

    Args:
        node_name: Name of the node.
        queue_name: Name of the queue.

    Returns:
        str: Full queue name in the format '{node_name}-{queue_name}-job-queue'.
    """
    return f"{node_name}-{queue_name}-job-queue"


def is_mirror_job_queue(queue_name: str) -> bool:
    """Check if the given queue is a mirror job queue.

    Mirror queues are created on the local manager to mirror remote queues.
    This function should be run on the local manager.

    Args:
        queue_name: Name of the queue to check.

    Returns:
        bool: True if the queue is a mirror queue, False otherwise.
    """
    remotes = get_remotes()

    for remote in remotes:
        if queue_name.startswith(f"{remote}-") and queue_name.endswith("-job-queue"):
            return True

    return False


def build_resource_flavor_crd(flavor: KueueFlavor):
    """Build a Kubernetes CRD YAML for a ResourceFlavor.

    Args:
        flavor: KueueFlavor object containing flavor specifications.

    Returns:
        str: YAML string representing the ResourceFlavor CRD.
    """
    return f"""
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: "{flavor.name}"
  namespace: "{get_namespace_from_resources_file()}"
"""


def apply_resource_flavors(
    dry_run: bool,
    flavors: list[KueueFlavor],
    kubeconfig: Optional[str] = None,
):
    """
    Apply the given resources file to the given remote.

    :param dry_run: If True, does not actually apply the resources.
    :param flavors: The resources to apply.
    :param kubeconfig: The kubeconfig file to use.
    """
    target_node = (
        get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else "local"
    )
    click.secho(
        f"Applying the following resource flavors to '{target_node}': {', '.join([flavor.name for flavor in flavors])}"
    )

    # Apply resource flavors
    flavor_crds = [build_resource_flavor_crd(flavor) for flavor in flavors]

    cmd = f"{kubectl('apply -f -', kubeconfig)} <<EOF\n{"".join(flavor_crds)}\nEOF"
    run_cmd(cmd, dry_run, check=True)

    if not dry_run:
        click.secho("Resource flavors applied successfully.\n", fg="green")


def remove_resource_flavors(
    dry_run: bool, flavors: list[KueueFlavor], kubeconfig: Optional[str] = None
):
    """Remove the specified resource flavors from a cluster.

    Args:
        dry_run: If True, does not actually remove the resources.
        flavors: List of KueueFlavor objects to remove.
        kubeconfig: Optional path to kubeconfig file. If None, uses default cluster.
    """
    for flavor in flavors:
        click.echo(f"Removing resource flavor '{flavor.name}'...")
        force_delete_resources(
            dry_run, "resourceflavor", flavor.name, kubeconfig=kubeconfig
        )


def apply_batch_queues(dry_run: bool):
    """
    Apply batch queues to the local cluster.

    Creates a ResourceFlavor, LocalQueue, and ClusterQueue for batch processing
    on the local cluster using the configuration defined in BATCH_QUEUE.

    Args:
        dry_run: If True, does not actually apply the resources.
    """
    click.echo(
        f"Applying batch queue '{BATCH_QUEUE['name']}' and flavor '{BATCH_QUEUE['flavor']}'..."
    )
    namespace = get_namespace_from_resources_file()
    batch_crds = f"""---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: "{BATCH_QUEUE['flavor']}"
  namespace: "{namespace}"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  name: "{BATCH_QUEUE['name']}"
  namespace: "{namespace}"
spec:
  clusterQueue: "{BATCH_QUEUE['name']}"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "{BATCH_QUEUE['name']}"
  namespace: "{namespace}"
spec:
  namespaceSelector: {{}}
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
    - name: "{BATCH_QUEUE['flavor']}"
      resources:
{"".join(f"      - name: {k}\n        nominalQuota: {v}\n" for k, v in BATCH_QUEUE["resources"].items())}"""

    cmd = f"{kubectl('apply -f -')} <<EOF\n{batch_crds}\nEOF"
    run_cmd(cmd, dry_run, check=True)
    if not dry_run:
        click.secho("Batch queue applied successfully.\n", fg="green")


def apply_job_queue(
    dry_run: bool,
    queue: KueueQueue,
    kubeconfig: Optional[str] = None,
    link_admission_check: bool = False,
):
    """Apply a job queue to a cluster.

    Creates both a LocalQueue and ClusterQueue for the given queue configuration.
    For remote clusters, also adds an admission check reference.

    Args:
        dry_run: If True, does not actually apply the resources.
        queue: KueueQueue object containing queue configuration.
        kubeconfig: Optional path to kubeconfig file. If None, applies to local cluster.
        link_admission_check: If True, adds an admission check reference to the ClusterQueue.
    """
    node_name = (
        get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else "local"
    )
    namespace = get_namespace_from_resources_file()
    click.echo(f"Applying job queue '{queue.name}' to node '{node_name}'...")
    job_crds = f"""
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  name: "{queue.name}"
  namespace: "{namespace}"
spec:
  clusterQueue: "{queue.name}"
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "{queue.name}"
  namespace: "{namespace}"
spec:
  namespaceSelector: {{}}
  resourceGroups:
  - coveredResources: ["cpu", "memory"]
    flavors:
{"".join(f"    - name: {resource.name}\n      resources:\n      - name: cpu\n        nominalQuota: {resource.cpu}\n      - name: memory\n        nominalQuota: {resource.memory}\n" for resource in queue.flavors)}
{f"""  admissionChecks:
  - {get_admission_check_name(queue.name)}
""" if link_admission_check else ""}
"""

    cmd = f"{kubectl('apply -f -', kubeconfig)} <<EOF\n{job_crds}\nEOF"
    run_cmd(cmd, dry_run, check=True)
    if not dry_run:
        click.secho("Job queues applied successfully.\n", fg="green")


def remove_job_queue(
    dry_run: bool, queue: KueueQueue, kubeconfig: Optional[str] = None
):
    """Remove a job queue from a cluster.

    Deletes both the LocalQueue and ClusterQueue resources.

    Args:
        dry_run: If True, does not actually remove the resources.
        queue: KueueQueue object to remove.
        kubeconfig: Optional path to kubeconfig file. If None, removes from local cluster.
    """
    node_name = (
        get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else "local"
    )
    click.echo(f"Removing job queue '{queue.name}' from node '{node_name}'...")
    force_delete_resources(dry_run, "localqueue", queue.name, kubeconfig=kubeconfig)
    force_delete_resources(dry_run, "clusterqueue", queue.name, kubeconfig=kubeconfig)


def apply_admission_check(
    dry_run: bool,
    queue: KueueQueue,
):
    """Apply an AdmissionCheck for a queue on the local manager.

    Creates an AdmissionCheck resource that enables MultiKueue functionality
    for the specified queue.

    Args:
        dry_run: If True, does not actually apply the resources.
        queue: KueueQueue object for which to create the admission check.
    """
    admission_crd = f"""
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: AdmissionCheck
metadata:
  name: "{get_admission_check_name(queue.name)}"
  namespace: "{get_namespace_from_resources_file()}"
spec:
  controllerName: "kueue.x-k8s.io/multikueue"
  parameters:
    apiGroup: kueue.x-k8s.io
    kind: MultiKueueConfig
    name: "{MULTIKUEUE_CONFIG_NAME}"
"""

    cmd = f"{kubectl('apply -f -')} <<EOF\n{admission_crd}\nEOF"
    run_cmd(cmd, dry_run, check=True)
    if not dry_run:
        click.secho("Admission check applied successfully.\n", fg="green")


def remove_admission_check(dry_run: bool, queue: KueueQueue):
    """Remove an AdmissionCheck for a queue.

    Args:
        dry_run: If True, does not actually remove the resources.
        queue: KueueQueue object whose admission check should be removed.
    """
    force_delete_resources(
        dry_run, "admissioncheck", get_admission_check_name(queue.name)
    )


def ensure_secret_store_created(dry_run: bool, kubeconfig: Optional[str] = None):
    """Ensure the REANA secrets store secret exists on a cluster.

    Creates an empty secret for the admin user if it doesn't already exist.
    This secret is used by REANA to store user secrets.

    Args:
        dry_run: If True, does not actually create the secret.
        kubeconfig: Optional path to kubeconfig file. If None, uses local cluster.
    """
    remote = get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else "local"
    click.secho(f"Ensuring reana-secretsstore secret exists on node '{remote}'...")

    secret_name = f"reana-secretsstore-{ADMIN_USER_ID}"
    cmd = kubectl(f"get secret {secret_name}", kubeconfig)
    if run_cmd(cmd, dry_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        # Secret does not exist, create it
        cmd = f"{kubectl(f"create secret generic {secret_name} --dry-run=client -o yaml")} | {kubectl("apply -f -", kubeconfig)}"
        run_cmd(cmd, dry_run, check=True)
        click.secho(f"Secret {secret_name} created.", fg="green")


def connect_remote_cluster(dry_run: bool, remote: str):
    """
    Connect a remote cluster to the local Kueue manager.

    Args:
        dry_run: If True, does not actually apply the resources.
        remote: Name of the remote cluster to connect.
    """
    # Configure local cluster
    click.secho("Configuring Kueue for minimal workload types on local cluster...")
    configure_kueue_minimal(dry_run)

    # Configure remote cluster
    click.secho(
        f"Configuring Kueue for minimal workload types on remote cluster '{remote}'..."
    )
    configure_kueue_minimal(dry_run, remote)

    # Create secret and MultiKueueCluster
    secret_name = get_secret_name(remote)
    cmd = f"{kubectl(f'create secret generic {secret_name} --from-file=kubeconfig=\"{get_kubeconfig_file(remote)}\" --dry-run=client -o yaml', namespace=KUEUE_SYSTEM_NAMESPACE)} | {kubectl('apply -f -', namespace=KUEUE_SYSTEM_NAMESPACE)}"
    run_cmd(cmd, dry_run, check=True)

    create_multikueue_cluster(dry_run, remote)


def configure_kueue_minimal(dry_run: bool, remote: str = None):
    """Configure Kueue for minimal workload types on a cluster.

    Args:
        dry_run: If True, does not actually apply the configuration.
        remote: If provided, configure the remote cluster. Otherwise, configure local.
    """
    config = f"""apiVersion: config.kueue.x-k8s.io/v1beta1
kind: Configuration
namespace: {KUEUE_SYSTEM_NAMESPACE}
health:
  healthProbeBindAddress: :8081
metrics:
  bindAddress: :8080
webhook:
  port: 9443
leaderElection:
  leaderElect: true
  resourceName: c1f6bfd2.kueue.x-k8s.io
controller:
  groupKindConcurrency:
    Job.batch: 5
    Pod.v1: 5
    Workload.kueue.x-k8s.io: 5
    LocalQueue.kueue.x-k8s.io: 1
    ClusterQueue.kueue.x-k8s.io: 1
    ResourceFlavor.kueue.x-k8s.io: 1
    AdmissionCheck.kueue.x-k8s.io: 1
integrations:
  frameworks:
    - "batch/job"
  podOptions:
    namespaceSelector:
      matchExpressions:
      - key: kubernetes.io/metadata.name
        operator: NotIn
        values: [ {KUBE_SYSTEM_NAMESPACE}, {KUEUE_SYSTEM_NAMESPACE} ]
"""
    kubeconfig = get_kubeconfig_file(remote) if remote else None
    cmd = f"{kubectl(f'create configmap kueue-manager-config --from-literal=controller_manager_config.yaml={shlex.quote(config)} --dry-run=client -o yaml', kubeconfig=kubeconfig, namespace=KUEUE_SYSTEM_NAMESPACE)} | {kubectl('apply -f -', kubeconfig=kubeconfig, namespace=KUEUE_SYSTEM_NAMESPACE)}"
    run_cmd(cmd, dry_run, check=True)

    cmd = kubectl(
        "rollout restart deployment/kueue-controller-manager",
        namespace=KUEUE_SYSTEM_NAMESPACE,
    )
    run_cmd(cmd, dry_run, check=True)

    if not dry_run:
        time.sleep(2)
        click.secho(
            f"Kueue configured for minimal workload types on {f'remote cluster {remote}' if remote else 'local cluster'}",
            fg="green",
        )


def create_multikueue_cluster(dry_run: bool, remote: str):
    """Create a MultiKueueCluster resource for a remote cluster.

    Creates or updates the MultiKueueCluster and MultiKueueConfig resources
    to register the remote cluster with the local Kueue manager.

    Args:
        dry_run: If True, does not actually apply the resources.
        remote: Name of the remote cluster.
    """
    mk_cluster_name = get_multikueue_cluster_name(remote)
    mk_cluster_crd = f"""
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueCluster
metadata:
  name: {mk_cluster_name}
  namespace: {KUEUE_SYSTEM_NAMESPACE}
spec:
  kubeConfig:
    locationType: Secret
    location: {get_secret_name(remote)}
"""

    cmd = f"{kubectl('apply -f -')} <<EOF\n{mk_cluster_crd}\nEOF"
    run_cmd(cmd, dry_run, check=True)
    if not dry_run:
        click.secho("MultiKueueCluster created successfully.", fg="green")

    # Check if multikueueconfig exists, create if not
    cmd = kubectl(
        f"get multikueueconfig {MULTIKUEUE_CONFIG_NAME}",
        None,
        namespace=KUEUE_SYSTEM_NAMESPACE,
    )
    if run_cmd(cmd, dry_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        # Create multikueueconfig
        click.secho("Creating MultiKueueConfig...")
        multikueueconfig_crd = f"""
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: MultiKueueConfig
metadata:
  name: {MULTIKUEUE_CONFIG_NAME}
  namespace: {KUEUE_SYSTEM_NAMESPACE}
spec:
  clusters:
  - {mk_cluster_name}
"""
        cmd = f"{kubectl('apply -f -')} <<EOF\n{multikueueconfig_crd}\nEOF"
        run_cmd(cmd, dry_run, check=True)
    else:
        # Check if node already exists in multikueueconfig
        cmd = f"{kubectl(f"get multikueueconfig {MULTIKUEUE_CONFIG_NAME} -o jsonpath='{{.spec.clusters}}'", namespace=KUEUE_SYSTEM_NAMESPACE)} | grep -q {mk_cluster_name}"
        if run_cmd(cmd, dry_run):
            # Patch multikueueconfig
            click.secho("MultiKueueConfig already exists. Patching...")
            cmd = kubectl(
                f'patch multikueueconfig {MULTIKUEUE_CONFIG_NAME} --type=\'json\' -p \'[{{"op": "add", "path": "/spec/clusters/-", "value": "{mk_cluster_name}"}}]\'',
                namespace=KUEUE_SYSTEM_NAMESPACE,
            )
            run_cmd(cmd, dry_run, check=True)
        else:
            click.secho(f"{remote} already exists in MultiKueueConfig. Skipping...")


def disconnect_remote_cluster(dry_run: bool, remote: str):
    """Disconnect a remote cluster from the local Kueue manager.

    Removes all Kueue resources from the remote cluster and cleans up
    the MultiKueueCluster, secrets, and related resources on the manager.

    Args:
        dry_run: If True, does not actually apply the resources.
        remote: Name of the remote cluster to disconnect.
    """
    kubeconfig = get_kubeconfig_file(remote)
    resources_snapshot = get_resources_snapshot(
        dry_run, exclude_implicit_resources=False
    )
    queues_on_node = resources_snapshot.get_node(remote).queues

    # Delete all kueue resources on remote
    force_delete_resources(dry_run, "localqueue", kubeconfig=kubeconfig)
    force_delete_resources(dry_run, "clusterqueue", kubeconfig=kubeconfig)
    force_delete_resources(dry_run, "resourceflavor", kubeconfig=kubeconfig)

    # Delete AdmissionChecks and mirror job queues from the manager
    for queue in queues_on_node:
        force_delete_resources(
            dry_run, "admissioncheck", get_admission_check_name(queue.name)
        )
        force_delete_resources(dry_run, "localqueue", queue.name)
        force_delete_resources(dry_run, "clusterqueue", queue.name)

    mk_cluster_name = get_multikueue_cluster_name(remote)
    secret_name = get_secret_name(remote)

    # Remove multikueuecluster
    force_delete_resources(
        dry_run, "multikueuecluster", mk_cluster_name, namespace=KUEUE_SYSTEM_NAMESPACE
    )

    # Remove secret
    force_delete_resources(
        dry_run, "secret", secret_name, namespace=KUEUE_SYSTEM_NAMESPACE
    )

    # Remove from multikueueconfig
    cmd = kubectl(
        f'patch multikueueconfig {MULTIKUEUE_CONFIG_NAME} --type=\'json\' -p \'[{{"op": "remove", "path": "/spec/clusters", "value": ["{mk_cluster_name}"]}}]\'',
        namespace=KUEUE_SYSTEM_NAMESPACE,
    )
    run_cmd(cmd, dry_run, check=True)


def force_delete_resources(
    dry_run: bool,
    kind: str,
    name: Optional[str] = None,
    namespace: Optional[str] = None,
    kubeconfig: Optional[str] = None,
):
    """Force delete Kubernetes resources, bypassing finalizers.

    Removes finalizers and forcefully deletes resources. Can delete a single
    resource by name or all resources of a given kind.

    Args:
        dry_run: If True, does not actually delete resources.
        kind: Type of Kubernetes resource (e.g., 'clusterqueue', 'localqueue').
        name: Optional name of specific resource to delete. If None, deletes all
              resources of the given kind that contain 'kueue' in their name.
        namespace: Optional namespace for namespaced resources.
        kubeconfig: Optional path to kubeconfig file. If None, uses default cluster.
    """
    try:
        if name:
            # Single resource delete
            cmd = f"{kubectl(f"patch {kind} {name} --type merge -p '{{\"metadata\":{{\"finalizers\":[]}}}}'", kubeconfig, namespace)}"
            run_cmd(cmd, dry_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cmd = f"{kubectl(f"delete {kind} {name} --force --grace-period=0 --ignore-not-found=true --wait=false", kubeconfig, namespace)}"
            run_cmd(cmd, dry_run, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Delete all resources of that kind
            cmd = f"{kubectl(f"get {kind} -o name", kubeconfig)}"
            resources = run_cmd(cmd, dry_run, capture_output=True).split("\n")
            resources = [r for r in resources if "kueue" in r]

            for resource in resources:
                force_delete_resources(dry_run, kind, resource, namespace, kubeconfig)
    except subprocess.CalledProcessError:
        pass


def get_connected_remotes(dry_run: bool) -> list[str]:
    """Return a list of all currently connected remote clusters.

    Queries the local manager for MultiKueueCluster resources to determine
    which remote clusters are currently connected.

    Args:
        dry_run: If True, does not actually query the clusters.

    Returns:
        list[str]: List of remote cluster names.
    """
    cmd = kubectl(
        "get multikueueclusters -o jsonpath='{.items[*].metadata.name}'",
        namespace=KUEUE_SYSTEM_NAMESPACE,
    )
    multikueue_clusters = run_cmd(cmd, dry_run, capture_output=True).split()
    return [name.rsplit("-", maxsplit=2)[0] for name in multikueue_clusters]


def get_resources_snapshot(
    dry_run: bool, exclude_implicit_resources: bool = True
) -> KueueResources:
    """Capture the current state of Kueue resources across all clusters.

    Queries all local and connected remote clusters to build a snapshot of
    currently deployed resource flavors, queues, and their configurations.

    Args:
        dry_run: If True, does not actually query the clusters.
        exclude_implicit_resources: If True, excludes batch queues and mirror
                                   queues from the snapshot. Default is True.

    Returns:
        KueueResources: Object containing all flavors and nodes with their queues.
    """
    flavors: set[KueueFlavor] = set()
    nodes: list[KueueNode] = []

    connected_remotes = get_connected_remotes(dry_run)
    for kubeconfig in [
        None,
        *[get_kubeconfig_file(remote) for remote in connected_remotes],
    ]:
        node_name = (
            get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else "local"
        )

        # --- Get clusterqueues
        clusterqueues = []
        try:
            cmd = kubectl("get clusterqueues -o json", kubeconfig)
            cq_json = run_cmd(cmd, dry_run, capture_output=True)
            clusterqueues = json.loads(cq_json).get("items", [])
        except subprocess.CalledProcessError:
            # No clusterqueues found
            pass

        # --- Extract resource flavors from clusterqueues
        queues: list[KueueQueue] = []

        for cq in clusterqueues:
            cq_name = cq["metadata"]["name"]
            if exclude_implicit_resources:
                if node_name == "local" and (
                    cq_name == BATCH_QUEUE["name"] or is_mirror_job_queue(cq_name)
                ):
                    continue

            flavors_in_queue: list[KueueFlavor] = []

            resources = cq.get("spec", {}).get("resourceGroups", [])
            for rg in resources:
                for flavor_ref in rg.get("flavors", []):
                    flavor_name = flavor_ref["name"]
                    quota = flavor_ref.get("resources", [])
                    cpu = next(r["nominalQuota"] for r in quota if r["name"] == "cpu")
                    memory = next(
                        r["nominalQuota"] for r in quota if r["name"] == "memory"
                    )

                    flavor_obj = KueueFlavor(flavor_name, cpu, memory)

                    if (
                        exclude_implicit_resources
                        and flavor_name == BATCH_QUEUE["flavor"]
                    ):
                        continue

                    flavors_in_queue.append(flavor_obj)
                    flavors.add(flavor_obj)

            queues.append(KueueQueue(cq_name, list(set(flavors_in_queue))))

        nodes.append(KueueNode(node_name, queues))

    return KueueResources(list(flavors), nodes)


def calc_flavors_diff(
    kueue_resources: KueueResources, resources_snapshot: KueueResources
) -> tuple[set[KueueFlavor], list[KueueFlavor], set[KueueFlavor]]:
    """Calculate the differences in resource flavors between desired and current state.

    Compares the flavors defined in the resources file with those currently deployed
    to identify additions, modifications, and removals.

    Args:
        kueue_resources: Desired state from the resources file.
        resources_snapshot: Current state from the cluster.

    Returns:
        tuple: A 3-tuple containing:
            - flavors_added (set[KueueFlavor]): New flavors to be added.
            - flavors_modified (list[KueueFlavor]): Existing flavors with changed specs.
            - flavors_removed (set[KueueFlavor]): Flavors to be removed.
    """
    flavors_added = set(kueue_resources.flavors) - set(resources_snapshot.flavors)
    flavors_modified: list[KueueFlavor] = []
    flavors_removed = set(resources_snapshot.flavors) - set(kueue_resources.flavors)

    # Modified flavors have the same name but different cpu/memory
    names_in_common = set([f.name for f in resources_snapshot.flavors]) & set(
        [f.name for f in kueue_resources.flavors]
    )
    for flavor_name in names_in_common:
        flavor_before = next(
            f for f in resources_snapshot.flavors if f.name == flavor_name
        )
        flavor_after = next(f for f in kueue_resources.flavors if f.name == flavor_name)

        if (
            flavor_before.cpu != flavor_after.cpu
            or flavor_before.memory != flavor_after.memory
        ):
            flavors_added.discard(flavor_after)
            flavors_modified.append(flavor_after)
            flavors_removed.discard(flavor_before)
            click.secho(f"Flavor '{flavor_name}' will be modified:", fg="yellow")

            if flavor_before.cpu != flavor_after.cpu:
                click.secho(
                    f"  - cpu: {flavor_before.cpu} -> {flavor_after.cpu}", fg="yellow"
                )
            if flavor_before.memory != flavor_after.memory:
                click.secho(
                    f"  - memory: {flavor_before.memory} -> {flavor_after.memory}",
                    fg="yellow",
                )

    if flavors_added:
        click.secho(
            f"Flavor(s) to be added: {', '.join([f.name for f in flavors_added])}",
            fg="green",
        )

    if flavors_removed:
        click.secho(
            f"Flavor(s) to be removed: {', '.join([f.name for f in flavors_removed])}",
            fg="red",
        )

    return flavors_added, flavors_modified, flavors_removed


def calc_nodes_diff(
    kueue_resources: KueueResources, resources_snapshot: KueueResources
) -> tuple[set[str], set[str]]:
    """Calculate the differences in nodes between desired and current state.

    Compares the nodes defined in the resources file with those currently deployed
    to identify additions and removals.

    Args:
        kueue_resources: Desired state from the resources file.
        resources_snapshot: Current state from the cluster.

    Returns:
        tuple: A 2-tuple containing:
            - nodes_added (set[str]): New node names to be added.
            - nodes_removed (set[str]): Node names to be removed.
    """
    nodes_added = set([n.name for n in kueue_resources.nodes]) - set(
        [n.name for n in resources_snapshot.nodes]
    )
    nodes_removed = set([n.name for n in resources_snapshot.nodes]) - set(
        [n.name for n in kueue_resources.nodes]
    )

    if nodes_added:
        click.secho(f"Node(s) to be added: {', '.join(nodes_added)}", fg="green")

    if nodes_removed:
        click.secho(f"Node(s) to be removed: {', '.join(nodes_removed)}", fg="red")

    return nodes_added, nodes_removed


def calc_queues_diff(
    kueue_resources: KueueResources,
    resources_snapshot: KueueResources,
    flavors_modified: list[KueueFlavor],
    flavors_removed: set[KueueFlavor],
    nodes_removed: set[str],
):
    """Calculate the differences in queues between desired and current state.

    Compares the queues defined in the resources file with those currently deployed
    to identify additions, modifications, and removals on each node. A queue is
    considered modified if its flavor list changes or if it uses any modified/removed flavors.

    Args:
        kueue_resources: Desired state from the resources file.
        resources_snapshot: Current state from the cluster.
        flavors_modified: List of flavors that have been modified.
        flavors_removed: Set of flavors that will be removed.
        nodes_removed: Set of node names that will be removed.

    Returns:
        tuple: A 3-tuple containing:
            - queues_added_by_node (dict[str, list[KueueQueue]]): New queues per node.
            - queues_modified_by_node (dict[str, list[KueueQueue]]): Modified queues per node.
            - queues_removed_by_node (dict[str, list[KueueQueue]]): Removed queues per node.
    """
    queues_added_by_node: dict[str, list[KueueQueue]] = {}
    queues_modified_by_node: dict[str, list[KueueQueue]] = {}
    queues_removed_by_node: dict[str, list[KueueQueue]] = {}

    for node in resources_snapshot.nodes:
        if node.name in nodes_removed:
            continue

        queues_added = set(kueue_resources.get_node(node.name).queues) - set(
            node.queues
        )
        queues_modified: list[KueueQueue] = []
        queues_removed = set(node.queues) - set(
            kueue_resources.get_node(node.name).queues
        )

        # Modified queues have the same name but different flavors
        names_in_common = set([q.name for q in node.queues]) & set(
            [q.name for q in kueue_resources.get_node(node.name).queues]
        )
        for queue_name in names_in_common:
            queue_before = next(q for q in node.queues if q.name == queue_name)
            queue_after = next(
                q
                for q in kueue_resources.get_node(node.name).queues
                if q.name == queue_name
            )

            modified_flavor_names = {f.name for f in flavors_modified}
            removed_flavor_names = {f.name for f in flavors_removed}
            queue_uses_any_modified_flavor = any(
                f.name in modified_flavor_names for f in queue_after.flavors
            )
            queue_uses_any_removed_flavor = any(
                f.name in removed_flavor_names for f in queue_after.flavors
            )

            if (
                set(queue_before.flavors) != set(queue_after.flavors)
                or queue_uses_any_modified_flavor
                or queue_uses_any_removed_flavor
            ):
                queues_added.discard(queue_after)
                queues_removed.discard(queue_before)
                queues_modified.append(queue_after)

        queues_added_by_node[node.name] = list(queues_added)
        queues_modified_by_node[node.name] = queues_modified
        queues_removed_by_node[node.name] = list(queues_removed)

    if any(queues_added_by_node.values()):
        click.secho("Queues to be added to existing node(s):", fg="green")
        for node, queues in queues_added_by_node.items():
            if queues:
                click.secho(
                    f"  - {node}: {', '.join([q.name for q in queues])}", fg="green"
                )

    if any(queues_modified_by_node.values()):
        click.secho("Queues to be modified on node(s):", fg="yellow")
        for node, queues in queues_modified_by_node.items():
            for queue in queues:
                click.secho(f"  - {node}: {queue.name}", fg="yellow")

                queue_before = next(
                    q
                    for q in resources_snapshot.get_node(node).queues
                    if q.name == queue.name
                )
                queue_after = next(
                    q
                    for q in kueue_resources.get_node(node).queues
                    if q.name == queue.name
                )
                click.secho(
                    f"    - flavors: {', '.join([f.name for f in queue_before.flavors])} -> {', '.join([f.name for f in queue_after.flavors])}",
                    fg="yellow",
                )

    if any(queues_removed_by_node.values()):
        click.secho("Queues to be removed from node(s):", fg="red")
        for node, queues in queues_removed_by_node.items():
            if queues:
                click.secho(
                    f"  - {node}: {', '.join([q.name for q in queues])}", fg="red"
                )

    return queues_added_by_node, queues_modified_by_node, queues_removed_by_node


def calc_resource_diff(
    dry_run: bool,
    kueue_resources: KueueResources,
) -> Tuple[
    list[KueueFlavor],
    list[KueueFlavor],
    list[KueueFlavor],
    list[str],
    list[str],
    dict[str, list[KueueQueue]],
    dict[str, list[KueueQueue]],
    dict[str, list[KueueQueue]],
]:
    """Calculate comprehensive differences between desired and current Kueue resources.

    Compares the resources defined in the resources file with the current cluster state
    to identify all changes needed for flavors, nodes, and queues.

    Args:
        dry_run: If True, does not actually query the cluster.
        kueue_resources: Desired state from the resources file.

    Returns:
        tuple: An 8-tuple containing:
            - flavors_added (list[KueueFlavor]): New flavors to add.
            - flavors_modified (list[KueueFlavor]): Flavors with changed specs.
            - flavors_removed (list[KueueFlavor]): Flavors to remove.
            - nodes_added (list[str]): New node names to add.
            - nodes_removed (list[str]): Node names to remove.
            - queues_added_by_node (dict[str, list[KueueQueue]]): New queues per node.
            - queues_modified_by_node (dict[str, list[KueueQueue]]): Modified queues per node.
            - queues_removed_by_node (dict[str, list[KueueQueue]]): Removed queues per node.
    """
    click.echo(
        "\n-------------------------------------------------------------\n",
    )

    resources_snapshot = get_resources_snapshot(dry_run)

    flavors_added, flavors_modified, flavors_removed = calc_flavors_diff(
        kueue_resources, resources_snapshot
    )

    nodes_added, nodes_removed = calc_nodes_diff(kueue_resources, resources_snapshot)

    queues_added_by_node, queues_modified_by_node, queues_removed_by_node = (
        calc_queues_diff(
            kueue_resources,
            resources_snapshot,
            flavors_modified,
            flavors_removed,
            nodes_removed,
        )
    )

    click.echo(
        "\n-------------------------------------------------------------",
    )

    return (
        list(flavors_added),
        flavors_modified,
        list(flavors_removed),
        list(nodes_added),
        list(nodes_removed),
        queues_added_by_node,
        queues_modified_by_node,
        queues_removed_by_node,
    )


def find_duplicate_flavors(kueue_resources: KueueResources) -> dict[str, list[str]]:
    """Find duplicate flavor definitions in a KueueResources object.

    Identifies flavors with the same name but different specifications (CPU/memory)
    across different queues and nodes.

    Args:
        kueue_resources: KueueResources object to check for duplicates.

    Returns:
        dict[str, list[str]]: Mapping of duplicate flavor names to their locations
                             and specifications.
    """
    flavor_names = [f.name for f in kueue_resources.flavors]

    duplicate_flavors = {}
    for flavor_name in set(flavor_names):
        if flavor_names.count(flavor_name) > 1:
            locations = []
            for node in kueue_resources.nodes:
                for queue in node.queues:
                    for flavor in queue.flavors:
                        if flavor.name == flavor_name:
                            locations.append(
                                f"{node.name}/{queue.name} (cpu: {flavor.cpu}, memory: {flavor.memory})"
                            )
                            break

            duplicate_flavors[flavor_name] = locations

    return duplicate_flavors


def uninstall_kueue(
    dry_run: bool, remote: Optional[str] = None, delete_namespace: bool = False
):
    """Uninstall Kueue from a cluster.

    Removes all Kueue resources and the Kueue Helm release from the specified
    cluster (or local cluster if no remote is specified).

    Args:
        dry_run: If True, shows what would be changed without applying changes.
        remote: Optional name of the remote cluster. If None, uninstalls from local cluster.
        delete_namespace: If True, also deletes the namespace specified in the resources file.
    """
    kubeconfig = get_kubeconfig_file(remote) if remote else None
    namespace = get_namespace_from_resources_file()

    if kubeconfig:
        click.secho(f"Ensuring remote '{remote}' is reachable...")
        ensure_kubeconfig_exists(kubeconfig)
        ensure_remote_reachable(dry_run, kubeconfig)

    _, any_crds_present = check_kueue_crds_installed(dry_run, kubeconfig, quiet=True)
    if any_crds_present:
        if not dry_run:
            click.secho(f"Removing Kueue resources from namespace '{namespace}'...")

        force_delete_resources(dry_run, "clusterqueue", kubeconfig=kubeconfig)
        force_delete_resources(dry_run, "admissioncheck", kubeconfig=kubeconfig)
        force_delete_resources(dry_run, "resourceflavor", kubeconfig=kubeconfig)
        force_delete_resources(dry_run, "localqueue", kubeconfig=kubeconfig)
        force_delete_resources(
            dry_run, "secret", namespace=KUEUE_SYSTEM_NAMESPACE, kubeconfig=kubeconfig
        )
        force_delete_resources(
            dry_run,
            "multikueueconfig",
            namespace=KUEUE_SYSTEM_NAMESPACE,
            kubeconfig=kubeconfig,
        )
        force_delete_resources(
            dry_run,
            "multikueuecluster",
            namespace=KUEUE_SYSTEM_NAMESPACE,
            kubeconfig=kubeconfig,
        )

    if not dry_run:
        click.secho("Uninstalling Kueue...")

    if run_cmd(
        f"{helm("uninstall kueue --wait --timeout 20s", kubeconfig)}",
        dry_run,
    ):
        click.secho(
            "Something went wrong (the Kueue release may already be gone)", fg="yellow"
        )

    if check_namespace_exists(dry_run, namespace, kubeconfig):
        click.secho(f"Removing '{KUEUE_SYSTEM_NAMESPACE}' namespace...")
        force_delete_resources(
            dry_run, "namespace", name=KUEUE_SYSTEM_NAMESPACE, kubeconfig=kubeconfig
        )
        click.secho(f"Namespace '{KUEUE_SYSTEM_NAMESPACE}' removed.", fg="green")
    else:
        click.secho(f"Namespace '{KUEUE_SYSTEM_NAMESPACE}' already gone.", fg="green")

    if delete_namespace:
        if check_namespace_exists(dry_run, namespace, kubeconfig):
            click.secho(f"Removing '{namespace}' namespace...")
            force_delete_resources(
                dry_run, "namespace", name=namespace, kubeconfig=kubeconfig
            )
            click.secho(f"Namespace '{namespace}' removed.", fg="green")
        else:
            click.secho(f"Namespace '{namespace}' already gone.", fg="green")

    if dry_run:
        return

    click.secho("Waiting for resources to be removed...", fg="blue")
    time.sleep(5)
    click.secho(
        f"Kueue uninstalled from node '{get_remote_name_from_kubeconfig_file(kubeconfig) if kubeconfig else 'local'}'.",
        fg="green",
    )

    if not delete_namespace:
        click.secho(
            f"Namespace '{namespace}' was not deleted. Please delete it manually if you no longer need it.",
            fg="yellow",
        )


def compare_values_yaml_with_resources(
    resources: KueueResources, resources_src: str, listed_queues: list[dict[str, str]]
) -> bool:
    """Compare Kueue configuration in values.yaml with resource definitions.

    Validates that the queues listed in values.yaml match the queues defined
    in the resources file or currently installed resources.

    Args:
        resources: KueueResources object to compare against.
        resources_src: Description of the resource source (for error messages).
        listed_queues: List of queue dictionaries from values.yaml.

    Returns:
        bool: True if any problems were found, False otherwise.
    """
    any_problems = False

    # Check if all nodes in values.yaml are defined in resources snapshot
    if not all([q["node"] in [n.name for n in resources.nodes] for q in listed_queues]):
        missing_nodes = [
            q["node"]
            for q in listed_queues
            if q["node"] not in [n.name for n in resources.nodes]
        ]
        click.secho(
            f"Not all nodes listed in values.yaml are defined in {resources_src} (or values.yaml is undeployed). Missing: {', '.join(set(missing_nodes))}",
            fg="yellow",
        )
        any_problems = True

    # Check if all nodes in resources snapshot are defined in values.yaml
    for node in resources.nodes:
        if node.name not in [q["node"] for q in listed_queues]:
            click.secho(
                f"Node '{node.name}' is defined in {resources_src} but not in values.yaml (or values.yaml is undeployed).",
                fg="yellow",
            )
            any_problems = True

    for node in resources.nodes:
        # Check if the queues in each node in values.yaml match the resources snapshot
        queues_in_node = [
            get_job_queue_name(q["node"], q["name"])
            for q in listed_queues
            if q["node"] == node.name
        ]
        for queue in node.queues:
            if queue.name not in queues_in_node:
                click.secho(
                    f"Queue '{queue.name}' is defined in {resources_src} but not in values.yaml (or values.yaml is undeployed).",
                    fg="yellow",
                )
                any_problems = True

        # Check if the queues in each node in the resources snapshot match the values.yaml
        for queue in queues_in_node:
            if queue not in [q.name for q in node.queues]:
                click.secho(
                    f"Queue '{queue}' is defined in values.yaml but not in {resources_src} (or values.yaml is undeployed).",
                    fg="yellow",
                )
                any_problems = True

    return any_problems


def validate_kueue_values_yaml(dry_run: bool) -> bool:
    """Validate the Kueue configuration in the REANA Helm values.yaml file.

    Checks that:

    - Kueue is properly configured and enabled

    - Default node and queue are set correctly

    - Listed queues match the resources file and installed resources

    - All referenced nodes and queues exist

    Args:
        dry_run: If True, does not actually check the resources.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    cmd = "reana-client info --json"
    try:
        output = run_cmd(cmd, dry_run, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        click.secho(
            "Could not validate values.yaml as REANA client is not working. Please check your REANA access token and server URL.",
            fg="red",
        )
        return False

    deployment_info = json.loads(output)
    kueue_enabled = deployment_info.get("kueue_enabled", {}).get("value")
    default_node_and_queue = deployment_info.get("kueue_default_queue", {}).get("value")
    default_node = (
        default_node_and_queue.split("-")[0] if default_node_and_queue else None
    )
    default_queue = (
        default_node_and_queue.split("-")[1] if default_node_and_queue else None
    )
    available_nodes_and_queues = deployment_info.get("kueue_available_queues", {}).get(
        "value", []
    )
    available_queues = [
        {"node": nq.rsplit("-", maxsplit=1)[0], "name": nq.split("-")[-1]}
        for nq in available_nodes_and_queues
    ]

    if kueue_enabled is None:
        click.secho("Kueue is not configured in values.yaml.", fg="red")
        return False

    all_valid = True
    if kueue_enabled:
        click.secho("Kueue is enabled in values.yaml.", fg="green")
    else:
        all_valid = False
        click.secho(
            "Kueue is not enabled in values.yaml or the format is invalid.",
            fg="red",
        )

    if default_node and not default_queue:
        all_valid = False
        click.secho(
            "Default node is set in values.yaml but no default queue is set.",
            fg="red",
        )

    if default_queue and not default_node:
        all_valid = False
        click.secho(
            "Default queue is set in values.yaml but no default node is set.",
            fg="red",
        )

    if default_node and default_queue:
        # Check if default node is one of the listed nodes
        if any([queue["node"] == default_node for queue in available_queues]):
            click.secho(f"Default node: '{default_node}'")
        else:
            all_valid = False
            click.secho(
                f"Default node '{default_node}' is not one of the nodes listed in values.yaml.",
                fg="red",
            )

        # Check if default queue is one of the listed queues
        if any([queue["name"] == default_queue for queue in available_queues]):
            click.secho(f"Default queue: '{default_queue}'")
        else:
            all_valid = False
            click.secho(
                f"Default queue '{default_queue}' is not one of the queues listed in values.yaml.",
                fg="red",
            )

    if kueue_enabled and not default_node and not default_queue:
        click.secho(
            "Kueue is enabled but no default queue is set in values.yaml. Jobs that do not specify a kubernetes_queue will not run properly.",
            fg="yellow",
        )

    if available_queues:
        click.secho("Available queues:")
        for queue in available_queues:
            click.echo(f"- {queue['node']}: '{queue['name']}'")
    else:
        click.secho("No queues are listed in values.yaml.", fg="red")

    click.echo()

    if check_kueue_installed(dry_run, quiet=True):
        any_problems = compare_values_yaml_with_resources(
            get_resources_snapshot(dry_run),
            "currently installed resources",
            available_queues,
        )
        if any_problems:
            # If the currently installed resources do not match values.yaml, this isn't a problem,
            # it just means the user needs to run kueue-sync
            click.secho(
                "Kueue resources in values.yaml do not match the installed resources. Run 'reana-dev kueue-sync' to apply the changes.",
                fg="yellow",
            )
        else:
            click.secho("Currently installed resources match values.yaml.", fg="green")

    any_problems = compare_values_yaml_with_resources(
        KueueResources(), KUEUE_RESOURCES_FILE, available_queues
    )
    if any_problems:
        all_valid = False
        click.secho(
            "There are problems with the Kueue configuration in your values.yaml. Please fix them before using Kueue. After fixing your values.yaml, remember to redeploy the REANA cluster to apply the changes.",
            fg="red",
        )
    else:
        click.secho(
            f"Resources defined in {KUEUE_RESOURCES_FILE} match values.yaml.",
            fg="green",
        )

    return all_valid


def apply_job_queues(
    dry_run: bool, kueue_resources: KueueResources, remote: Optional[str] = None
):
    """
    Apply job queues to the given remote.

    Args:
        dry_run: If True, does not actually apply the resources.
        kueue_resources: KueueResources object containing the desired state.
        remote: Optional name of the remote cluster. If None, applies to all clusters.
    """
    # For each new/modified remote job queue, apply it on the remote and
    # apply an admission check and mirror queue on the manager
    for node in kueue_resources.nodes:
        if remote and node.name != remote and node.name != "local":
            # If the --remote option is given, skip any other nodes
            continue

        for queue in node.queues:
            kubeconfig = (
                get_kubeconfig_file(node.name) if node.name != "local" else None
            )
            apply_job_queue(dry_run, queue, kubeconfig)

            if node.name != "local":
                apply_job_queue(
                    dry_run, queue, kubeconfig=None, link_admission_check=True
                )
                apply_admission_check(dry_run, queue)


def sync_multikueue_config(
    dry_run: bool,
    kueue_resources: KueueResources,
    nodes_removed: list[str],
    remote: Optional[str] = None,
):
    """
    Handle connecting and disconnecting remote MultiKueueClusters and update MultiKueueConfig.

    Args:
        dry_run: If True, does not actually apply the resources.
        kueue_resources: The resources to apply.
        nodes_removed: The nodes to remove.
        remote: Optional name of the remote cluster. If None, applies to all clusters.
    """
    # Create MultiKueueClusters for any new remotes and add to MultiKueueConfig
    for node in kueue_resources.nodes:
        if node.name == "local":
            continue

        if remote and node.name != remote:
            # If the --remote option is given, skip any other nodes
            continue

        if not dry_run:
            click.echo(f"\nConnecting remote cluster '{node.name}'...")
        connect_remote_cluster(dry_run, node.name)

    # Remove MultiKueueClusters for any removed remotes and remove from MultiKueueConfig
    for node in nodes_removed:
        if node == "local":
            continue

        if remote and node != remote:
            # If the --remote option is given, skip any other nodes
            continue

        if not dry_run:
            click.echo(f"\nDisconnecting remote cluster '{node}'...")
        disconnect_remote_cluster(dry_run, node)


def sync_resource_flavors(
    dry_run: bool,
    kueue_resources: KueueResources,
    flavors_removed: list[KueueFlavor],
    remote: Optional[str] = None,
    local_only: bool = False,
):
    """
    Sync the resource flavors to the given remote.

    Args:
        dry_run: If True, does not actually apply the resources.
        kueue_resources: The resources to apply.
        flavors_removed: The flavors to remove.
        remote: Optional name of the remote cluster. If None, applies to all clusters.
        local_only: If True, only applies to the local cluster.
    """
    # Apply new/modified resource flavors to all nodes
    for kubeconfig in kueue_resources.get_kubeconfigs():
        if (
            remote
            and kubeconfig
            and get_remote_name_from_kubeconfig_file(kubeconfig) != remote
        ):
            # If the --remote option is given, skip any other nodes
            continue

        if local_only and kubeconfig:
            # Skip remote nodes if only syncing local resources
            continue

        apply_resource_flavors(dry_run, kueue_resources.flavors, kubeconfig)
        remove_resource_flavors(dry_run, flavors_removed, kubeconfig)


def check_remote_in_resources_file_exist(kueue_resources: KueueResources):
    """Check if all remotes referenced in the resources file have a corresponding kubeconfig file.

    Args:
        kueue_resources: The resources to check.

    Returns:
        bool: True if all remotes exist, False otherwise.
    """
    all_exist = True

    available_remotes = get_remotes()
    for node in kueue_resources.nodes:
        if node.name == "local":
            continue

        if node.name not in available_remotes:
            all_exist = False
            click.secho(
                f"Remote '{node.name}' is referenced in {KUEUE_RESOURCES_FILE}, but there are only kubeconfigs for these remotes: {', '.join(available_remotes)}",
                fg="red",
            )

    return all_exist


@click.group()
def kueue_commands():
    """Click command group for Kueue-related commands."""


@kueue_commands.command(name="kueue-validate")
def kueue_validate_command():
    """Call `kueue_validate`."""
    kueue_validate(strict=True)


def kueue_validate(strict: bool = False):
    """Validate the Kueue resources file and values.yaml configuration.

    Performs comprehensive validation including:

    - Checking the syntax and structure of the resources file

    - Validating values.yaml Kueue configuration

    - Comparing resources file with installed resources

    - Detecting duplicate flavor definitions

    Args:
        strict: If True, returns False if there are any differences between the resources file and the installed resources.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    click.secho(f"\nValidating {KUEUE_RESOURCES_FILE}...", fg="blue")
    kueue_resources = KueueResources()

    all_exist = check_remote_in_resources_file_exist(kueue_resources)
    if all_exist:
        click.secho("Kueue resources file is valid.", fg="green")

    click.secho("\nValidating values.yaml...", fg="blue")
    all_valid = validate_kueue_values_yaml(dry_run=False)

    if check_kueue_installed(dry_run=False, quiet=True):
        resources_snapshot = get_resources_snapshot(dry_run=False)
        if kueue_resources != resources_snapshot:
            if strict:
                all_valid = False

            click.secho(
                "There are differences between the resources file and the installed resources. Run 'reana-dev kueue-diff' to compare.",
                fg="yellow",
            )

        # Check for duplicate flavor names
        click.secho("\nChecking for duplicate flavor names...", fg="blue")

        duplicate_flavors = find_duplicate_flavors(resources_snapshot)
        if duplicate_flavors:
            all_valid = False

            click.secho(
                "Some installed resource flavors with the same name are defined differently in different places:",
                fg="red",
            )

            for duplicate_flavor, locations in duplicate_flavors.items():
                click.secho(f"'{duplicate_flavor}':", fg="red")
                for location in locations:
                    click.secho(f"- {location}", fg="red")
        elif strict:
            click.secho("Currently installed resources are valid.", fg="green")

    return all_valid


@click.option(
    "--remote",
    "-r",
    help=f"The remote in which to install Kueue {get_available_remotes_str()}",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Only print the commands to be executed without executing them.",
)
@kueue_commands.command(name="kueue-install")
def kueue_install(dry_run: bool, remote: Optional[str] = None):
    """Install Kueue on a cluster using Helm.

    Installs Kueue from the official OCI registry. Verifies that
    the cluster is reachable and that Kueue is not already installed before proceeding.
    """
    kubeconfig = get_kubeconfig_file(remote) if remote else None
    if kubeconfig:
        ensure_kubeconfig_exists(kubeconfig)
        ensure_remote_reachable(dry_run, kubeconfig)

    # Check for existence of Kubernetes cluster
    cmd = f"{kubectl("get nodes", kubeconfig)} | grep -q 'Ready'"
    try:
        if run_cmd(cmd, dry_run, check=True):
            raise click.ClickException("Could not find Kubernetes cluster.")
    except subprocess.CalledProcessError:
        raise click.ClickException("Could not find Kubernetes cluster.")

    if check_kueue_installed(dry_run, kubeconfig, quiet=True):
        click.secho("Kueue is already installed.", fg="green")
        return

    cmd = f"{helm("list", kubeconfig)} | grep -q kueue"
    namespace_exists = run_cmd(cmd, dry_run) == 0
    if namespace_exists and not dry_run:
        raise click.ClickException("Cannot install Kueue: namespace already exists.")

    cmd = helm(
        f"install kueue https://github.com/kubernetes-sigs/kueue/releases/download/v{KUEUE_VERSION}/kueue-{KUEUE_VERSION}.tgz --create-namespace --wait --timeout 300s",
        kubeconfig,
    )
    run_cmd(cmd, dry_run, check=True)

    if not dry_run:
        time.sleep(15 if remote else 5)

    all_crds_installed, _ = check_kueue_crds_installed(dry_run, kubeconfig)
    if not all_crds_installed and not dry_run:
        raise click.ClickException(
            f"There were problems while installing Kueue. It may not be installed or some CRDs may be missing. Please run 'reana-dev kueue-uninstall{f' --remote {remote}' if remote else ''}' and try again."
        )

    if dry_run:
        return

    click.secho("Kueue installed successfully.", fg="green")


@kueue_commands.command(name="kueue-diff")
def kueue_diff():
    """Display differences between the resources file and installed resources.

    Compares the desired state defined in the Kueue resources file with the
    current state of resources deployed in the cluster, showing what would
    change if a sync operation were performed.
    """
    check_kueue_installed(dry_run=False, expect_installed=True)
    kueue_resources = KueueResources()
    calc_resource_diff(dry_run=False, kueue_resources=kueue_resources)


@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Only print the commands to be executed without executing them.",
)
@click.option(
    "--remote",
    "-r",
    help=f"The remote to sync resources with {get_available_remotes_str()}",
)
@click.option(
    "--local-only",
    "-l",
    is_flag=True,
    help="Only sync resources to the local cluster.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force sync even if there are no changes.",
)
@kueue_commands.command(name="kueue-sync")
def kueue_sync(
    dry_run: bool,
    remote: Optional[str] = None,
    local_only: bool = False,
    force: bool = False,
):
    """Synchronize Kueue resources from the resources file to the cluster.

    Applies all changes needed to make the cluster state match the resources file,
    including:

    - Adding, modifying, or removing resource flavors

    - Adding or removing nodes (remote clusters)

    - Adding, modifying, or removing queues

    - Setting up MultiKueue connections for remote clusters
    """
    # Check if remote is valid
    if remote and remote not in get_remotes():
        raise click.ClickException(
            f"Remote {remote} is not in the list of available remotes: {get_available_remotes_str()}"
        )

    kueue_resources = KueueResources()

    ensure_kueue_set_up_on_nodes(dry_run, [None])
    if kueue_resources == get_resources_snapshot(dry_run) and not force:
        click.secho("No changes to sync.", fg="green")
        return

    (
        flavors_added,
        flavors_modified,
        flavors_removed,
        nodes_added,
        nodes_removed,
        queues_added_by_node,
        queues_modified_by_node,
        queues_removed_by_node,
    ) = calc_resource_diff(dry_run, kueue_resources)

    if not kueue_validate():
        raise click.ClickException(
            "There are problems with the Kueue configuration. Please fix them before syncing."
        )

    if not force:
        if not dry_run and not click.confirm(
            f"Apply changes{remote and f' (only {remote})' or ''}?", default=False
        ):
            return

    ensure_namespaces_exist(dry_run, kueue_resources, remote, local_only)
    ensure_kueue_set_up_on_nodes(
        dry_run,
        (
            [None, get_kubeconfig_file(remote)]
            if remote
            else [None] if local_only else kueue_resources.get_kubeconfigs()
        ),
    )

    # Ensure batch queues are applied to the manager
    apply_batch_queues(dry_run)

    # Apply new/modified job queues to all nodes
    apply_job_queues(dry_run, kueue_resources, remote)

    # For each removed remote job queue, remove the admission check and mirror queue from the manager
    for node, queues in queues_removed_by_node.items():
        if remote and node != remote and node != "local":
            # If the --remote option is given, skip any other nodes
            continue

        for queue in queues:
            kubeconfig = get_kubeconfig_file(node) if node != "local" else None
            remove_job_queue(dry_run, queue, kubeconfig)

            if node != "local":
                remove_admission_check(dry_run, queue)

    sync_resource_flavors(dry_run, kueue_resources, flavors_removed, remote, local_only)

    if not local_only:
        sync_multikueue_config(dry_run, kueue_resources, nodes_removed, remote)

    if dry_run:
        return

    click.secho("All resources synced successfully.", fg="green")


@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Only print the commands to be executed without executing them.",
)
@click.option(
    "--remote",
    "-r",
    help=f"The remote to uninstall Kueue from: {get_available_remotes_str()}",
)
@click.option(
    "--all-nodes",
    is_flag=True,
    help=f"Uninstall Kueue from all nodes: {get_available_remotes_str()}",
)
@click.option(
    "--delete-namespace",
    is_flag=True,
    help="Also delete the namespace specified in your resources file.",
)
@kueue_commands.command(name="kueue-uninstall")
def kueue_uninstall(
    dry_run: bool,
    remote: Optional[str] = None,
    all_nodes: bool = False,
    delete_namespace: bool = False,
):
    """Uninstall Kueue from one or more clusters.

    Removes all Kueue resources and the Kueue Helm release. Can uninstall from
    a specific remote cluster, the local cluster, or all clusters at once.
    """
    if all_nodes:
        if not dry_run and not click.confirm(
            f"Kueue will be uninstalled from the following nodes: local,{get_available_remotes_str()}. Are you sure?",
            default=False,
        ):
            return

        for remote in [None, *get_remotes()]:
            click.secho(f"\nUninstalling Kueue from {remote or 'local'}...", fg="blue")
            uninstall_kueue(dry_run, remote, delete_namespace)
    else:
        uninstall_kueue(dry_run, remote, delete_namespace)


@click.option(
    "--remote",
    "-r",
    help=f"The remote to check the status of: {get_available_remotes_str()}",
)
@kueue_commands.command(name="kueue-status")
def kueue_status(remote: Optional[str] = None):
    """Check the status of Kueue installation and resources.

    Displays comprehensive status information including:

    - Installation status and version
    - Resource flavors

    - Local and cluster queues

    - Available remote clusters

    - Kueue configuration in values.yaml
    """
    if remote and remote not in get_remotes():
        raise click.ClickException(
            f"Remote {remote} is not in the list of available remotes: {get_available_remotes_str()}"
        )

    kubeconfig = get_kubeconfig_file(remote) if remote else None

    # Check installation status
    click.secho("Installation status:", fg="blue")
    check_kueue_installed(dry_run=False, kubeconfig=kubeconfig)

    # List resource flavors
    click.secho("\nResource flavors:", fg="blue")
    run_cmd(f"{kubectl('get resourceflavors', kubeconfig)}", dry_run=False)

    # List local queues
    click.secho("\nLocal queues:", fg="blue")
    run_cmd(f"{kubectl('get localqueues', kubeconfig)}", dry_run=False)

    # List cluster queues
    click.secho("\nCluster queues:", fg="blue")
    run_cmd(f"{kubectl('get clusterqueues', kubeconfig)}", dry_run=False)

    # List available remotes
    if not kubeconfig:
        click.secho("\nAvailable remotes:", fg="blue")
        remotes = get_remotes()
        for remote in remotes:
            click.echo(f"- {remote} ({get_kubeconfig_file(remote)})")

    # Check Kueue setup in `values.yaml`
    click.secho("\nKueue setup in values.yaml:", fg="blue")
    validate_kueue_values_yaml(dry_run=False)


@click.option(
    "--name",
    "-n",
    help="Name of the resources file to generate.",
)
@kueue_commands.command(name="kueue-generate-resources")
def kueue_generate_resources(name: Optional[str] = None):
    """Generate a default kueue-resources.yaml template file.

    Creates a sample resources file with example flavors, nodes, and queues
    that can be customized for your specific setup.
    """
    if os.path.exists(KUEUE_RESOURCES_FILE):
        if not click.confirm(
            f"File {KUEUE_RESOURCES_FILE} already exists. Overwrite?", default=False
        ):
            return

    with open(f"{name}.yaml" if name else KUEUE_RESOURCES_FILE, "w") as f:
        f.write(
            """---
namespace: my-kueue-namespace

flavors:
  - name: small
    cpu: 1
    memory: 1Gi
  - name: medium
    cpu: 2
    memory: 2Gi
  - name: large
    cpu: 4
    memory: 4Gi

nodes:
  - name: local
    queues:
      - name: default
        flavors:
          - small
          - medium
          - large
      - name: other
        flavors:
          - medium
  - name: remote
    queues:
      - name: default
        flavors:
          - small
          - medium
"""
        )

    click.secho(f"Generated file: '{KUEUE_RESOURCES_FILE}'", fg="green")


kueue_commands_list = list(kueue_commands.commands.values())
