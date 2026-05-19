#!/usr/bin/env python3
"""
Save guardrail eval records to a persistent baseline JSON file.

Usage:
  python3 save_baseline.py \
    --events /tmp/bt_events.json \
    --exp-id <UUID> \
    --exp-name test-cases-super-merge-train-ba2f49c6 \
    --output ~/Desktop/baseline_ba2f49c6.json

The output file is the input format for compare_runs.py.
"""
import argparse
import json
import os
from datetime import datetime

GROUP_MAP = {
    "regulated-advice":      "Regulated Advice",
    "content-guardrails":    "Content Guardrails",
    "crisis-safety":         "Crisis Safety",
    "pii-protection":        "PII Protection",
    "abuse-misuse":          "Abuse & Misuse",
    "jailbreak-injection":   "Jailbreak - Injection",
    "anti-money-laundering": "Anti-Money Laundering",
}


def get_groups(meta):
    if not isinstance(meta, dict):
        return []
    if "groups" in meta:
        return meta["groups"]
    if "Assertions" in meta:
        return meta["Assertions"].get("groups", [])
    return []


def extract(events: list) -> list:
    task_map = {}
    for e in events:
        if (e.get("span_attributes") or {}).get("name") == "task":
            root = e.get("root_span_id", "")
            inp = e.get("input") or {}
            test_id = inp.get("test_id", "")
            scenario_type = inp.get("scenario_type", "")
            if not scenario_type:
                for prefix in ("block", "pass", "escalate"):
                    if test_id.startswith(prefix + "-"):
                        scenario_type = prefix
                        break
            task_map[root] = {
                "test_id":       test_id,
                "scenario_type": scenario_type,
                "mock_user":     inp.get("mock_user", ""),
            }

    records = []
    for span in events:
        name = (span.get("span_attributes") or {}).get("name", "")
        if "assertion_scorer" not in name:
            continue
        root = span.get("root_span_id", "")
        task = task_map.get(root, {})
        for grp in get_groups(span.get("metadata") or {}):
            if not isinstance(grp, dict):
                continue
            gid = grp.get("group_id", "")
            if gid not in GROUP_MAP:
                continue
            crs = [cr for cr in (grp.get("criteria_results") or []) if isinstance(cr, dict)]
            evaluated = [cr for cr in crs if cr.get("pass") is not None]
            rules_passed = sum(1 for cr in evaluated if cr.get("pass") is True)
            rules_total = len(evaluated)
            records.append({
                "group_id":      gid,
                "category":      GROUP_MAP[gid],
                "test_id":       task.get("test_id", ""),
                "scenario_type": task.get("scenario_type", ""),
                "mock_user":     task.get("mock_user", ""),
                "group_pass":    grp.get("pass"),
                "pass_rate":     rules_passed / rules_total if rules_total > 0 else None,
                "threshold":     grp.get("pass_rate_threshold"),
                "rules_passed":  rules_passed,
                "rules_total":   rules_total,
            })

    return records


def main():
    parser = argparse.ArgumentParser(description="Save guardrail eval records as a baseline")
    parser.add_argument("--events", required=True, help="Path to events JSON file")
    parser.add_argument("--exp-id", required=True, help="Experiment UUID")
    parser.add_argument("--exp-name", required=True, help="Experiment name")
    parser.add_argument("--output", required=True, help="Output path for baseline JSON")
    args = parser.parse_args()

    with open(args.events) as f:
        events = [e for e in json.load(f) if e]

    records = extract(events)
    output = os.path.expanduser(args.output)
    data = {
        "experiment_id":   args.exp_id,
        "experiment_name": args.exp_name,
        "created":         datetime.utcnow().strftime("%Y-%m-%d"),
        "records":         records,
    }
    with open(output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(records)} records to {output}")
    by_group: dict[str, int] = {}
    for r in records:
        by_group[r["category"]] = by_group.get(r["category"], 0) + 1
    for cat, n in sorted(by_group.items()):
        print(f"  {cat}: {n} records")


if __name__ == "__main__":
    main()
