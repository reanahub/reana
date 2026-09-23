# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023, 2024, 2025, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s cluster commands."""

import json
import os
import shlex
import subprocess
import sys

import click
import yaml

from reana.reana_dev.utils import (
    display_message,
    find_reana_srcdir,
    find_standard_component_name,
    get_srcdir,
    print_colima_start_help,
    run_command,
    validate_mode_option,
)

SHARED_STORAGE_BACKENDS = ("hostpath", "cephfs")
CEPHFS_VALUES_FILE = "helm/configurations/values-dev-cephfs.yaml"
KIND_CEPHFS_NODE_LABEL = "reana.io/infrastructure-storage=cephfs"
KIND_CONTROL_PLANE_CONTAINER = "kind-control-plane"
RESERVED_DEBUG_PORTS = {
    "wdb": 31984,
    "maildev": 32580,
    "rabbitmq": 31672,
    "postgresql": 30432,
}


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


def merge_values_dicts(base_values, overlay_values):
    """Recursively merge values dictionaries."""
    for key, value in overlay_values.items():
        if isinstance(value, dict) and isinstance(base_values.get(key), dict):
            merge_values_dicts(base_values[key], value)
        else:
            base_values[key] = value
    return base_values


def default_cluster_values_files(mode, shared_storage_backend, values_files):
    """Return the values files that should be layered for cluster deployment."""
    values_files = tuple(values_files)
    if not values_files and mode != "releasehelm":
        values_files = ("helm/configurations/values-dev.yaml",)

    # The backend selector is authoritative and therefore has final precedence.
    if shared_storage_backend == "cephfs":
        values_files = tuple(
            values_file
            for values_file in values_files
            if values_file != CEPHFS_VALUES_FILE
        )
        values_files += (CEPHFS_VALUES_FILE,)

    return values_files


def load_cluster_values(values_files):
    """Load and merge the requested Helm values files."""
    values_dict = {}
    for values_file in values_files:
        with open(os.path.join(get_srcdir("reana"), values_file)) as values_stream:
            merge_values_dicts(
                values_dict,
                yaml.safe_load(values_stream.read()) or {},
            )
    return values_dict


def cluster_data_roots(shared_storage_backend):
    """Return the node-side data roots owned by the effective deployment.

    The shared workspace root is always owned. The CephFS overlay moves the
    database and message broker onto a separate infrastructure hostPath, so
    that root is read back from the overlay instead of being hard-coded here.
    """
    data_roots = ["/var/reana"]
    if shared_storage_backend != "cephfs":
        return data_roots

    infrastructure_storage = load_cluster_values((CEPHFS_VALUES_FILE,)).get(
        "infrastructure_storage", {}
    )
    if infrastructure_storage.get("backend") == "hostpath":
        root_path = infrastructure_storage.get("hostpath", {}).get("root_path")
        if root_path and root_path not in data_roots:
            data_roots.append(root_path)
    return data_roots


def validate_shared_storage_backend(kubernetes, shared_storage_backend):
    """Reject unsupported local shared storage combinations."""
    if shared_storage_backend == "cephfs" and kubernetes != "kind":
        display_message(
            "[ERROR] Local CephFS shared storage is currently supported only with --kubernetes kind. Exiting.",
            "reana",
        )
        sys.exit(1)


def cephfs_helper_script(script_name):
    """Return the absolute path to a local CephFS helper script."""
    return os.path.join(get_srcdir("reana"), "scripts", script_name)


def cephfs_state_file():
    """Return the host-side lifecycle state path for the local Kind backend."""
    state_dir = os.getenv("REANA_DEV_STATE_DIR")
    if not state_dir:
        state_home = os.getenv(
            "XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state")
        )
        state_dir = os.path.join(state_home, "reana-dev")
    return os.path.join(state_dir, "kind-cephfs.state")


def load_cephfs_state():
    """Load the tab-delimited local CephFS lifecycle record."""
    state = {"devices": []}
    state_path = cephfs_state_file()
    if not os.path.exists(state_path):
        return state

    with open(state_path, encoding="utf-8") as state_stream:
        for line in state_stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                continue
            if fields[0] == "device" and len(fields) == 3:
                state["devices"].append({"path": fields[1], "backing_file": fields[2]})
            else:
                state[fields[0]] = fields[1]
    return state


