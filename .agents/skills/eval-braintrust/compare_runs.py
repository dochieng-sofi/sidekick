#!/usr/bin/env python3
"""
Compare two guardrail eval baselines, showing per-category accuracy deltas.

Usage:
  python3 compare_runs.py --baseline1 baseline_old.json --baseline2 baseline_new.json
  python3 compare_runs.py --baseline1 baseline_old.json --baseline2 baseline_new.json --csv

Each baseline is produced by save_baseline.py.

Output columns:
  Category | Score         | <baseline1> | <baseline2> | Delta
  ---
  Block Accuracy  = % of "block" scenario tests where group_pass is True
  Pass Accuracy   = % of "pass" scenario tests where group_pass is True
  Escalate Accuracy = % of "escalate" scenario tests where group_pass is True
"""
import argparse
import json
from collections import defaultdict

GROUP_ORDER = [
    "regulated-advice",
    "content-guardrails",
    "crisis-safety",
    "pii-protection",
    "abuse-misuse",
    "jailbreak-injection",
    "anti-money-laundering",
]

GROUP_NAMES = {
    "regulated-advice":      "Regulated Advice",
    "content-guardrails":    "Content Guardrails",
    "crisis-safety":         "Crisis Safety",
    "pii-protection":        "PII Protection",
    "abuse-misuse":          "Abuse & Misuse",
    "jailbreak-injection":   "Jailbreak - Injection",
    "anti-money-laundering": "Anti-Money Laundering",
}

SCENARIO_ORDER = ["block", "pass", "escalate"]
SCENARIO_LABELS = {
    "block":    "Block Accuracy",
    "pass":     "Pass Accuracy",
    "escalate": "Escalate Accuracy",
}


def compute_stats(records: list) -> dict:
    """Returns {group_id: {scenario_type: [passed, total]}}"""
    stats: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for rec in records:
        gid = rec.get("group_id", "")
        stype = rec.get("scenario_type", "")
        if not gid or not stype:
            continue
        stats[gid][stype][1] += 1
        if rec.get("group_pass") is True:
            stats[gid][stype][0] += 1
    return stats


def load_baseline(path: str) -> tuple[str, list]:
    with open(path) as f:
        data = json.load(f)
    return data.get("experiment_name", path), data.get("records", [])


def pct(passed: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{100 * passed / total:.1f}%"


def delta_str(a: list, b: list) -> str:
    if a[1] == 0 or b[1] == 0:
        return "—"
    d = (100 * b[0] / b[1]) - (100 * a[0] / a[1])
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.1f}pp"


def main():
    parser = argparse.ArgumentParser(description="Compare two guardrail eval baselines")
    parser.add_argument("--baseline1", required=True, help="Path to first (older) baseline JSON")
    parser.add_argument("--baseline2", required=True, help="Path to second (newer) baseline JSON")
    parser.add_argument("--csv", action="store_true", help="Output CSV instead of text table")
    args = parser.parse_args()

    name1, records1 = load_baseline(args.baseline1)
    name2, records2 = load_baseline(args.baseline2)

    stats1 = compute_stats(records1)
    stats2 = compute_stats(records2)

    if args.csv:
        print(f"Category,Score,{name1},{name2},Delta")
    else:
        w = 28
        print(f"\nComparison")
        print(f"  Baseline 1: {name1}")
        print(f"  Baseline 2: {name2}")
        print()
        print(f"{'Category':<{w}} {'Score':<20} {'Baseline 1':>12} {'Baseline 2':>12} {'Delta':>10}")
        print("-" * (w + 58))

    for gid in GROUP_ORDER:
        gname = GROUP_NAMES.get(gid, gid)
        printed_header = False
        for stype in SCENARIO_ORDER:
            a = stats1[gid][stype]
            b = stats2[gid][stype]
            if a[1] == 0 and b[1] == 0:
                continue
            label = SCENARIO_LABELS[stype]
            if args.csv:
                print(f"{gname},{label},{pct(*a)},{pct(*b)},{delta_str(a, b)}")
            else:
                cat_col = gname if not printed_header else ""
                print(
                    f"{cat_col:<{w}} {label:<20} {pct(*a):>12} {pct(*b):>12} {delta_str(a, b):>10}"
                )
                printed_header = True

    if not args.csv:
        print()


if __name__ == "__main__":
    main()
