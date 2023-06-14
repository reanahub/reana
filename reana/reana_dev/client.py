# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2022, 2023 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s command line client commands."""

import base64
import json
import logging
import subprocess
import traceback

import click

from reana.config import REPO_LIST_CLIENT
from reana.reana_dev.utils import run_command


@click.group()
def client_commands():
    """Client commands group."""


@client_commands.command(name="client-install")
def client_install():  # noqa: D301
    """Install latest REANA client and its dependencies."""
    for component in REPO_LIST_CLIENT:
        for cmd in [
            "if [ -e setup.py ]; then pip install . --upgrade; fi",
        ]:
            run_command(cmd, component)
    run_command("pip check", "reana")


@client_commands.command(name="client-uninstall")
def client_uninstall():  # noqa: D301
    """Uninstall REANA client and its dependencies."""
    cmd = "pip uninstall -y " + " ".join(REPO_LIST_CLIENT)
    run_command(cmd, "reana")
    run_command("pip check", "reana")


@client_commands.command(name="client-setup-environment")
@click.option("--server-hostname", help="Set customized REANA Server hostname.")
@click.option("--insecure-url", is_flag=True, help="REANA Server URL with HTTP.")
@click.option(
    "--namespace", "-n", default="default", help="Kubernetes namespace [default]"
)
@click.option("--instance-name", default="reana", help="REANA instance name")
def client_setup_environment(
    server_hostname, insecure_url, namespace, instance_name
):  # noqa: D301
    """Display commands to set up shell environment for local cluster.

    Display commands how to set up REANA_SERVER_URL and REANA_ACCESS_TOKEN
    suitable for current local REANA cluster deployment. The output should be
    passed to eval.
    """
    try:
        export_lines = []
        component_export_line = "export {env_var_name}={env_var_value}"
        export_lines.append(
            component_export_line.format(
                env_var_name="REANA_SERVER_URL",
                env_var_value=server_hostname or "https://localhost:30443",
            )
        )
        get_access_token_cmd = f"kubectl get secret -n {namespace} -o json {instance_name}-admin-access-token"
        secret_json = json.loads(
            subprocess.check_output(get_access_token_cmd, shell=True).decode()
        )
        admin_access_token_b64 = secret_json["data"]["ADMIN_ACCESS_TOKEN"]
        admin_access_token = base64.b64decode(admin_access_token_b64).decode()
        export_lines.append(
            component_export_line.format(
                env_var_name="REANA_ACCESS_TOKEN", env_var_value=admin_access_token
            )
        )

        click.echo("\n".join(export_lines))
    except Exception as e:
        logging.debug(traceback.format_exc())
        logging.debug(str(e))
        click.echo(
            click.style(
                "Environment variables could not be generated: \n{}".format(str(e)),
                fg="red",
            ),
            err=True,
        )


client_commands_list = list(client_commands.commands.values())
