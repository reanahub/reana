# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020, 2021, 2022, 2024 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""`reana-dev`'s wiki commands."""

import click

from reana.config import (
    CODECOV_REANAHUB_URL,
    GIT_SUPPORTED_MAINT_BRANCHES,
    GITHUB_REANAHUB_URL,
    REPO_LIST_DEMO_ALL,
)


@click.group()
def wiki_commands():
    """Wiki commands group."""


@wiki_commands.command(name="wiki-create-build-status-page")
def create_build_status_page():
    """Generate Markdown for the Build Status wiki page."""
    sections = {
        "researchers": {
            "title": "For researchers",
            "description": "Find out how you can use REANA to describe, run, preserve and reuse your analyses.",
            "packages": {
                "reana-client": {},
                "blog.reana.io": {"coverage": False, "docs": False},
                "docs.reana.io": {"coverage": False, "docs": False},
                "www.reana.io": {"coverage": False, "docs": False},
            },
        },
        "administrators": {
            "title": "For administrators",
            "description": "Install and manage the REANA reusable analysis platform on your own compute cloud.",
            "packages": {
                "reana-commons": {},
                "reana-db": {},
                "reana-job-controller": {},
                "reana-message-broker": {},
                "reana-server": {},
                "reana-ui": {},
                "reana-workflow-controller": {},
                "reana-workflow-engine-cwl": {},
                "reana-workflow-engine-serial": {},
                "reana-workflow-engine-yadage": {},
                "reana-workflow-engine-snakemake": {},
                "reana-workflow-validator": {},
            },
        },
        "developers": {
            "title": "For developers",
            "description": "Understand REANA source code, adapt it to your needs, contribute changes back.",
            "packages": {"reana": {}, "pytest-reana": {}},
        },
        "environments": {
            "simple": True,
            "title": "Environments",
            "description": "Selected containerised environments.",
            "packages": {
                "reana-env-aliphysics": {},
                "reana-env-jupyter": {},
                "reana-env-root6": {},
            },
        },
        "authentication": {
            "simple": True,
            "title": "Authentication",
            "description": "Selected authentication environments.",
            "packages": {
                "reana-auth-krb5": {},
                "reana-auth-rucio": {},
                "reana-auth-vomsproxy": {},
            },
        },
        "examples": {
            "simple": True,
            "title": "Examples",
            "description": "Selected reusable analysis examples.",
            "packages": {demo: {} for demo in sorted(REPO_LIST_DEMO_ALL)},
        },
    }

    def _print_section(data):
        click.echo(f"### {data['title']}\n")
        click.echo(f"{data['description']}\n")
        _print_table(data["packages"], simple=data.get("simple"))
        click.echo()

    def _print_header(hs):
        header = separator = "|"
        for h in hs:
            header += f" {h} |"
            separator += f" {'-' * len(h)} |"
        click.echo(header)
        click.echo(separator)

    def _print_table(components, simple=False):
        if simple:
            headers = ["Package", "Build", "Version"]
        else:
            headers = [
                "Package",
                "`master`",
                "Docs",
                "Coverage",
                "Version",
            ]
            headers[1:1] = [f"`{branch}`" for branch in GIT_SUPPORTED_MAINT_BRANCHES]
        _print_header(headers)
        for c, options in components.items():
            table_row = f"| [{c}]({GITHUB_REANAHUB_URL}/{c}) "
            if not simple:
                for branch in GIT_SUPPORTED_MAINT_BRANCHES:
                    table_row += f"| [![{branch}]({GITHUB_REANAHUB_URL}/{c}/workflows/CI/badge.svg?branch={branch})]({GITHUB_REANAHUB_URL}/{c}/actions?query=branch:{branch}) "

            table_row += f"| [![master]({GITHUB_REANAHUB_URL}/{c}/workflows/CI/badge.svg?branch=master)]({GITHUB_REANAHUB_URL}/{c}/actions?query=branch:master) "

            if not simple:
                table_row += (
                    f"| [![Docs](https://readthedocs.org/projects/{c}/badge/?version=latest)](https://{c}.readthedocs.io/en/latest/?badge=latest) "
                    if options.get("docs", True)
                    else "| N/A "
                ) + (
                    f"| [![Coverage]({CODECOV_REANAHUB_URL}/{c}/branch/master/graph/badge.svg)]({CODECOV_REANAHUB_URL}/{c}) "
                    if options.get("coverage", True)
                    else "| N/A "
                )

            table_row += f"| [![Tag](https://img.shields.io/github/tag/reanahub/{c}.svg)]({GITHUB_REANAHUB_URL}/{c}/releases) |"

            click.echo(table_row)
        click.echo()

    click.echo("# REANA build status\n")
    for section, data in sections.items():
        _print_section(data)


wiki_commands_list = list(wiki_commands.commands.values())
