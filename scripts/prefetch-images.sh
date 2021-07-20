#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020, 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

for image in \
    maildev/maildev:1.1.0 \
    postgres:9.6.2 \
    redis:5.0.5 \
    jupyter/scipy-notebook \
    reanahub/reana-job-controller:0.8.0-alpha.3 \
    reanahub/reana-message-broker:0.8.0-alpha.1 \
    reanahub/reana-server:0.8.0-alpha.2 \
    reanahub/reana-ui:0.8.0-alpha.2 \
    reanahub/reana-workflow-controller:0.8.0-alpha.2 \
    reanahub/reana-workflow-engine-cwl:0.8.0-alpha.2 \
    reanahub/reana-workflow-engine-serial:0.8.0-alpha.2 \
    reanahub/reana-workflow-engine-yadage:0.8.0-alpha.2 \
    reanahub/reana-workflow-engine-snakemake:0.8.0-alpha.0; do
    docker pull $image
    kind load docker-image $image
done
