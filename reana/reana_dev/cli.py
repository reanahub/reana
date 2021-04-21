# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018, 2019, 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Helper scripts for REANA developers. Run `reana-dev --help` for help."""

import click

from reana.reana_dev.client import client_commands_list
from reana.reana_dev.cluster import cluster_commands_list
from reana.reana_dev.docker import docker_commands_list
from reana.reana_dev.git import git_commands_list
from reana.reana_dev.helm import helm_commands_list
from reana.reana_dev.kind import kind_commands_list
from reana.reana_dev.kubectl import kubectl_commands_list
from reana.reana_dev.python import python_commands_list
from reana.reana_dev.release import release_commands_list
from reana.reana_dev.run import run_commands_list
from reana.reana_dev.wiki import wiki_commands_list


@click.group()
def reana_dev():  # noqa: D301
    """Run REANA development and integration commands.

    How to prepare your environment:

    .. code-block:: console

        \b
        $ # prepare directory that will hold sources
        $ mkdir -p ~/project/reana/src
        $ cd ~/project/reana/src
        $ # create new virtual environment
        $ virtualenv ~/.virtualenvs/reana
        $ source ~/.virtualenvs/reana/bin/activate
        $ # install reana-dev developer helper script
        $ pip install git+git://github.com/reanahub/reana.git#egg=reana
        $ # run ssh-agent locally to simplify GitHub interaction
        $ eval "$(ssh-agent -s)"
        $ ssh-add ~/.ssh/id_rsa

    How to fork and clone all REANA repositories:

    .. code-block:: console

        \b
        $ reana-dev git-fork -c ALL
        $ eval "$(reana-dev git-fork -c ALL)"
        $ reana-dev git-clone -c ALL -u tiborsimko

    How to run CI tests:

    .. code-block:: console

        \b
        $ # example (a): fast, CLI mode only, fast example
        $ reana-dev cluster-delete
        $ reana-dev run-ci -m /var/reana:/var/reana -c r-d-helloworld --exclude-components=r-ui,r-a-vomsproxy
                           --admin-email john.doe@example.org --admin-password mysecretpassword
        $ # example (b): slow, CLI and Web modes, all examples
        $ reana-dev cluster-delete
        $ reana-dev run-ci --admin-email john.doe@example.org --admin-password mysecretpassword

    How to create REANA cluster:

    .. code-block:: console

        \b
        $ # example (a): simple cluster creation
        $ reana-dev cluster-create
        $ # example (b): mount sharing /var/reana with host
        $ reana-dev cluster-create -m /var/reana:/var/reana
        $ # example (c): mount sharing /var/reana with host and /cvmfs for jobs
        $ reana-dev cluster-create -m /var/reana:/var/reana -j /cvmfs:/cvmfs
        $ # example (d): debug mode with code sharing as well
        $ reana-dev cluster-create -m /var/reana:/var/reana --mode debug

    How to setup a local multinode cluster:

    .. code-block:: console

        \b
        $ reana-dev cluster-create -m /var/reana:/var/reana --worker-nodes 3
        $ kubectl label node kind-worker reana.io/system=infrastructure
        $ kubectl label node kind-worker2 reana.io/system=runtimebatch
        $ kubectl label node kind-worker3 reana.io/system=runtimejobs
        $ reana-dev cluster-build --skip-load
        $ reana-dev kind-load-docker-image -c CLUSTER-INFRASTRUCTURE -n kind-worker
        $ reana-dev kind-load-docker-image -c CLUSTER-RUNTIMEBATCH -n kind-worker2
        $ reana-dev kind-load-docker-image -c reana-demo-worldpopulation -n kind-worker3

    How to set up your shell environment variables:

    .. code-block:: console

        \b
        $ eval $(reana-dev client-setup-environment)

    How to run full REANA example using a given workflow engine:

    .. code-block:: console

        \b
        $ reana-dev run-example -c reana-demo-root6-roofit -w serial

    How to run Python unit tests in independent virtual environments:

    .. code-block:: console

        \b
        $ reana-dev python-unit-tests -c r-server -c r-w-controller
        $ reana-dev python-unit-tests -c CLUSTER
        $ reana-dev python-unit-tests -c ALL

    How to test one component pull request:

    .. code-block:: console

        \b
        $ cd reana-workflow-controller
        $ reana-dev git-checkout-pr -b . 72 --fetch
        $ reana-dev docker-build -c .
        $ reana-dev kind-load-docker-image -c .
        $ reana-dev kubectl-delete-pod -c .

    How to test multiple component branches:

    .. code-block:: console

        \b
        $ reana-dev git-checkout-pr -b reana-server 72
        $ reana-dev git-checkout-pr -b reana-workflow-controller 98
        $ reana-dev git-status
        $ reana-dev docker-build
        $ reana-dev kind-load-docker-image -c reana-server
        $ reana-dev kubectl-delete-pod -c reana-server
        $ reana-dev kind-load-docker-image -c reana-workflow-controller
        $ reana-dev kubectl-delete-pod -c reana-workflow-controller

    How to test multiple component branches with commits to shared modules:

    .. code-block:: console

        \b
        $ reana-dev git-checkout-pr -b reana-commons 72
        $ reana-dev git-checkout-pr -b reana-db 73
        $ reana-dev git-checkout-pr -b reana-workflow-controller 98
        $ reana-dev git-checkout-pr -b reana-server 112
        $ reana-dev run-ci [using same old options]

    How to work on maintenance branches:

    .. code-block:: console

        \b
        $ reana-dev git-checkout -c CLIENT -c CLUSTER maint-0.7
        $ reana-dev git-status --base maint-0.7 -s

    How to release and push cluster component images:

    .. code-block:: console

        \b
        $ reana-dev git-clean
        $ reana-dev docker-build --no-cache
        $ # we should now run one more test with non-cached ``latest``
        $ # once it works, we can tag and push
        $ reana-dev docker-build -t 0.3.0.dev20180625
        $ reana-dev docker-push -t 0.3.0.dev20180625
        $ # we should now publish stable helm charts for tag via chartpress

    """
    pass


@click.command()
def version():
    """Show version."""
    from reana.version import __version__

    click.echo(__version__)


@click.command()
def help():
    """Display usage help tips and tricks."""
    click.echo(__doc__)


for cmd in (
    client_commands_list
    + cluster_commands_list
    + docker_commands_list
    + kind_commands_list
    + kubectl_commands_list
    + git_commands_list
    + python_commands_list
    + run_commands_list
    + release_commands_list
    + helm_commands_list
    + wiki_commands_list
):
    reana_dev.add_command(cmd)
