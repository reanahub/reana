# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Benchmark results are cleaned and plotted for workflows in any status."""

import importlib
import sys
from types import ModuleType

import pytest

pd = pytest.importorskip("pandas")
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

PLOTS = [
    "execution_progress",
    "execution_status",
    "histogram_total_time",
    "histogram_runtime",
    "histogram_pending_time",
]

COLLECTED_RESULTS = """\
name,created,started,ended,status,asked_to_start_date,collected_date
bench-1,2026-01-01T08:00:00,2026-01-01T08:00:20,2026-01-01T08:01:00,finished,2026-01-01T08:00:10,2026-01-01T08:05:00
bench-2,2026-01-01T08:00:01,2026-01-01T08:00:25,2026-01-01T08:01:30,finished,2026-01-01T08:00:11,2026-01-01T08:05:00
bench-3,2026-01-01T08:00:02,2026-01-01T08:00:30,2026-01-01T08:00:50,failed,2026-01-01T08:00:12,2026-01-01T08:05:00
bench-4,2026-01-01T08:00:03,,,failed,2026-01-01T08:00:13,2026-01-01T08:05:00
bench-5,2026-01-01T08:00:04,2026-01-01T08:00:40,,running,2026-01-01T08:00:14,2026-01-01T08:05:00
bench-6,2026-01-01T08:00:05,2026-01-01T08:00:45,,stopped,2026-01-01T08:00:15,2026-01-01T08:05:00
bench-7,2026-01-01T08:00:06,,,pending,2026-01-01T08:00:16,2026-01-01T08:05:00
bench-8,2026-01-01T08:00:07,,,queued,2026-01-01T08:00:17,2026-01-01T08:05:00
bench-9,2026-01-01T08:00:08,,,created,,2026-01-01T08:05:00
"""


@pytest.fixture
def benchmark(tmp_path, monkeypatch):
    """Import the benchmark modules against a fake of the REANA client."""
    fakes = {
        "reana_client": {},
        "reana_client.api": {},
        "reana_client.api.client": {"start_workflow": None},
        "reana_client.auth": {},
        "reana_client.auth.oidc": {},
    }
    for name, attributes in fakes.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        parent, _, child = name.rpartition(".")
        if parent:
            setattr(sys.modules[parent], child, module)
    modules = [
        f"reana.reana_benchmark.{name}"
        for name in ("utils", "start", "collect", "analyze")
    ]
    for name in modules:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.chdir(tmp_path)

    yield {name.rpartition(".")[2]: importlib.import_module(name) for name in modules}
    for name in modules:
        sys.modules.pop(name, None)


def _saved_plots(tmp_path):
    return sorted(path.name for path in tmp_path.glob("*.png"))


def test_analyze_saves_all_plots_for_workflows_in_any_status(benchmark, tmp_path):
    """Every plot is saved when the runs are in a mix of statuses."""
    (tmp_path / "bench_collected_results.csv").write_text(COLLECTED_RESULTS)

    benchmark["analyze"].analyze("bench", (1, 9), {"title": "bench"})

    assert _saved_plots(tmp_path) == sorted(f"bench_{plot}_1_9.png" for plot in PLOTS)


def test_analyze_saves_all_plots_without_finished_workflows(benchmark, tmp_path):
    """Histograms of finished workflows are still saved when there are none."""
    (tmp_path / "bench_collected_results.csv").write_text(COLLECTED_RESULTS)

    benchmark["analyze"].analyze("bench", (7, 9), {"title": "bench"})

    assert _saved_plots(tmp_path) == sorted(f"bench_{plot}_7_9.png" for plot in PLOTS)


def test_histograms_include_only_finished_workflows(benchmark, tmp_path):
    """Runtime and total time are taken from the finished workflows."""
    analyze = benchmark["analyze"]
    (tmp_path / "bench_collected_results.csv").write_text(COLLECTED_RESULTS)
    df = analyze._derive_metrics(pd.read_csv(tmp_path / "bench_collected_results.csv"))

    _, runtime = analyze._build_runtime_histogram(df, {"title": "bench"})
    _, total_time = analyze._build_total_time_histogram(df, {"title": "bench"})

    assert "fastest: 40, median: 52, mean: 52, slowest: 65" in (
        runtime.axes[0].get_title()
    )
    assert "fastest: 50, median: 64, mean: 64, slowest: 79" in (
        total_time.axes[0].get_title()
    )


def test_collect_cleans_missing_dates_in_any_status(benchmark):
    """Dates reported as "-" by the client are treated as missing."""
    df = pd.DataFrame(
        {
            "name": ["bench-1", "bench-2", "bench-3"],
            "status": ["finished", "failed", "stopped"],
            "started": ["2026-01-01T08:00:20", "-", "2026-01-01T08:00:45"],
            "ended": ["2026-01-01T08:01:00", "-", "-"],
            "asked_to_start_date": ["2026-01-01T08:00:10"] * 3,
        }
    )

    cleaned = benchmark["collect"]._clean_results(df)

    assert cleaned["started"].isna().tolist() == [False, True, False]
    assert cleaned["ended"].isna().tolist() == [False, True, True]
