# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2021, 2023, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for reana-dev helm-* commands."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

HELM_CHART = Path(__file__).parent.parent / "helm" / "reana"
HELM_TEST_SECRETS = {
    "cache": {"user": "test", "password": "test"},
    "database": {"user": "test", "password": "test"},
    "message_broker": {"user": "test", "password": "test"},
    "reana": {"REANA_SECRET_KEY": "test"},
}


def _render_helm_chart(tmp_path, values=None, namespace="default", check=True):
    """Render the REANA Helm chart with common test secrets."""
    values_file = tmp_path / "values.yaml"
    chart_values = {"secrets": HELM_TEST_SECRETS}
    chart_values.update(values or {})
    values_file.write_text(yaml.safe_dump(chart_values))

    if not any((HELM_CHART / "charts").glob("*.tgz")):
        subprocess.run(
            ["helm", "dependency", "update", str(HELM_CHART)],
            capture_output=True,
            check=True,
        )

    return subprocess.run(
        [
            "helm",
            "template",
            "reana",
            str(HELM_CHART),
            "--namespace",
            namespace,
            "--kube-version",
            "1.29.0",
            "-f",
            str(values_file),
        ],
        capture_output=True,
        text=True,
        check=check,
    )


def _rendered_documents(rendered):
    """Return non-empty resources from Helm output."""
    return [document for document in yaml.safe_load_all(rendered.stdout) if document]


