#!/usr/bin/env python3
"""
Extract guardrail records from a Braintrust events JSON file.

Usage:
  python3 extract_guardrails.py --events /tmp/bt_events.json [--group all|regulated-advice|...]

Output: JSON array to stdout, one object per assertion group per test case:
  {
    "category":        "Regulated Advice",
    "group_id":        "regulated-advice",
    "test_id":         "block-apple-stock-advice",
    "scenario_type":   "block",
    "user_query":      "...",
    "mock_user":       "...",
    "response":        "...",
    "group_pass":      true,
    "pass_rate":       0.857,
    "threshold":       0.83,
    "rules_passed":    6,
    "rules_total":     7,
    "criteria_results": [
      {"criteria": "A-01", "pass": true, "reasoning": "..."},
      ...
    ]
  }
"""
import argparse
import json

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


def extract(events: list, group_filter: str | None) -> list:
    task_map = {}
    for e in events:
        if (e.get("span_attributes") or {}).get("name") == "task":
            root = e.get("root_span_id", "")
            inp = e.get("input") or {}
            out = e.get("output") or {}
            uq = inp.get("user_query", "")
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
                "user_query":    " | ".join(uq) if isinstance(uq, list) else str(uq),
                "mock_user":     inp.get("mock_user", ""),
                "response":      out.get("response", "") if isinstance(out, dict) else str(out),
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
            if group_filter and gid != group_filter:
                continue
            crs = [cr for cr in (grp.get("criteria_results") or []) if isinstance(cr, dict)]
            evaluated = [cr for cr in crs if cr.get("pass") is not None]
            rules_passed = sum(1 for cr in evaluated if cr.get("pass") is True)
            rules_total = len(evaluated)
            records.append({
                "category":       GROUP_MAP[gid],
                "group_id":       gid,
                "test_id":        task.get("test_id", ""),
                "scenario_type":  task.get("scenario_type", ""),
                "user_query":     task.get("user_query", ""),
                "mock_user":      task.get("mock_user", ""),
                "response":       task.get("response", ""),
                "group_pass":     grp.get("pass"),
                "pass_rate":      rules_passed / rules_total if rules_total > 0 else None,
                "threshold":      grp.get("pass_rate_threshold"),
                "rules_passed":   rules_passed,
                "rules_total":    rules_total,
                "criteria_results": [
                    {
                        "criteria":  cr.get("criteria", ""),
                        "pass":      cr.get("pass"),
                        "reasoning": cr.get("reasoning", "") or "",
                    }
                    for cr in crs
                ],
            })

    return records


def main():
    parser = argparse.ArgumentParser(description="Extract guardrail records from Braintrust events")
    parser.add_argument("--events", required=True, help="Path to events JSON file")
    parser.add_argument("--group", default="all", help="Group ID to filter, or 'all'")
    args = parser.parse_args()

    with open(args.events) as f:
        events = [e for e in json.load(f) if e]

    group_filter = None if args.group == "all" else args.group
    records = extract(events, group_filter)
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