def selected_shared_storage_backend(requested_backend, kubernetes=None):
    """Prefer persisted lifecycle state when deleting a local cluster.

    An explicitly requested backend always wins, so that a stale record can
    never steer a command the caller has already made unambiguous. The record
    is also only consulted for the Kubernetes provider that wrote it.
    """
    state = load_cephfs_state()
    persisted_backend = state.get("backend")
    persisted_kubernetes = state.get("kubernetes")

    if requested_backend:
        if (
            persisted_backend in SHARED_STORAGE_BACKENDS
            and persisted_backend != requested_backend
            and persisted_kubernetes == kubernetes
        ):
            display_message(
                f"[WARNING] Lifecycle state records the '{persisted_backend}' shared "
                f"storage backend, but '{requested_backend}' was requested explicitly; "
                "using the requested backend.",
                "reana",
            )
        return requested_backend, state

    if persisted_backend in SHARED_STORAGE_BACKENDS:
        if kubernetes is not None and persisted_kubernetes != kubernetes:
            display_message(
                f"[WARNING] Ignoring lifecycle state recorded for --kubernetes "
                f"'{persisted_kubernetes}'; '{kubernetes}' was selected. Pass "
                "--shared-storage-backend explicitly to act on that state.",
                "reana",
            )
            return "hostpath", state
        return persisted_backend, state

    return "hostpath", state


def kind_cephfs_node_name():
    """Return the uniquely labelled Kind node that owns the local Ceph data."""
    node_name = run_command(
        [
            "kubectl",
            "get",
            "nodes",
            "-l",
            KIND_CEPHFS_NODE_LABEL,
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ],
        "reana",
        return_output=True,
    )
    if not node_name:
        raise click.ClickException(
            f"No Kubernetes node has the required label {KIND_CEPHFS_NODE_LABEL}."
        )
    return node_name


def extend_kind_control_plane_for_debug(control_plane, mounts):
    """Mount the source tree and reserved debug ports in Kind debug mode."""
    mounts.append({"hostPath": find_reana_srcdir(), "containerPath": "/code"})
    control_plane["extraPortMappings"].extend(
        [
            {"containerPort": port, "hostPort": port, "protocol": "TCP"}
            for port in RESERVED_DEBUG_PORTS.values()
        ]
    )


def validate_multi_node_mounts(mounts, worker_nodes, shared_storage_backend):
    """Require a shared volume mount when creating a multi-node cluster."""
    if worker_nodes <= 0 or shared_storage_backend == "cephfs":
        return

    mount_targets = [x["containerPath"].strip("/") for x in mounts]
    if "var/reana" in mount_targets or "var" in mount_targets:
        return

    click.echo(
        "[ERROR] For multi-node deployments, one has to use a shared storage volume for cluster nodes."
    )
    click.echo(
        "[ERROR] Example: reana-dev cluster-create -m /var/reana:/var/reana --worker-nodes 2."
    )
    sys.exit(1)