@pytest.mark.parametrize(
    "original,docker_images, expected",
    [
        (
            "docker.io/reanahub/reana-job-controller:0.8.0-alpha.3 \\\n"
            " docker.io/reanahub/reana-message-broker:0.8.0-alpha.1 \\",
            [
                "docker.io/reanahub/reana-job-controller:0.8.1",
                "docker.io/reanahub/reana-message-broker:0.8.0-alpha.1",
            ],
            "docker.io/reanahub/reana-job-controller:0.8.1 \\\n"
            " docker.io/reanahub/reana-message-broker:0.8.0-alpha.1 \\",
        ),
        (
            "image: docker.io/reanahub/reana-server:0.8.0-alpha.2\nenvironment:",
            ["docker.io/reanahub/reana-server:0.8.1"],
            "image: docker.io/reanahub/reana-server:0.8.1\nenvironment:",
        ),
    ],
)
def test_replace_docker_images(original, docker_images, expected):
    """
    Purpose of the test is to check if internal _replace_docker_images function
    properly replaces docker images (name + tag) followed by empty space or a new line
    """
    from reana.reana_dev.helm import _replace_docker_images

    assert _replace_docker_images(original, docker_images) == expected


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
def test_nginx_config_quoted_origins(tmp_path):
    """Quoted origins in a security header value must be escaped correctly in the rendered nginx config."""
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        yaml.dump(
            {
                "components": {
                    "reana_ui": {
                        "nginx": {
                            "security_headers": {
                                "permissions_policy": 'geolocation=(self "https://example.org")'
                            }
                        }
                    }
                },
                "secrets": {
                    "cache": {"user": "test", "password": "test"},
                    "database": {"user": "test", "password": "test"},
                    "message_broker": {"user": "test", "password": "test"},
                    "reana": {"REANA_SECRET_KEY": "test"},
                },
            }
        )
    )

    # Fetch charts if they are missing
    if not any((HELM_CHART / "charts").glob("*.tgz")):
        subprocess.run(
            ["helm", "dependency", "update", str(HELM_CHART)],
            capture_output=True,
            check=True,
        )

    rendered = subprocess.run(
        ["helm", "template", "reana", str(HELM_CHART), "-f", str(values_file)],
        capture_output=True,
        text=True,
        check=True,
    )

    nginx_conf = None
    for doc in yaml.safe_load_all(rendered.stdout):
        if (
            doc
            and doc.get("kind") == "ConfigMap"
            and "nginx" in doc["metadata"]["name"]
        ):
            nginx_conf = doc["data"]["reana-ui.conf"]
            break

    assert nginx_conf is not None, "nginx ConfigMap not found in rendered chart"
    assert (
        r'add_header Permissions-Policy "geolocation=(self \"https://example.org\")" always;'
        in nginx_conf
    )


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
@pytest.mark.parametrize(
    "job_controller_environment",
    [
        pytest.param({}, id="no-operator-override"),
        pytest.param(
            {
                "REANA_VETTED_CONTAINER_IMAGES": (
                    '{"enabled": false, "allowlist": ["stale.example/image"]}'
                )
            },
            id="chart-policy-overrides-operator-environment",
        ),
    ],
)
def test_job_controller_receives_vetted_container_images(
    tmp_path, job_controller_environment
):
    """Vetted-image settings must reach job-controller as nested JSON."""
    values_file = tmp_path / "values.yaml"
    vetted_images = {
        "enabled": True,
        "allowlist": ["docker.io/snakemake/snakemake:v9.22.0"],
    }
    values_file.write_text(
        yaml.dump(
            {
                "components": {
                    "reana_job_controller": {
                        "environment": job_controller_environment,
                    }
                },
                "secrets": {
                    "cache": {"user": "test", "password": "test"},
                    "database": {"user": "test", "password": "test"},
                    "message_broker": {"user": "test", "password": "test"},
                    "reana": {"REANA_SECRET_KEY": "test"},
                },
                "vetted_container_images": vetted_images,
            }
        )
    )

    if not any((HELM_CHART / "charts").glob("*.tgz")):
        subprocess.run(
            ["helm", "dependency", "update", str(HELM_CHART)],
            capture_output=True,
            check=True,
        )

    rendered = subprocess.run(
        ["helm", "template", "reana", str(HELM_CHART), "-f", str(values_file)],
        capture_output=True,
        text=True,
        check=True,
    )

    workflow_controller_env = None
    for document in yaml.safe_load_all(rendered.stdout):
        if not document or document.get("kind") != "Deployment":
            continue
        for container in document["spec"]["template"]["spec"]["containers"]:
            for env_var in container.get("env", []):
                if env_var["name"] == "REANA_JOB_CONTROLLER_ENV_VARS":
                    workflow_controller_env = env_var["value"]
                    break

    assert workflow_controller_env is not None
    job_controller_env = json.loads(workflow_controller_env)
    assert (
        json.loads(job_controller_env["REANA_VETTED_CONTAINER_IMAGES"]) == vetted_images
    )


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
@pytest.mark.parametrize(
    "shared_storage",
    [
        pytest.param({"backend": "cephfs"}, id="default-storage-class"),
        pytest.param(
            {"backend": "cephfs", "storage_class_name": None},
            id="null-storage-class",
        ),
    ],
)
def test_runtime_namespace_renders_static_cephfs_resources(tmp_path, shared_storage):
    """A separate runtime namespace should share the static CephFS volume."""
    rendered = _render_helm_chart(
        tmp_path,
        {
            "namespace_runtime": "runtime",
            "shared_storage": shared_storage,
        },
        namespace="infrastructure",
    )
    documents = _rendered_documents(rendered)

    runtime_namespace = next(
        document
        for document in documents
        if document["kind"] == "Namespace" and document["metadata"]["name"] == "runtime"
    )
    assert runtime_namespace["metadata"]["labels"] == {
        "app.kubernetes.io/component": "runtime",
        "app.kubernetes.io/instance": "reana",
        "app.kubernetes.io/managed-by": "Helm",
        "app.kubernetes.io/part-of": "reana",
    }

    infrastructure_volume = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolume"
        and document["metadata"]["name"].endswith("-shared-persistent-volume-storage")
    )
    runtime_volume = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolume"
        and document["metadata"]["name"].endswith("-runtime-storage")
    )
    infrastructure_csi = infrastructure_volume["spec"]["csi"]
    runtime_csi = runtime_volume["spec"]["csi"]
    assert infrastructure_csi["volumeHandle"] != runtime_csi["volumeHandle"]
    assert runtime_volume["spec"]["csi"]["volumeHandle"].endswith("-runtime")
    for attribute in ("shareID", "shareAccessID"):
        assert (
            infrastructure_csi["volumeAttributes"][attribute]
            == runtime_csi["volumeAttributes"][attribute]
        )

    runtime_claim = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolumeClaim"
        and document["metadata"].get("namespace") == "runtime"
    )
    assert runtime_claim["spec"]["storageClassName"] == ""
    assert runtime_claim["spec"]["volumeName"] == runtime_volume["metadata"]["name"]

    runtime_service_account = next(
        document
        for document in documents
        if document["kind"] == "ServiceAccount"
        and document["metadata"].get("namespace") == "runtime"
    )
    assert any(
        document["kind"] == "ConfigMap"
        and document["metadata"].get("namespace") == "runtime"
        and document["metadata"]["name"].endswith("-krb5-conf")
        for document in documents
    )
    runtime_worker_binding = next(
        document
        for document in documents
        if document["kind"] == "RoleBinding"
        and document["metadata"]["name"].endswith("-runtime-worker")
    )
    assert runtime_worker_binding["metadata"]["namespace"] == "runtime"
    assert {
        "kind": "ServiceAccount",
        "name": runtime_service_account["metadata"]["name"],
        "namespace": "runtime",
    } in runtime_worker_binding["subjects"]


