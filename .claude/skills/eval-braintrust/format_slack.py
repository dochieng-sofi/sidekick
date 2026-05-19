#!/usr/bin/env python3
# Run with Python 3.12: PYENV_VERSION=3.12.0 python3 format_slack.py
"""
Format guardrail eval results as a Slack-ready console summary.

Structure:
  1. Header
  2. Legend — what Block/Pass/Escalate Accuracy means
  3. Table — Category x Block/Pass/Escalate
  4. Where the failures are — specific, actionable bullets per failing category

Usage:
  python3 format_slack.py \
    --summary /tmp/braintrust-<id>/summary.json \
    --exp-name test-cases-super-merge-train-aa18ec60 \
    --exp-url "https://..." \
    --excel "~/Desktop/guardrail_aa18ec60.xlsx"
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

LEGEND = """\
*What these numbers mean*
• *Block Accuracy* — adversarial requests the agent should refuse. Failing = compliance risk.
• *Pass Accuracy* — legitimate member requests handled without policy violations. Failing = member friction.
• *Escalate Accuracy* — crisis signals correctly routed to human support. Failing = safety risk.

Pass% = (test cases where all applicable rules pass their threshold) / (test cases in that category & scenario)"""


def icon(pct: int | None) -> str:
    if pct is None:
        return ""
    if pct >= 90:
        return "✅"
    if pct >= 40:
        return "⚠️"
    return "❌"


def cell(pct: int | None, passed: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{icon(pct)} {pct}% ({passed}/{total})"


def visual_width(s: str) -> int:
    w = 0
    for ch in s:
        cp = ord(ch)
        if 0x1F000 <= cp <= 0x1FFFF or 0x2600 <= cp <= 0x27BF:
            w += 2
        else:
            w += 1
    return w


def pad(s: str, width: int, align: str = "left") -> str:
    vw = visual_width(s)
    extra = max(0, width - vw)
    if align == "right":
        return " " * extra + s
    if align == "center":
        left = extra // 2
        return " " * left + s + " " * (extra - left)
    return s + " " * extra


def box_table(rows: list[dict], cat_width: int = 23, col_width: int = 16) -> str:
    cols = ["Block Accuracy", "Pass Accuracy", "Escalate Accuracy"]
    col_w = [col_width, col_width + 1, col_width + 3]

    def hline(left, mid, right, fill="─"):
        parts = [fill * (cat_width + 2)] + [fill * (w + 2) for w in col_w]
        return left + mid.join(parts) + right

    lines = [hline("┌", "┬", "┐")]
    hdr_vals = [pad(c, w, "center") for c, w in zip(cols, col_w)]
    lines.append("│" + "│".join(
        [f" {pad('Category', cat_width, 'center')} "] + [f" {v} " for v in hdr_vals]
    ) + "│")
    lines.append(hline("├", "┼", "┤"))

    for i, r in enumerate(rows):
        cells = [f" {pad(r['cat'], cat_width)} "]
        for v, w in zip(r["vals"], col_w):
            cells.append(f" {pad(v, w, 'right')} ")
        lines.append("│" + "│".join(cells) + "│")
        if i < len(rows) - 1:
            lines.append(hline("├", "┼", "┤"))

    lines.append(hline("└", "┴", "┘"))
    return "\n".join(lines)


def failure_bullets(summary: dict) -> list[str]:
    """
    One bullet per failing category, grounded in actual failure data.
    Format mirrors the old Slack reports: category name in italic, specific observation, action.
    """
    cat_map = {c["group_id"]: c for c in summary["category_summary"]}

    # Group failures by category
    failures_by_cat: dict = defaultdict(list)
    for f in summary.get("failures", []):
        failures_by_cat[f["group_id"]].append(f)

    # Top failing rules per category (from rule_stats)
    rule_stats = summary.get("rule_stats", {})

    bullets = []
    for gid in GROUP_ORDER:
        c = cat_map.get(gid)
        if not c:
            continue
        bs = c["by_scenario"]
        b = bs.get("block", {})
        p = bs.get("pass", {})
        e = bs.get("escalate", {})

        # Only emit a bullet for categories with at least one failing scenario
        failing_scenarios = []
        for stype, s, label in [
            ("block", b, "block accuracy"),
            ("pass", p, "pass accuracy"),
            ("escalate", e, "escalate accuracy"),
        ]:
            if s.get("total", 0) > 0 and s.get("pct", 100) < 90:
                failing_scenarios.append((label, s["pct"], s["fail"], s["total"]))

        if not failing_scenarios:
            continue

        cat_name = GROUP_NAMES.get(gid, gid)
        cat_failures = failures_by_cat.get(gid, [])
        top_rules = rule_stats.get(gid, [])
        top_failing = [r for r in top_rules if r["fail"] > 0]

        # Build the bullet body
        parts = []

        # Scenario summary
        scenario_str = ", ".join(
            f"{label} {pct}% ({fail}/{total})"
            for label, pct, fail, total in failing_scenarios
        )
        parts.append(scenario_str)

        # Most common failure pattern from rule data + failure samples
        if top_failing:
            top = top_failing[0]
            rule_id = top["rule_id"]
            note = top["notes"]
            rule_desc = f"{rule_id}" + (f" ({note})" if note else "")

            # Find a concrete example from failure samples
            example = ""
            for f in cat_failures:
                rule_ids = [r["rule"] for r in f.get("failing_rules", [])]
                if rule_id in rule_ids:
                    query = f.get("user_query", "")[:60]
                    reasoning = ""
                    for r in f.get("failing_rules", []):
                        if r["rule"] == rule_id:
                            raw = r.get("reasoning", "") or ""
                            # truncate at word boundary
                            if len(raw) > 100:
                                raw = raw[:100].rsplit(" ", 1)[0] + "…"
                            reasoning = raw
                            break
                    if query:
                        example = f'e.g. "{query}…" — {reasoning}' if reasoning else f'e.g. "{query}…"'
                    break

            if example:
                parts.append(f"Top rule: {rule_desc}. {example}")
            else:
                parts.append(f"Top rule: {rule_desc} ({top['fail']} failures, {top['fail_rate_pct']}% fail rate)")

        bullets.append(f"• *{cat_name}:* {'. '.join(parts)}.")

    return bullets


def main():
    parser = argparse.ArgumentParser(description="Format guardrail eval results for Slack")
    parser.add_argument("--summary", required=True, help="Path to summary.json")
    parser.add_argument("--exp-name", required=True, help="Experiment name")
    parser.add_argument("--exp-url", default="", help="Braintrust URL")
    parser.add_argument("--excel", default="", help="Excel output path")
    parser.add_argument("--output", default="", help="Write report to this file (Claude reads it and prints as response text)")
    args = parser.parse_args()

    with open(args.summary) as f:
        summary = json.load(f)

    total = summary["total_records"]
    failures_count = summary["total_failures"]
    cat_map = {c["group_id"]: c for c in summary["category_summary"]}

    rows = []
    for gid in GROUP_ORDER:
        c = cat_map.get(gid)
        if not c:
            continue
        bs = c["by_scenario"]
        b, p, e = bs.get("block", {}), bs.get("pass", {}), bs.get("escalate", {})
        pcts = [s.get("pct", 100) for s in [b, p, e] if s.get("total", 0) > 0]
        rows.append({
            "cat": c["category"],
            "sort_key": min(pcts) if pcts else 100,
            "vals": [
                cell(b.get("pct"), b.get("pass", 0), b.get("total", 0)),
                cell(p.get("pct"), p.get("pass", 0), p.get("total", 0)),
                cell(e.get("pct"), e.get("pass", 0), e.get("total", 0)),
            ],
        })
    rows.sort(key=lambda r: r["sort_key"])

    link = f"<{args.exp_url}|Braintrust>" if args.exp_url else "Braintrust"
    excel_note = f" | Excel: {args.excel}" if args.excel else ""

    lines = []
    lines.append(f"*Guardrail Eval — {args.exp_name}*")
    lines.append(f"{link} | {total} tests | {failures_count} failures{excel_note}")
    lines.append("")
    lines.append(LEGEND)
    lines.append("")
    lines.append(box_table(rows))

    bullets = failure_bullets(summary)
    if bullets:
        lines.append("")
        lines.append("*Where the failures are*")
        lines.extend(bullets)

    report = "\n".join(lines)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
    else:
        print(report)


if __name__ == "__main__":
    main()
