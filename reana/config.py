# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2023, 2024, 2025 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""``reana-dev`` CLI configuration."""

import re


REPO_LIST_DEMO_RUNNABLE = [
    "reana-demo-alice-lego-train-test-run",
    "reana-demo-alice-pt-analysis",
    "reana-demo-atlas-recast",
    "reana-demo-bsm-search",
    "reana-demo-cms-dimuon-mass-spectrum",
    "reana-demo-cms-h4l",
    "reana-demo-helloworld",
    "reana-demo-root6-roofit",
    "reana-demo-worldpopulation",
]
"""All git repositories containing REANA runnable demos."""

REPO_LIST_DEMO_ALL = REPO_LIST_DEMO_RUNNABLE + [
    "reana-demo-agc-cms-ttbar-coffea",
    "reana-demo-cdci-crab-pulsar-integral-verification",
    "reana-demo-cdci-integral-data-reduction",
    "reana-demo-cms-reco",
    "reana-demo-dask-coffea",
    "reana-demo-fcchh-fullsim",
    "reana-demo-lhcb-d2pimumu",
    "reana-demo-lhcb-mc-production",
]
"""All git repositories containing REANA demos."""


REPO_LIST_ALL = [
    "blog.reana.io",
    "docs.reana.io",
    "reana",
    "reana-auth-krb5",
    "reana-auth-rucio",
    "reana-auth-vomsproxy",
    "reana-client",
    "reana-client-go",
    "reana-commons",
    "reana-db",
    "reana-env-aliphysics",
    "reana-env-jupyter",
    "reana-env-root6",
    "reana-github-actions",
    "reana-job-controller",
    "pytest-reana",
    "reana-message-broker",
    "reana-server",
    "reana-ui",
    "reana-workflow-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
    "reana-workflow-engine-snakemake",
    "reana-workflow-validator",
    "reana-dask-kubernetes-operator",
    "www.reana.io",
] + REPO_LIST_DEMO_ALL
"""All REANA git repositories."""

REPO_LIST_CLIENT = [
    # shared utils
    "pytest-reana",
    "reana-commons",
    "reana-db",
    # client
    "reana-client",
    "reana-client-go",
]
"""List of git repositories related to command line clients."""

REPO_LIST_CLUSTER_INFRASTRUCTURE = [
    "reana-ui",
    "reana-message-broker",
    "reana-server",
    "reana-workflow-controller",
    "reana-dask-kubernetes-operator",
]
"""List of git repositories related to infrastructure cluster components."""

REPO_LIST_CLUSTER_RUNTIME_BATCH = [
    "reana-job-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
    "reana-workflow-engine-snakemake",
    "reana-workflow-validator",
]
"""List of git repositories related to batch runtime cluster components."""

REPO_LIST_SHARED = [
    "reana-db",
    "reana-commons",
]
"""List of shared modules among REANA components."""

REPO_LIST_CLUSTER = (
    [
        # shared utils
        "pytest-reana",
        # cluster helpers
        "reana-auth-krb5",
        "reana-auth-rucio",
        "reana-auth-vomsproxy",
    ]
    + REPO_LIST_SHARED
    + REPO_LIST_CLUSTER_INFRASTRUCTURE
    + REPO_LIST_CLUSTER_RUNTIME_BATCH
)
"""List of git repositories related to cluster components."""

REPO_LIST_PYTHON_REQUIREMENTS = [
    "reana-server",
    "reana-workflow-controller",
    "reana-job-controller",
    "reana-workflow-engine-cwl",
    "reana-workflow-engine-serial",
    "reana-workflow-engine-yadage",
    "reana-workflow-engine-snakemake",
    "reana-workflow-validator",
    "reana-dask-kubernetes-operator",
]
"""List of cluster components that have a Python requirements file."""

WORKFLOW_ENGINE_LIST_ALL = ["cwl", "serial", "yadage", "snakemake"]
"""List of supported workflow engines."""

COMPUTE_BACKEND_LIST_ALL = ["kubernetes", "htcondorcern", "slurmcern", "compute4punch"]
"""List of supported compute backends."""

CLUSTER_DEPLOYMENT_MODES = ["releasehelm", "releasepypi", "latest", "debug"]
"""List of supported modes to run a REANA cluster."""

COMPONENT_PODS = {
    "reana-db": "reana-db",
    "reana-message-broker": "reana-message-broker",
    "reana-server": "reana-server",
    "reana-workflow-controller": "reana-workflow-controller",
    "reana-ui": "reana-ui",
    "reana-dask-kubernetes-operator": "reana-dask-kubernetes-operator",
}
"""Component pods by repository name."""

EXAMPLE_NON_STANDARD_REANA_YAML_FILENAME = {
    "reana-demo-atlas-recast": {
        "yadage": {
            "htcondorcern": "reana-htcondorcern.yaml",
            "kubernetes": "reana.yaml",
        },
    },
    "reana-demo-bsm-search": {
        "yadage": {
            "kubernetes": "reana.yaml",
        }
    },
    "reana-demo-cms-h4l": {
        "snakemake": {
            "kubernetes": "reana.yaml",
        }
    },
}
"""List of non standard REANA demo's reana.yaml file names."""

