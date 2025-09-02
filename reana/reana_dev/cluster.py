# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023, 2025 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s cluster commands."""

import json
import os
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
@cluster_commands.command(name="cluster-create")
def cluster_create(
    mounts,
    mode,
    worker_nodes,
    extra_ports,
    disable_default_cni,
    kind_node_version,
    kubernetes,
):  # noqa: D301
    """Create new REANA cluster.

    \b
    Example:
       $ reana-dev cluster-create -m /var/reana:/var/reana
                                  -m /usr/share/local/mydata:/mydata
                                  --mode debug
                                  --extra-ports 30080 30443 30444
    """
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

        # Reserved ports mapped to their respective services
        RESERVED_DEBUG_PORTS = {
            "wdb": 31984,
            "maildev": 32580,
            "rabbitmq": 31672,
            "postgresql": 30432,
        }

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
            "extraPortMappings": extra_port_mappings,  # Only user-specified ports
        }

        if mode == "debug":
            mounts.append({"hostPath": find_reana_srcdir(), "containerPath": "/code"})
            control_plane["extraPortMappings"].extend(
                [
                    {"containerPort": port, "hostPort": port, "protocol": "TCP"}
                    for port in RESERVED_DEBUG_PORTS.values()
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
    "-v",
    "--values",
    default="helm/configurations/values-dev.yaml",
    help="Which Helm configuration values file to use? [default=helm/configurations/values-dev.yaml]",
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
def cluster_deploy(
    namespace,
    job_mounts,
    mode,
    values,
    exclude_components,
    admin_email,
    admin_password,
    instance_name,
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

    if mode in ("releasehelm") and values == "helm/configurations/values-dev.yaml":
        values = ""

    values_dict = {}
    if values:
        with open(os.path.join(get_srcdir("reana"), values)) as f:
            values_dict = yaml.safe_load(f.read()) or {}

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
    helm_install = f"cat <<EOF | helm install {instance_name} helm/reana -n {namespace} --create-namespace --wait -f -\n{values_yaml}\nEOF"

    cmds = []
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
def cluster_undeploy(namespace, instance_name, kubernetes):  # noqa: D301
    """Undeploy REANA cluster."""
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
            for cmd in [
                "colima exec -- sh -c 'sudo /bin/rm -rf /var/reana/*'",
            ]:
                run_command(cmd, "reana")
        elif kubernetes == "kind":
            for cmd in [
                "docker exec -i -t kind-control-plane sh -c '/bin/rm -rf /var/reana/*'",
            ]:
                run_command(cmd, "reana")
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
@cluster_commands.command(name="cluster-delete")
def cluster_delete(mounts, kubernetes):  # noqa: D301
    """Delete REANA cluster.

    \b
    Example:
       $ reana-dev cluster-delete -m /var/reana:/var/reana
    """
    cmds = []
    # delete cluster
    if kubernetes == "colima/k3s":
        pass  # not necessary
    elif kubernetes == "kind":
        cmds.append("kind delete cluster")
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
                    "colima exec -- sh -c 'sudo /bin/rm -rf {}/*'".format(local_path)
                )
            elif kubernetes == "kind":
                cmds.append("sudo /bin/rm -rf {}/*".format(local_path))
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
    for cmd in cmds:
        run_command(cmd, "reana")


cluster_commands_list = list(cluster_commands.commands.values())