@click.group()
def cluster_commands():
    """Cluster commands group."""


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
    callback=validate_mode_option,
    help="In which mode to run REANA cluster? (releasehelm,releasepypi,latest,debug) [default=latest]",
)
@click.option("--worker-nodes", default=0, help="How many worker nodes? [default=0]")
@click.option(
    "--extra-ports",
    multiple=True,
    type=int,
    default=(30080, 30443),
    help="Extra ports to expose, format: hostPort (containerPort will be the same)",
)
@click.option(
    "--disable-default-cni",
    is_flag=True,
    help="Disable default CNI and use e.g. Calico.",
)
@click.option(
    "--kind-node-version",
    help="Which kindest/node image version to use?",
)
@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@click.option(
    "--shared-storage-backend",
    type=click.Choice(SHARED_STORAGE_BACKENDS),
    default="hostpath",
    help="Which shared workspace backend to prepare? (hostpath, cephfs). [default=hostpath]",
)
@cluster_commands.command(name="cluster-create")
def cluster_create(
    mounts,
    mode,
    worker_nodes,
    extra_ports,
    disable_default_cni,
    kind_node_version,
    kubernetes,
    shared_storage_backend,
):  # noqa: D301
    """Create new REANA cluster.

    \b
    Example:
       $ reana-dev cluster-create -m /var/reana:/var/reana
                                  -m /usr/share/local/mydata:/mydata
                                  --mode debug
                                  --extra-ports 30080 30443 30444
    """
    validate_shared_storage_backend(kubernetes, shared_storage_backend)
    if kubernetes == "colima/k3s":
        print_colima_start_help()
        sys.exit(1)
    elif kubernetes == "kind":

        class literal_str(str):
            pass

        def literal_unicode_str(dumper, data):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

        def add_volume_mounts(node):
            """Add needed volumes mounts to the provided node."""

        yaml.add_representer(literal_str, literal_unicode_str)

        # Get reserved port values
        reserved_ports = set(RESERVED_DEBUG_PORTS.values())

        # Detect conflicting ports
        conflicting_ports = set(extra_ports) & reserved_ports
        if conflicting_ports:
            conflict_details = [
                f"{port} ({service})"
                for service, port in RESERVED_DEBUG_PORTS.items()
                if port in conflicting_ports
            ]
            raise click.BadParameter(
                f"The following ports are reserved for debug mode and cannot be used: {', '.join(conflict_details)}"
            )

        # Convert extra ports into mappings
        extra_port_mappings = [
            {"containerPort": port, "hostPort": port, "protocol": "TCP"}
            for port in extra_ports
        ]

        node_labels = ["ingress-ready=true"]
        if shared_storage_backend == "cephfs":
            node_labels.append(KIND_CEPHFS_NODE_LABEL)

        control_plane = {
            "role": "control-plane",
            "kubeadmConfigPatches": [
                literal_str(
                    "kind: InitConfiguration\n"
                    "nodeRegistration:\n"
                    "  kubeletExtraArgs:\n"
                    f'    node-labels: "{",".join(node_labels)}"\n'
                )
            ],
            "extraPortMappings": extra_port_mappings,  # Only user-specified ports
        }

        if mode == "debug":
            extend_kind_control_plane_for_debug(control_plane, mounts)

        validate_multi_node_mounts(mounts, worker_nodes, shared_storage_backend)

        nodes = [{"role": "worker"} for _ in range(worker_nodes)] + [control_plane]
        for node in nodes:
            node["extraMounts"] = mounts

        cluster_config = {
            "kind": "Cluster",
            "apiVersion": "kind.x-k8s.io/v1alpha4",
            "nodes": nodes,
        }

        if disable_default_cni:
            cluster_config["networking"] = {
                "disableDefaultCNI": True,
                "podSubnet": "192.168.0.0/16",
            }

        # detect user container technology (Docker vs Podman)
        kind_provider = ""
        docker_version_output = run_command("docker version", return_output=True)
        if docker_version_output and "Podman Engine" in docker_version_output:
            kind_provider = "KIND_EXPERIMENTAL_PROVIDER=podman"

        # create cluster
        image_flag = ""
        if kind_node_version is not None:
            image_flag = f"--image kindest/node:{kind_node_version}"

        cluster_create = "cat <<EOF | {kind_provider} kind create cluster {image_flag} --config=-\n{cluster_config}\nEOF".format(
            kind_provider=kind_provider,
            image_flag=image_flag,
            cluster_config=yaml.dump(cluster_config),
        )
        run_command(cluster_create, "reana")
        run_command(
            "docker exec kind-control-plane sh -c 'mkdir -p /var/reana && chmod g+rwx /var/reana'",
            "reana",
        )
        if shared_storage_backend == "cephfs":
            state_file = cephfs_state_file()
            node_name = kind_cephfs_node_name()
            for cmd in [
                [
                    "/bin/sh",
                    cephfs_helper_script("setup-kind-rook-loop-devices.sh"),
                    KIND_CONTROL_PLANE_CONTAINER,
                    node_name,
                    state_file,
                ],
                [
                    "/bin/sh",
                    cephfs_helper_script("deploy-kind-rook-cephfs.sh"),
                    state_file,
                ],
            ]:
                run_command(cmd, "reana")
    else:
        display_message(
            f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
            "reana",
        )
        sys.exit(1)

    # pull Docker images
    if mode in ("releasepypi", "latest", "debug"):
        for cmd in [
            "reana-dev docker-pull -c reana",
        ]:
            run_command(cmd, "reana")
        if kubernetes == "kind":
            for cmd in [
                "reana-dev kind-load-docker-image -c reana",
            ]:
                run_command(cmd, "reana")