EXAMPLE_OUTPUT_FILENAMES = {
    "reana-demo-helloworld": ("greetings.txt",),
    "reana-demo-bsm-search": ("prefit.pdf", "postfit.pdf"),
    "reana-demo-alice-lego-train-test-run": ("plot.pdf",),
    "reana-demo-alice-pt-analysis": ("plot_eta.pdf", "plot_pt.pdf"),
    "reana-demo-atlas-recast": ("pre.png", "limit.png", "limit_data.json"),
    "reana-demo-cms-dimuon-mass-spectrum": ("DoubleMu.root",),
    "reana-demo-cms-h4l": ("results/mass4l_combine_userlvl3.pdf",),
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
    "reana-demo-worldpopulation": (
        "Input Notebook",
        "Output Notebook",
    ),
    "reana-demo-atlas-recast": (
        "MC channel Number",
        "MIGRAD MINIMIZATION HAS CONVERGED",
    ),
    "reana-demo-cms-h4l": ("results/mass4l_combine_userlvl3.pdf has been created",),
    "reana-demo-alice-pt-analysis": (
        "pdf file plot_pt.pdf has been created",
        "pdf file plot_eta.pdf has been created",
    ),
    "reana-demo-alice-lego-train-test-run": ("pdf file plot.pdf has been created",),
    "reana-demo-bsm-search": ("postfit.pdf has been created",),
    "reana-demo-cms-dimuon-mass-spectrum": ("T---Report end!",),
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
    "reana-workflow-engine-snakemake",
    "reana-workflow-validator",
    "reana-dask-kubernetes-operator",
]
"""List of components which use the module REANA-Commons."""

COMPONENTS_USING_SHARED_MODULE_DB = [
    "reana-job-controller",
    "reana-server",
    "reana-workflow-controller",
    "reana-dask-kubernetes-operator",
]
"""List of components which use the module REANA-DB."""

DOCKER_PREFETCH_IMAGES = {
    "reana": [
        "docker.io/library/postgres:14.10",
        "docker.io/kozea/wdb:3.2.5",
        "docker.io/maildev/maildev:1.1.0",
        "docker.io/library/redis:5.0.5",
    ],
    "reana-demo-helloworld": [
        "docker.io/library/python:2.7-slim",
    ],
    "reana-demo-worldpopulation": [
        "docker.io/reanahub/reana-env-jupyter:2.0.0",
    ],
    "reana-demo-root6-roofit": [
        "docker.io/reanahub/reana-env-root6:6.18.04",
    ],
    "reana-demo-atlas-recast": [
        "docker.io/reanahub/reana-demo-atlas-recast-eventselection:1.0",
        "docker.io/reanahub/reana-demo-atlas-recast-statanalysis:1.0",
    ],
    "reana-demo-bsm-search": [
        "docker.io/reanahub/reana-demo-bsm-search:1.0.0",
        "docker.io/reanahub/reana-env-root6:6.18.04",
    ],
    "reana-demo-cms-h4l": [
        "docker.io/cmsopendata/cmssw_5_3_32",
    ],
    "reana-demo-cms-dimuon-mass-spectrum": [
        "docker.io/cmsopendata/cmssw_5_3_32",
    ],
    "reana-demo-alice-pt-analysis": [
        "docker.io/reanahub/reana-env-aliphysics:vAN-20180614-1",
    ],
    "reana-demo-alice-lego-train-test-run": [
        "docker.io/reanahub/reana-env-aliphysics:vAN-20180614-1",
    ],
    "reana-demo-dask-coffea": [
        "docker.io/coffeateam/coffea-dask-cc7:0.7.22-py3.10-g7f049",
    ],
}
"""Images to be prefetched depending on the REANA demo to be executed."""

TIMECHECK = 5
"""Checking frequency in seconds for results when running demo analyses in CI."""

TIMEOUT = 900
"""Maximum timeout to wait for results when running demo analyses in CI."""

DOCKER_VERSION_FILE = "Dockerfile"
"""Docker version file."""

HELM_VERSION_FILE = "Chart.yaml"
"""Helm package version file."""

OPENAPI_VERSION_FILE = "openapi.json"
"""OpenAPI version file."""

JAVASCRIPT_VERSION_FILE = "package.json"
"""JavaScript package version file."""

PYTHON_VERSION_FILE = "version.py"
"""Python package version file."""

PYTHON_REQUIREMENTS_FILE = "requirements.txt"
"""Python requirements file."""

GIT_DEFAULT_BASE_BRANCH = "master"
"""Default git base branch we shall be working against."""

GIT_SUPPORTED_MAINT_BRANCHES = ["maint-0.7"]
"""Git supported maintenance branches."""

GITHUB_REANAHUB_URL = "https://github.com/reanahub"
"""REANA Hub organisation GitHub URL."""

CODECOV_REANAHUB_URL = "https://codecov.io/gh/reanahub"
"""REANA Hub organisation Codecov URL."""

PYTHON_EXECUTABLE_NAME = "python3.12"
"""Python executable name with the same version as cluster components."""

PYTHON_DOCKER_IMAGE = "docker.io/library/python:3.12"
"""Python docker image with the same version as cluster components."""

RELEASE_COMMIT_REGEX = re.compile("^(release:|chore.*: release)")
"""Regex to find out if commit message refers to a new release."""