def test_workflow_validator_environment_and_network_policy_rbac(tmp_path):
    """Validator settings and reconciliation permissions reach the controller."""
    values_file = tmp_path / "values.yaml"
    values_file.write_text(
        yaml.dump(
            {
                "components": {
                    "reana_workflow_validator": {
                        "environment": {
                            "REANA_LOG_LEVEL": "DEBUG",
                            "FEATURE_FLAG": True,
                        }
                    }
                },
                "secrets": {
                    "cache": {"user": "test", "password": "test"},
                    "database": {"user": "test", "password": "test"},
                    "message_broker": {"user": "test", "password": "test"},
                    "reana": {"REANA_SECRET_KEY": "test"},
                },
            }
        )
    )

    if not any((HELM_CHART / "charts").glob("*.tgz")):
        subprocess.run(
            ["helm", "dependency", "update", str(HELM_CHART)],
            capture_output=True,
            check=True,
        )

    rendered = subprocess.run(
        ["helm", "template", "reana", str(HELM_CHART), "-f", str(values_file)],
        capture_output=True,
        text=True,
        check=True,
    )

    controller_env = None
    network_policy_verbs = None
    for document in yaml.safe_load_all(rendered.stdout):
        if not document:
            continue
        if document.get("kind") == "Deployment" and document["metadata"][
            "name"
        ].endswith("-workflow-controller"):
            container = document["spec"]["template"]["spec"]["containers"][0]
            controller_env = {
                entry["name"]: entry["value"]
                for entry in container.get("env", [])
                if "value" in entry
            }
        if document.get("kind") == "ClusterRole":
            for rule in document.get("rules", []):
                if rule.get("resources") == ["networkpolicies"]:
                    network_policy_verbs = rule["verbs"]

    assert json.loads(controller_env["REANA_WORKFLOW_VALIDATOR_ENV_VARS"]) == {
        "REANA_LOG_LEVEL": "DEBUG",
        "FEATURE_FLAG": True,
    }
    assert network_policy_verbs == ["create", "get", "update"]


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
@pytest.mark.parametrize(
    "shared_storage,error_message",
    [
        pytest.param(
            {"backend": "cephfs", "storage_class_name": "rook-cephfs"},
            "namespace_runtime cannot be used together with "
            "shared_storage.storage_class_name",
            id="custom-storage-class",
        ),
        pytest.param(
            {"backend": "nfs"},
            "namespace_runtime is supported only with shared_storage.backend=cephfs",
            id="nfs",
        ),
    ],
)
def test_runtime_namespace_rejects_unsupported_pvc_storage(
    tmp_path, shared_storage, error_message
):
    """A runtime PVC must not silently target a different shared volume."""
    rendered = _render_helm_chart(
        tmp_path,
        {
            "namespace_runtime": "runtime",
            "shared_storage": shared_storage,
        },
        check=False,
    )

    assert rendered.returncode != 0
    assert error_message in rendered.stderr


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
def test_runtime_namespace_hostpath_does_not_create_pvc(tmp_path):
    """Hostpath storage should not require a namespace-scoped PVC."""
    rendered = _render_helm_chart(
        tmp_path,
        {"namespace_runtime": "runtime"},
    )
    documents = _rendered_documents(rendered)

    assert any(
        document["kind"] == "Namespace" and document["metadata"]["name"] == "runtime"
        for document in documents
    )
    assert not any(
        document["kind"] == "PersistentVolumeClaim"
        and document["metadata"].get("namespace") == "runtime"
        for document in documents
    )


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
@pytest.mark.parametrize(
    "namespace_runtime",
    [
        pytest.param(None, id="unset"),
        pytest.param("infrastructure", id="release-namespace"),
    ],
)
def test_runtime_namespace_disabled_does_not_create_resources(
    tmp_path, namespace_runtime
):
    """An unset or same-as-release value should not duplicate namespaced resources."""
    values = {}
    if namespace_runtime:
        values["namespace_runtime"] = namespace_runtime
    rendered = _render_helm_chart(
        tmp_path,
        values,
        namespace="infrastructure",
    )
    documents = _rendered_documents(rendered)

    assert not any(
        document["kind"] == "Namespace"
        and document["metadata"]["name"] == "infrastructure"
        for document in documents
    )
    # The runtime ServiceAccount is always created (PR976-17), but without a
    # dedicated namespace it must land alongside infrastructure, not in a
    # duplicated one.
    runtime_service_account = next(
        document
        for document in documents
        if document["kind"] == "ServiceAccount"
        and document["metadata"]["name"].endswith("-runtime")
    )
    assert runtime_service_account["metadata"]["namespace"] == "infrastructure"


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
def test_custom_storage_class_without_runtime_namespace(tmp_path):
    """Custom shared StorageClasses should retain their existing behaviour."""
    rendered = _render_helm_chart(
        tmp_path,
        {
            "shared_storage": {
                "backend": "cephfs",
                "storage_class_name": "rook-cephfs",
            }
        },
        namespace="infrastructure",
    )
    documents = _rendered_documents(rendered)

    infrastructure_claim = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolumeClaim"
        and document["metadata"].get("namespace") == "infrastructure"
        and document["metadata"]["name"].endswith("-shared-persistent-volume")
    )
    assert infrastructure_claim["spec"]["storageClassName"] == "rook-cephfs"


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
def test_null_storage_class_without_runtime_namespace(tmp_path):
    """A null StorageClass should retain static CephFS volume binding."""
    rendered = _render_helm_chart(
        tmp_path,
        {
            "shared_storage": {
                "backend": "cephfs",
                "storage_class_name": None,
            }
        },
        namespace="infrastructure",
    )
    documents = _rendered_documents(rendered)

    infrastructure_volume = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolume"
        and document["metadata"]["name"].endswith("-shared-persistent-volume-storage")
    )
    infrastructure_claim = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolumeClaim"
        and document["metadata"].get("namespace") == "infrastructure"
        and document["metadata"]["name"].endswith("-shared-persistent-volume")
    )
    assert infrastructure_claim["spec"]["storageClassName"] == ""
    assert (
        infrastructure_claim["spec"]["volumeName"]
        == infrastructure_volume["metadata"]["name"]
    )