@click.option(
    "--build-arg",
    "-b",
    multiple=True,
    help="Any build arguments? (e.g. `-b COMPUTE_BACKENDS=kubernetes,htcondorcern,slurmcern,compute4punch`)",
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
@click.option("--no-cache", is_flag=True, help="Do not use Docker image layer cache.")
@click.option("--skip-load", is_flag=True, help="Do not load images into kind node(s).")
@click.option(
    "--parallel",
    "-p",
    default=1,
    type=click.IntRange(min=1),
    help="Number of docker images to build in parallel.",
)
@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@cluster_commands.command(name="cluster-build")
def cluster_build(
    build_arg, mode, exclude_components, no_cache, skip_load, parallel, kubernetes
):  # noqa: D301
    """Build REANA cluster.

    \b
    Example:
       $ reana-dev cluster-build --exclude-components=r-ui,r-a-vomsproxy
                                 -b COMPUTE_BACKENDS=kubernetes,htcondorcern,slurmcern,compute4punch
                                 --mode debug
                                 --no-cache
    """
    cmds = []
    # initalise common submodules
    if mode in ("latest", "debug"):
        cmds.append("reana-dev git-submodule --update")
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
    cmd += f" --parallel {parallel}"
    cmds.append(cmd)
    if not skip_load and mode in ("releasepypi", "latest", "debug"):
        # load built Docker images into cluster
        if kubernetes == "kind":
            cmd = "reana-dev kind-load-docker-image -c CLUSTER"
            if exclude_components:
                cmd += " --exclude-components {}".format(exclude_components)
            cmds.append(cmd)
    # execute commands
    for cmd in cmds:
        run_command(cmd, "reana")


@cluster_commands.command(name="cluster-deploy")
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
    callback=validate_mode_option,
    help="In which mode to run REANA cluster? (releasehelm,releasepypi,latest,debug) [default=latest]",
)
@click.option(
    "-f",
    "-v",
    "--values",
    multiple=True,
    help=(
        "Helm values file(s), layered in order. When omitted, "
        "helm/configurations/values-dev.yaml is used except in releasehelm mode. "
        "The selected shared-storage overlay is applied last."
    ),
)
@click.option(
    "--set",
    "helm_set_values",
    multiple=True,
    help=(
        "Set a Helm value after applying the values files. Can be passed "
        "multiple times, using NAME=VALUE syntax."
    ),
)
@click.option(
    "--exclude-components",
    default="",
    help="Which components to exclude from build? [c1,c2,c3]",
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
    "--instance-name",
    default="reana",
    help="REANA instance name",
)
@click.option(
    "--shared-storage-backend",
    type=click.Choice(SHARED_STORAGE_BACKENDS),
    default="hostpath",
    help="Which shared workspace backend to configure? (hostpath, cephfs). [default=hostpath]",
)
@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
def cluster_deploy(
    namespace,
    job_mounts,
    mode,
    values,
    helm_set_values,
    exclude_components,
    admin_email,
    admin_password,
    instance_name,
    shared_storage_backend,
    kubernetes,
):  # noqa: D301
    """Deploy REANA cluster.

    \b
    Example:
       $ reana-dev cluster-deploy --mode debug
                                  --exclude-components=r-ui
                                  --admin-email john.doe@example.org
                                  --admin-password mysecretpassword
    """

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

    validate_shared_storage_backend(kubernetes, shared_storage_backend)
    values = default_cluster_values_files(mode, shared_storage_backend, values)

    values_dict = {}
    if values:
        values_dict = load_cluster_values(values)

    job_mount_config = job_mounts_to_config(job_mounts)
    if job_mount_config:
        values_dict.setdefault("components", {}).setdefault(
            "reana_workflow_controller", {}
        ).setdefault("environment", {})["REANA_JOB_HOSTPATH_MOUNTS"] = job_mount_config

    if mode in ("debug"):
        values_dict.setdefault("debug", {})["enabled"] = True

    if exclude_components:
        standard_named_exclude_components = [
            find_standard_component_name(c) for c in exclude_components.split(",")
        ]
        if "reana-ui" in standard_named_exclude_components:
            values_dict.setdefault("components", {}).setdefault("reana_ui", {})[
                "enabled"
            ] = False

    # set arbitrary big value for `width` to prevent PyYAML from wrapping long lines
    values_yaml = yaml.dump(values_dict, width=100000) if values_dict else ""
    helm_set_args = " ".join(f"--set {shlex.quote(value)}" for value in helm_set_values)
    if helm_set_args:
        helm_set_args = f" {helm_set_args}"
    helm_install = (
        f"cat <<EOF | helm install {instance_name} helm/reana -n {namespace} "
        f"--create-namespace --wait -f -{helm_set_args}\n{values_yaml}\nEOF"
    )

    cmds = []
    if shared_storage_backend == "cephfs":
        cmds.append(
            [
                "/bin/sh",
                cephfs_helper_script("deploy-kind-rook-cephfs.sh"),
                "--check-only",
                cephfs_state_file(),
            ]
        )
    if mode in ("debug"):
        cmds.append("reana-dev python-install-eggs")
        cmds.append("reana-dev git-submodule --update")
    cmds.extend(
        [
            "helm dep update helm/reana",
            helm_install,
            f"kubectl config set-context --current --namespace={namespace}",
            os.path.join(
                get_srcdir("reana"),
                f"scripts/create-admin-user.sh {namespace} {instance_name} {admin_email} {admin_password}",
            ),
        ]
    )
    for cmd in cmds:
        run_command(cmd, "reana")


