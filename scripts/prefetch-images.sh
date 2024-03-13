#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

for image in \
    docker.io/jupyter/scipy-notebook:notebook-6.4.5 \
    docker.io/maildev/maildev:1.1.0 \
    docker.io/library/postgres:12.13 \
    docker.io/library/redis:5.0.5 \
    docker.io/reanahub/reana-job-controller:0.9.3 \
    docker.io/reanahub/reana-message-broker:0.9.3 \
    docker.io/reanahub/reana-server:0.9.3 \
    docker.io/reanahub/reana-ui:0.9.4 \
    docker.io/reanahub/reana-workflow-controller:0.9.3 \
    docker.io/reanahub/reana-workflow-engine-cwl:0.9.3 \
    docker.io/reanahub/reana-workflow-engine-serial:0.9.3 \
    docker.io/reanahub/reana-workflow-engine-snakemake:0.9.3 \
    docker.io/reanahub/reana-workflow-engine-yadage:0.9.4 \
    ; do
        docker pull $image
        kind load docker-image $image
done
