# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2020 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Locust file for a default REANA instance stress testing.

Usage:
.. code-block:: console
  $ pip install locust

.. code-block:: console
  $ locust -f tests/benchmark/locustfile.py --host=$REANA_SERVER_URL
  [2020-04-14 16:31:54,321] x.home/INFO/locust.main: Starting web monitor
  at http://*:8089
  [2020-04-14 16:31:54,321] x.home/INFO/locust.main: Starting Locust 0.14.5
  ...
  $ firefox http://127.0.0.1:8089

"""

import os

from locust import HttpLocust, TaskSet, between, task

TOKEN = os.environ.get("REANA_ACCESS_TOKEN")

dummy_spec = {
    "workflow": {
        "specification": {
            "steps": [
                {
                    "environment": "reanahub/reana-env-jupyter",
                    "commands": ["echo 'Hello REANA'"],
                }
            ]
        },
        "type": "serial",
    },
}

workflow_name = "myworkflow"


class WorkflowsTaskSet(TaskSet):
    """Get workflows."""

    def on_start(self):
        """On start."""
        self.client.verify = False

    def setup(self):
        """Create 10 workflows to query them."""
        for _ in range(10):
            self.client.post(
                "/api/workflows",
                params=(("workflow_name", workflow_name), ("access_token", TOKEN)),
                json=dummy_spec,
                verify=False,
            )

    @task
    def ping(self):
        """Ping reana instance."""
        self.client.get(f"/api/ping")

    @task
    def get_worflows(self):
        """Get workflows."""
        self.client.get(f"/api/workflows", params=(("access_token", TOKEN),))

    @task
    def get_worflow_logs(self):
        """Get workflow logs."""
        self.client.get(
            f"/api/workflows/{workflow_name}/logs", params=(("access_token", TOKEN),)
        )


class WebsiteUser(HttpLocust):
    """Locust instance. Represent the user that attacks the system."""

    task_set = WorkflowsTaskSet
    wait_time = between(5, 10)
