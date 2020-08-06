# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""``reana-dev`` CLI configuration."""

REPO_LIST_DEMO = [
    "reana-demo-helloworld",
    "reana-demo-root6-roofit",
    "reana-demo-worldpopulation",
    "reana-demo-atlas-recast",
]
"""All git repositories containing REANA demos."""

REPO_LIST_ALL = [
    "docs.reana.io",
    "reana",
    "reana-auth-krb5",
    "reana-auth-vomsproxy",
    "reana-client",
    "reana-commons",
    "reana-db",
    "reana-demo-alice-lego-train-test-run",
    "reana-demo-alice-pt-analysis",
    "reana-demo-bsm-search",
    "reana-demo-cdci-crab-pulsar-integral-verification",
    "reana-demo-cdci-integral-data-reduction",
    "reana-demo-cms-dimuon-mass-spectrum",
    "reana-demo-cms-h4l",
    "reana-demo-cms-reco",
    "reana-demo-lhcb-d2pimumu",
    "reana-env-aliphysics",
    "reana-env-jupyter",
    "reana-env-root6",
    "reana-job-controller",
    "pytest-reana",
    "reana-message-broker",
    "reana-server",
    "reana-ui",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
    "reana-workflow-monitor",
    "www.reana.io",
] + REPO_LIST_DEMO
"""All REANA git repositories."""

REPO_LIST_CLIENT = [
    # shared utils
    "pytest-reana",
    "reana-commons",
    "reana-db",
    # client
    "reana-client",
]
"""List of git repositories related to command line clients."""

REPO_LIST_CLUSTER = [
    # shared utils
    "pytest-reana",
    "reana-commons",
    "reana-db",
    # cluster helpers
    "reana-auth-krb5",
    "reana-auth-vomsproxy",
    # cluster components
    "reana-ui",
    "reana-job-controller",
    "reana-message-broker",
    "reana-server",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
]
"""List of git repositories related to cluster components."""

REPO_LIST_SHARED = [
    "reana-db",
    "reana-commons",
]
"""List of shared modules among REANA components."""

WORKFLOW_ENGINE_LIST_ALL = ["cwl", "serial", "yadage"]
"""List of supported workflow engines."""

COMPONENT_PODS = {
    "reana-db": "reana-db",
    "reana-message-broker": "reana-message-broker",
    "reana-server": "reana-server",
    "reana-workflow-controller": "reana-workflow-controller",
    "reana-ui": "reana-ui",
}
"""Component pods by repository name."""

EXAMPLE_OUTPUT_FILENAMES = {
    "reana-demo-helloworld": ("greetings.txt",),
    "reana-demo-bsm-search": ("prefit.pdf", "postfit.pdf"),
    "reana-demo-alice-lego-train-test-run": ("plot.pdf",),
    "reana-demo-alice-pt-analysis": ("plot_eta.pdf", "plot_pt.pdf"),
    "reana-demo-atlas-recast": ("pre.png", "limit.png", "limit_data.json"),
    "reana-demo-cms-dimuon-mass-spectrum": ("DoubleMu.root",),
    "*": ("plot.png",),
}
"""Expected success produced files by REANA demos."""

EXAMPLE_LOG_MESSAGES = {
    "reana-demo-helloworld": ("Parameters: inputfile=",),
    "reana-demo-root6-roofit": (
        "gendata.C",
        "RooChebychev::bkg",
        "fitdata.C",
        "MIGRAD MINIMIZATION HAS CONVERGED",
    ),
    "reana-demo-worldpopulation": ("Input Notebook", "Output Notebook",),
    "reana-demo-atlas-recast": (
        "MC channel Number",
        "MIGRAD MINIMIZATION HAS CONVERGED",
    ),
    "*": ("job:",),
}
"""Expected success log messages from REANA demos."""

COMPONENTS_USING_SHARED_MODULE_COMMONS = [
    "reana-job-controller",
    "reana-server",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
]
"""List of components which use the module REANA-Commons."""

COMPONENTS_USING_SHARED_MODULE_DB = [
    "reana-job-controller",
    "reana-server",
    "reana-workflow-controller",
]
"""List of components which use the module REANA-DB."""

DOCKER_PREFETCH_IMAGES = {
    "reana": [
        "postgres:9.6.2",
        "kozea/wdb:3.2.5",
        "maildev/maildev:1.1.0",
        "redis:5.0.5",
    ],
    "reana-demo-helloworld": ["python:2.7-slim",],
    "reana-demo-worldpopulation": ["reanahub/reana-env-jupyter:1.0.0",],
    "reana-demo-root6-roofit": ["reanahub/reana-env-root6:6.18.04",],
    "reana-demo-atlas-recast": [
        "reanahub/reana-demo-atlas-recast-eventselection:1.0",
        "reanahub/reana-demo-atlas-recast-statanalysis:1.0",
    ],
}
"""Images to be prefetched depending on the REANA demo to be executed."""

TIMECHECK = 5
"""Checking frequency in seconds for results when running demo analyses in CI."""

TIMEOUT = 300
"""Maximum timeout to wait for results when running demo analyses in CI."""

HELM_VERSION_FILE = "Chart.yaml"
"""Helm package version file."""

OPENAPI_VERSION_FILE = "openapi.json"
"""OpenAPI version file."""

JAVASCRIPT_VERSION_FILE = "package.json"
"""JavaScript package version file."""

PYTHON_VERSION_FILE = "version.py"
"""Python package version file."""
