#!/bin/bash
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

for image in \
        jupyter/scipy-notebook:notebook-6.4.5 \
        maildev/maildev:1.1.0 \
        postgres:12.8 \
        redis:5.0.5 \
        reanahub/reana-job-controller:0.8.1 \
        reanahub/reana-message-broker:0.8.0 \
        reanahub/reana-server:0.8.3 \
        reanahub/reana-ui:0.8.2 \
        reanahub/reana-workflow-controller:0.8.1 \
        reanahub/reana-workflow-engine-cwl:0.8.1 \
        reanahub/reana-workflow-engine-serial:0.8.1 \
        reanahub/reana-workflow-engine-snakemake:0.8.1 \
        reanahub/reana-workflow-engine-yadage:0.8.2 \
    ; do
        docker pull $image
        kind load docker-image $image
done