@cluster_commands.command(name="cluster-undeploy")
@click.option(
    "--namespace", "-n", default="default", help="Kubernetes namespace [default]"
)
@click.option(
    "--instance-name",
    default="reana",
    help="REANA instance name",
)
@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@click.option(
    "--shared-storage-backend",
    type=click.Choice(SHARED_STORAGE_BACKENDS),
    default=None,
    help="Deployed shared workspace backend. [default: detect from lifecycle state]",
)
def cluster_undeploy(
    namespace, instance_name, kubernetes, shared_storage_backend
):  # noqa: D301
    """Undeploy REANA cluster."""
    shared_storage_backend, _ = selected_shared_storage_backend(
        shared_storage_backend, kubernetes
    )
    data_roots = cluster_data_roots(shared_storage_backend)
    helm_releases = run_command(
        f"helm ls --short -n {namespace}", "reana", return_output=True
    ).splitlines()
    if instance_name in helm_releases:
        for cmd in [
            f"helm uninstall {instance_name} -n {namespace}",
            f"kubectl get secrets -n {namespace} -o custom-columns=':metadata.name' | grep {instance_name} | xargs kubectl delete secret -n {namespace}",
        ]:
            run_command(cmd, "reana")
        if kubernetes == "colima/k3s":
            for data_root in data_roots:
                run_command(
                    f"colima exec -- sh -c 'sudo /bin/rm -rf {data_root}/*'", "reana"
                )
        elif kubernetes == "kind":
            # No `-i -t` here: allocating a TTY makes this fail with "cannot
            # attach stdin to a TTY-enabled container" whenever undeploy runs
            # non-interactively (CI, a pipeline, a background shell), which
            # would abort the command before the remaining data roots are
            # cleaned.
            for data_root in data_roots:
                run_command(
                    "docker exec kind-control-plane sh -c "
                    f"'/bin/rm -rf {data_root}/*'",
                    "reana",
                )
        else:
            display_message(
                f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
                "reana",
            )
            sys.exit(1)
    else:
        msg = "No REANA cluster to undeploy."
        display_message(msg, "reana")


@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@cluster_commands.command(name="cluster-stop")
def cluster_stop(kubernetes):
    """Stop currently running REANA cluster."""
    if kubernetes == "colima/k3s":
        pass  # not necessary
    elif kubernetes == "kind":
        cmd = "docker stop kind-control-plane"
        run_command(cmd, "reana")
    else:
        display_message(
            f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
            "reana",
        )
        sys.exit(1)


@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@cluster_commands.command(name="cluster-start")
def cluster_start(kubernetes):
    """Start previously stopped REANA cluster."""
    if kubernetes == "colima/k3s":
        pass  # not necessary
    elif kubernetes == "kind":
        cmd = "docker start kind-control-plane"
        run_command(cmd, "reana")
    else:
        display_message(
            f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
            "reana",
        )
        sys.exit(1)


@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@cluster_commands.command(name="cluster-pause")
def cluster_pause(kubernetes):
    """Pause all processes within REANA cluster."""
    if kubernetes == "colima/k3s":
        pass  # not necessary
    elif kubernetes == "kind":
        cmd = "docker pause kind-control-plane"
        run_command(cmd, "reana")
    else:
        display_message(
            f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
            "reana",
        )
        sys.exit(1)


