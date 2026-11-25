#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023, 2024, 2025, 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Are we using Kind for local developments? (kind, colima/k3s)
if [ -z "$1" ]; then
    kubernetes=kind
else
    kubernetes="$1"
fi

for image in \
    docker.io/maildev/maildev:2.2.1 \
    docker.io/library/postgres:18.7 \
    docker.io/library/redis:8.10.3 \
    docker.io/library/traefik:v3.7.19 \
    docker.io/reanahub/reana-job-controller:0.95.0-alpha.7 \
    docker.io/reanahub/reana-message-broker:0.95.0-alpha.4 \
    docker.io/reanahub/reana-server:0.95.0-alpha.8 \
    docker.io/reanahub/reana-ui:0.95.0-alpha.6 \
    docker.io/reanahub/reana-workflow-controller:0.95.0-alpha.9 \
    docker.io/reanahub/reana-workflow-engine-cwl:0.95.0-alpha.7 \
    docker.io/reanahub/reana-workflow-engine-serial:0.95.0-alpha.7 \
    docker.io/reanahub/reana-workflow-engine-snakemake:0.95.0-alpha.7 \
    docker.io/reanahub/reana-workflow-engine-yadage:0.95.0-alpha.7 \
    docker.io/reanahub/reana-workflow-validator:0.95.0-alpha.2 \
    docker.io/reanahub/reana-dask-kubernetes-operator:0.95.0-alpha.5 \
    ghcr.io/cloudnative-pg/pgbouncer:1.26.1 \
    quay.io/jupyter/scipy-notebook:notebook-7.6.3 \
    quay.io/keycloak/keycloak:26.8.2-3; do
    docker pull $image
    if [ "$kubernetes" == "kind" ]; then
        kind load docker-image $image
    fi
done
