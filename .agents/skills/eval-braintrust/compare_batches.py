#!/usr/bin/env python3
"""
Compare two aggregated eval batch summaries.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from compare_runs import GROUP_NAMES, GROUP_ORDER, SCENARIO_LABELS, SCENARIO_ORDER


def load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def delta(pre: float | None, post: float | None) -> str:
    if pre is None or post is None:
        return "—"
    value = (post - pre) * 100
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}pp"


def get_cell(summary: dict[str, Any], group_id: str, scenario: str) -> dict[str, Any] | None:
    return summary.get("summary", {}).get(group_id, {}).get("scenarios", {}).get(scenario)


def print_comparison(left: dict[str, Any], right: dict[str, Any]) -> None:
    print("Batch Comparison")
    print(f"  Left:  {left.get('batch_id')} ({left.get('phase')})")
    print(f"  Right: {right.get('batch_id')} ({right.get('phase')})")
    print()
    print(f"{'Category':<28} {'Score':<20} {'Left Mean':>12} {'Right Mean':>12} {'Delta':>10}")
    print("-" * 86)
    for group_id in GROUP_ORDER:
        category_printed = False
        for scenario in SCENARIO_ORDER:
            left_cell = get_cell(left, group_id, scenario)
            right_cell = get_cell(right, group_id, scenario)
            if not left_cell and not right_cell:
                continue
            category = GROUP_NAMES.get(group_id, group_id) if not category_printed else ""
            left_mean = left_cell.get("mean_accuracy") if left_cell else None
            right_mean = right_cell.get("mean_accuracy") if right_cell else None
            print(
                f"{category:<28} {SCENARIO_LABELS[scenario]:<20} "
                f"{pct(left_mean):>12} {pct(right_mean):>12} {delta(left_mean, right_mean):>10}"
            )
            category_printed = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two eval batch aggregate summaries")
    parser.add_argument("--left", required=True, help="Path to the older/pre aggregate JSON")
    parser.add_argument("--right", required=True, help="Path to the newer/post aggregate JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    left = load_summary(Path(args.left).expanduser())
    right = load_summary(Path(args.right).expanduser())
    print_comparison(left, right)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