@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@cluster_commands.command(name="cluster-unpause")
def cluster_unpause(kubernetes):
    """Unpause all processes within REANA cluster."""
    if kubernetes == "colima/k3s":
        pass  # not necessary
    elif kubernetes == "kind":
        cmd = "docker unpause kind-control-plane"
        run_command(cmd, "reana")
    else:
        display_message(
            f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
            "reana",
        )
        sys.exit(1)


@click.option(
    "-m",
    "--mount",
    "mounts",
    multiple=True,
    help="Which local path directories are to be deleted? [local_path:cluster_node_path]",
)
@click.option(
    "--kubernetes",
    "-k",
    default="kind",
    help="What Kubernetes cluster to use? (kind, colima/k3s). [default=kind]",
)
@click.option(
    "--shared-storage-backend",
    type=click.Choice(SHARED_STORAGE_BACKENDS),
    default=None,
    help="Prepared shared workspace backend. [default: detect from lifecycle state]",
)
@click.option(
    "--namespace", "-n", default="default", help="Kubernetes namespace [default]"
)
@click.option(
    "--instance-name",
    default="reana",
    help="REANA instance name",
)
@cluster_commands.command(name="cluster-delete")
def cluster_delete(
    mounts, kubernetes, shared_storage_backend, namespace, instance_name
):  # noqa: D301
    """Delete REANA cluster.

    \b
    Example:
       $ reana-dev cluster-delete -m /var/reana:/var/reana
    """
    cmds = []
    shared_storage_backend, _ = selected_shared_storage_backend(
        shared_storage_backend, kubernetes
    )
    validate_shared_storage_backend(kubernetes, shared_storage_backend)
    if kubernetes == "kind" and shared_storage_backend == "cephfs":
        state_file = cephfs_state_file()
        cmds.extend(
            [
                (
                    "REANA consumer removal",
                    [
                        "helm",
                        "uninstall",
                        instance_name,
                        "-n",
                        namespace,
                        "--ignore-not-found",
                        "--wait",
                        "--timeout",
                        "5m",
                    ],
                ),
                (
                    "Rook teardown",
                    [
                        "/bin/sh",
                        cephfs_helper_script("undeploy-kind-rook-cephfs.sh"),
                        state_file,
                    ],
                ),
                (
                    "loop-device cleanup",
                    [
                        "/bin/sh",
                        cephfs_helper_script("cleanup-kind-rook-loop-devices.sh"),
                        state_file,
                    ],
                ),
            ]
        )
    # delete cluster
    if kubernetes == "colima/k3s":
        pass  # not necessary
    elif kubernetes == "kind":
        cmds.append(("Kind cluster deletion", "kind delete cluster"))
    else:
        display_message(
            f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
            "reana",
        )
        sys.exit(1)
    # remove only local paths where cluster path starts with /var/reana for safety
    for mount in mounts:
        local_path, cluster_node_path = mount.split(":")
        if cluster_node_path.startswith("/var/reana"):
            if kubernetes == "colima/k3s":
                cmds.append(
                    (
                        f"host mount cleanup ({local_path})",
                        "colima exec -- sh -c 'sudo /bin/rm -rf {}/*'".format(
                            local_path
                        ),
                    )
                )
            elif kubernetes == "kind":
                cmds.append(
                    (
                        f"host mount cleanup ({local_path})",
                        "sudo /bin/rm -rf {}/*".format(local_path),
                    )
                )
            else:
                display_message(
                    f"[ERROR] Unsupported --kubernetes option value '{kubernetes}'. Must be 'kind' [default] or 'colima/k3s'. Exiting.",
                    "reana",
                )
                sys.exit(1)
        else:
            msg = "Directory {} will not be deleted for safety reasons.".format(
                local_path
            )
            display_message(msg, "reana")
    # execute commands
    failures = []
    for phase, cmd in cmds:
        try:
            run_command(cmd, "reana", exit_on_error=False)
        except (OSError, subprocess.CalledProcessError) as err:
            failures.append(f"{phase}: {err}")

    if failures:
        raise click.ClickException(
            "Cluster deletion completed with failed phase(s): " + "; ".join(failures)
        )


cluster_commands_list = list(cluster_commands.commands.values())
