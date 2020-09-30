# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
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
@cluster_commands.command(name="cluster-create")
def cluster_create(mounts, mode, worker_nodes):  # noqa: D301
    """Create new REANA cluster.

    \b
    Example:
       $ reana-dev cluster-create -m /var/reana:/var/reana
                                  -m /usr/share/local/mydata:/mydata
                                  --mode debug
    """

    class literal_str(str):
        pass

    def literal_unicode_str(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

    def add_volume_mounts(node):
        """Add needed volumes mounts to the provided node."""

    yaml.add_representer(literal_str, literal_unicode_str)

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
        "extraPortMappings": [
            {"containerPort": 30080, "hostPort": 30080, "protocol": "TCP"},  # HTTP
            {"containerPort": 30443, "hostPort": 30443, "protocol": "TCP"},  # HTTPS
        ],
    }

    if mode in ("debug"):
        mounts.append({"hostPath": find_reana_srcdir(), "containerPath": "/code"})
        control_plane["extraPortMappings"].extend(
            [
                {"containerPort": 31984, "hostPort": 31984, "protocol": "TCP"},  # wdb
                {
                    "containerPort": 32580,
                    "hostPort": 32580,
                    "protocol": "TCP",
                },  # maildev
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

    cluster_create = "cat <<EOF | kind create cluster --config=-\n{cluster_config}\nEOF"
    cluster_create = cluster_create.format(cluster_config=yaml.dump(cluster_config))

    # create cluster
    run_command(cluster_create, "reana")

    # pull Docker images
    if mode in ("releasepypi", "latest", "debug"):
        for cmd in [
            "reana-dev docker-pull -c reana",
            "reana-dev kind-load-docker-image -c reana",
        ]:
            run_command(cmd, "reana")


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
@click.option("--no-cache", is_flag=True, help="Do not use Docker image layer cache.")
@cluster_commands.command(name="cluster-build")
def cluster_build(
    build_arg, mode, exclude_components, no_cache,
):  # noqa: D301
    """Build REANA cluster.

    \b
    Example:
       $ reana-dev cluster-build --exclude-components=r-ui,r-a-vomsproxy
                                 -b COMPUTE_BACKENDS=kubernetes,htcondorcern,slurmcern
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
    cmds.append(cmd)
    # load built Docker images into cluster
    if mode in ("releasepypi", "latest", "debug"):
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
    "--admin-email", required=True, help="Admin user email address",
)
@click.option(
    "--admin-password", required=True, help="Admin user password",
)
@click.option(
    "--instance-name", default="reana", help="REANA instance name",
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
        values = "helm/reana/values.yaml"

    values_dict = {}
    with open(os.path.join(get_srcdir("reana"), values)) as f:
        values_dict = yaml.safe_load(f.read())

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
            values_dict["components"]["reana_ui"]["enabled"] = False

    helm_install = "cat <<EOF | helm install reana helm/reana -n {namespace} --create-namespace --wait -f -\n{values}\nEOF".format(
        namespace=namespace, values=values_dict and yaml.dump(values_dict) or "",
    )
    cmds = []
    if mode in ("debug"):
        cmds.append("reana-dev python-install-eggs")
        cmds.append("reana-dev git-submodule --update")
    cmds.extend(
        [
            "helm dep update helm/reana",
            helm_install,
            "kubectl config set-context --current --namespace={}".format(namespace),
            os.path.join(
                get_srcdir("reana"),
                f"scripts/create-admin-user.sh {instance_name} {admin_email} {admin_password}",
            ),
            os.path.join(
                get_srcdir("reana"),
                f"scripts/create-quotas.sh {instance_name} {admin_email} {admin_password}",
            ),
        ]
    )
    for cmd in cmds:
        run_command(cmd, "reana")


@cluster_commands.command(name="cluster-undeploy")
def cluster_undeploy():  # noqa: D301
    """Undeploy REANA cluster."""
    is_deployed = run_command("helm ls", "reana", return_output=True)
    if "reana" in is_deployed:
        for cmd in [
            "helm uninstall reana -n default",
            "kubectl get secrets -o custom-columns=':metadata.name' | grep reana | xargs kubectl delete secret",
            "docker exec -i -t kind-control-plane sh -c '/bin/rm -rf /var/reana/*'",
        ]:
            run_command(cmd, "reana")
    else:
        msg = "No REANA cluster to undeploy."
        display_message(msg, "reana")


@cluster_commands.command(name="cluster-stop")
def cluster_stop():
    """Stop currently running REANA cluster."""
    cmd = "docker stop kind-control-plane"
    run_command(cmd, "reana")


@cluster_commands.command(name="cluster-start")
def cluster_start():
    """Start previously stopped REANA cluster."""
    cmd = "docker start kind-control-plane"
    run_command(cmd, "reana")


@cluster_commands.command(name="cluster-pause")
def cluster_pause():
    """Pause all processes within REANA cluster."""
    cmd = "docker pause kind-control-plane"
    run_command(cmd, "reana")


@cluster_commands.command(name="cluster-unpause")
def cluster_unpause():
    """Unpause all processes within REANA cluster."""
    cmd = "docker unpause kind-control-plane"
    run_command(cmd, "reana")


@click.option(
    "-m",
    "--mount",
    "mounts",
    multiple=True,
    help="Which local path directories are to be deleted? [local_path:cluster_node_path]",
)
@cluster_commands.command(name="cluster-delete")
def cluster_delete(mounts):  # noqa: D301
    """Delete REANA cluster.

    \b
    Example:
       $ reana-dev cluster-delete -m /var/reana:/var/reana
    """
    cmds = []
    # delete cluster
    cmds.append("kind delete cluster")
    # remove only local paths where cluster path starts with /var/reana for safety
    for mount in mounts:
        local_path, cluster_node_path = mount.split(":")
        if cluster_node_path.startswith("/var/reana"):
            cmds.append("sudo rm -rf {}/*".format(local_path))
        else:
            msg = "Directory {} will not be deleted for safety reasons.".format(
                local_path
            )
            display_message(msg, "reana")
    # execute commands
    for cmd in cmds:
        run_command(cmd, "reana")


cluster_commands_list = list(cluster_commands.commands.values())