@pytest.mark.skipif(
    not shutil.which("helm"),
    reason="helm must be installed",
)
def test_infrastructure_cephfs_binds_static_volume(tmp_path):
    """Infrastructure CephFS storage should bind its own static volume."""
    rendered = _render_helm_chart(
        tmp_path,
        {
            "infrastructure_storage": {
                "backend": "cephfs",
                "access_modes": "ReadWriteMany",
                "volume_size": 20,
                "cephfs": {
                    "os_secret_name": "os-trustee",
                    "os_secret_namespace": "kube-system",
                    "cephfs_os_share_id": "infrastructure-share",
                    "cephfs_os_share_access_id": "infrastructure-share-access",
                },
            }
        },
        namespace="infrastructure",
    )
    documents = _rendered_documents(rendered)

    volume = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolume"
        and document["metadata"]["name"].endswith(
            "-infrastructure-persistent-volume-storage"
        )
    )
    claim = next(
        document
        for document in documents
        if document["kind"] == "PersistentVolumeClaim"
        and document["metadata"]["name"].endswith("-infrastructure-persistent-volume")
    )
    assert claim["spec"]["storageClassName"] == ""
    assert claim["spec"]["volumeName"] == volume["metadata"]["name"]
    assert volume["spec"]["csi"]["volumeHandle"] == "infrastructure-share"

    # The legacy Manila provisioner StorageClass is unreachable on every
    # Kubernetes version the chart supports and must no longer be rendered.
    assert not any(
        document["kind"] == "StorageClass"
        and document["metadata"]["name"].endswith("-volume-storage-class")
        for document in documents
    )


def test_workflow_validator_reserved_environment_is_rejected():
    """The chart rejects attempts to replace the sandbox filesystem contract."""
    rendered = subprocess.run(
        [
            "helm",
            "template",
            "reana",
            str(HELM_CHART),
            "--set",
            "components.reana_workflow_validator.environment.PYTHONPATH=/tmp/inject",
        ],
        capture_output=True,
        text=True,
    )

    assert rendered.returncode != 0
    assert "PYTHONPATH is reserved by the validation sandbox" in rendered.stderr
