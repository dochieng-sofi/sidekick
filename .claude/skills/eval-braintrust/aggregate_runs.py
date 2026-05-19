#!/usr/bin/env python3
"""
Aggregate baseline JSON files referenced by a batch manifest.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from compare_runs import GROUP_NAMES, GROUP_ORDER, SCENARIO_LABELS, SCENARIO_ORDER


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("records", []))


def compute_run_stats(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, int | float | None]]]:
    stats: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for record in records:
        group_id = record.get("group_id", "")
        scenario = record.get("scenario_type", "")
        if not group_id or not scenario:
            continue
        stats[group_id][scenario][1] += 1
        if record.get("group_pass") is True:
            stats[group_id][scenario][0] += 1

    output: dict[str, dict[str, dict[str, int | float | None]]] = {}
    for group_id, scenarios in stats.items():
        output[group_id] = {}
        for scenario, (passed, total) in scenarios.items():
            accuracy = (passed / total) if total else None
            output[group_id][scenario] = {
                "passed": passed,
                "total": total,
                "accuracy": accuracy,
            }
    return output


def summarize_runs(run_stats: list[dict[str, dict[str, dict[str, int | float | None]]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for group_id in GROUP_ORDER:
        group_summary: dict[str, Any] = {}
        for scenario in SCENARIO_ORDER:
            accuracies: list[float] = []
            pooled_passed = 0
            pooled_total = 0
            contributing_runs = 0
            for stats in run_stats:
                cell = stats.get(group_id, {}).get(scenario)
                if not cell:
                    continue
                passed = int(cell["passed"])
                total = int(cell["total"])
                accuracy = cell["accuracy"]
                pooled_passed += passed
                pooled_total += total
                contributing_runs += 1
                if isinstance(accuracy, (int, float)):
                    accuracies.append(float(accuracy))
            if not pooled_total:
                continue
            group_summary[scenario] = {
                "label": SCENARIO_LABELS[scenario],
                "run_count": contributing_runs,
                "pooled_passed": pooled_passed,
                "pooled_total": pooled_total,
                "pooled_accuracy": pooled_passed / pooled_total,
                "mean_accuracy": statistics.mean(accuracies) if accuracies else None,
                "min_accuracy": min(accuracies) if accuracies else None,
                "max_accuracy": max(accuracies) if accuracies else None,
                "stdev_accuracy": statistics.pstdev(accuracies) if len(accuracies) > 1 else 0.0,
            }
        if group_summary:
            summary[group_id] = {
                "category": GROUP_NAMES.get(group_id, group_id),
                "scenarios": group_summary,
            }
    return summary


def aggregate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    run_entries = [
        run
        for run in manifest.get("runs", [])
        if run.get("status") == "success" and run.get("baseline_path")
    ]
    runs: list[dict[str, Any]] = []
    run_stats: list[dict[str, dict[str, dict[str, int | float | None]]]] = []
    for run in run_entries:
        baseline_path = Path(str(run["baseline_path"]))
        records = load_records(baseline_path)
        stats = compute_run_stats(records)
        runs.append(
            {
                "index": run.get("index"),
                "baseline_path": str(baseline_path),
                "experiment_name": run.get("resolved_experiment_name") or run.get("experiment_name"),
                "stats": stats,
            }
        )
        run_stats.append(stats)

    return {
        "schema_version": 1,
        "batch_id": manifest.get("batch_id"),
        "phase": manifest.get("phase"),
        "provider": manifest.get("provider"),
        "tag": manifest.get("tag"),
        "runs_requested": manifest.get("runs_requested"),
        "runs_included": len(runs),
        "runs": runs,
        "summary": summarize_runs(run_stats),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate eval baselines from a batch manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(Path(args.manifest).expanduser())
    aggregate = aggregate_manifest(manifest)
    output_path = Path(args.output).expanduser()
    output_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    print(f"Saved aggregate summary for {aggregate['runs_included']} run(s) to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
