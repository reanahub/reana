# This file is part of REANA.
# Copyright (C) 2021 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Responsible for monitoring K8s cluster, DB connections."""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Generator
from collections import defaultdict
import subprocess
from abc import abstractmethod, ABC

from reana.reana_benchmark.utils import get_utc_now_timestamp, logger


class BaseMetric(ABC):
    """Base class for other metrics."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the metric."""
        raise NotImplementedError

    @abstractmethod
    def _collect(self, parameters: Dict) -> Any:
        raise NotImplementedError

    def collect(self, parameters: Dict) -> Dict[str, Any]:  # noqa: D102
        result = self._collect(parameters)
        return {
            self.name: result,
        }


class WorkflowDBStatusesMetric(BaseMetric):
    """Count number of workflows statuses directly from DB."""

    name = "workflow_db_statuses"

    def _collect(self, parameters: Dict) -> Any:
        workflow_prefix = parameters.get("workflow")

        if not workflow_prefix:
            logger.warning(
                f"{self.name} metrics cannot find workflow parameter. Metric will not be collected."
            )
            return {}

        cmd = [
            "kubectl",
            "exec",
            "deployment/reana-db",
            "--",
            "psql",
            "-U",
            "reana",
            "-c",
            f"SELECT status,COUNT(*) FROM __reana.workflow WHERE name LIKE '{workflow_prefix}-%' GROUP BY status;",
        ]
        output = subprocess.check_output(cmd).decode("ascii")
        result = {}

        rows = output.splitlines()[2:-2]

        for row in rows:
            status, count = row.split("|")[0].strip(), int(row.split("|")[1].strip())
            result[status] = count

        return result


class NumberOfDBConnectionsMetric(BaseMetric):
    """Count number of server processes in REANA DB."""

    name = "db_connections_number"

    def _collect(self, parameters: Dict) -> Any:
        cmd = [
            "kubectl",
            "exec",
            "deployment/reana-db",
            "--",
            "psql",
            "-U",
            "reana",
            "-c",
            "SELECT COUNT(*) FROM pg_stat_activity;",
        ]
        output = subprocess.check_output(cmd).decode("ascii")
        result = int(output.splitlines()[2].strip())
        return result


class WorkflowPodsMetric(BaseMetric):
    """Count number of job and batch jobs in different phases."""

    name = "workflows_pods_status"

    @staticmethod
    def _filter(pods: List[Dict], name_contains: str) -> Generator[Dict, None, None]:
        for pod in pods:
            name = pod.get("metadata", {}).get("name", "")
            if name_contains in name:
                yield pod

    @staticmethod
    def _count(pods: List[Dict], name_contains: str) -> Dict[str, int]:
        statistics = defaultdict(lambda: 0)
        for pod in WorkflowPodsMetric._filter(pods, name_contains):
            phase = pod.get("status", {}).get("phase")
            statistics[phase] += 1
        return dict(statistics)

    def _collect(self, parameters: Dict) -> Any:
        kubectl_cmd = ("kubectl", "get", "pods", "-o", "json")
        output = subprocess.check_output(kubectl_cmd)
        pods = json.loads(output).get("items", [])

        result = {
            "batch_pods": self._count(pods, "run-batch"),
            "job_pods": self._count(pods, "run-job"),
        }

        return result


METRICS = [
    NumberOfDBConnectionsMetric(),
    WorkflowPodsMetric(),
    WorkflowDBStatusesMetric(),
]


def _build_monitored_results_path(workflow: str) -> Path:
    return Path(f"{workflow}_monitored_results.json")


def _save_metrics(workflow: str, results: Dict) -> None:
    with open(_build_monitored_results_path(workflow), "w") as f:
        json.dump(results, f)


def _collect_metrics(parameters: Dict) -> Dict[str, Any]:
    collected_metrics = {}
    for metric in METRICS:
        try:
            result = metric.collect(parameters)
            collected_metrics = dict(collected_metrics, **result)
        except Exception as error:
            logger.error(
                f"Error during collection of {metric.name} metric. Details: {error}"
            )
    return collected_metrics


def _print_metrics() -> None:
    logger.info("Following metrics will be collected:")
    for m in METRICS:
        logger.info(f"- {m.name}")


def monitor(workflow: str, sleep: int) -> None:
    """Start periodically collect defined metrics and save them to JSON file.

    This function is blocking.
    """
    _print_metrics()
    logger.info("Starting monitoring...")

    all_metrics = {}
    metrics_parameters = {
        "workflow": workflow,
    }

    try:
        while True:
            # if metrics will take, for example, couple of seconds to collect monitored_date will be less accurate
            monitored_date = get_utc_now_timestamp()
            collected_metrics = _collect_metrics(metrics_parameters)
            all_metrics[monitored_date] = collected_metrics
            _save_metrics(workflow, all_metrics)

            time.sleep(sleep)
    except KeyboardInterrupt:
        logger.info("Stopping monitoring...")
    finally:
        _save_metrics(workflow, all_metrics)
