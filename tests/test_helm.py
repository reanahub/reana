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
