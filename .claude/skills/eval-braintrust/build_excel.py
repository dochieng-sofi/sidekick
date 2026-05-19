#!/usr/bin/env python3
"""
Generate a 15-tab guardrail evaluation Excel workbook.

Tabs:
  1.     Summary                  — all 7 categories x Block/Pass/Escalate Accuracy
  2-8.   <Category>               — per-rule detail rows, sorted by scenario_type then pass/fail
  9-15.  <Category> Matrix        — rules as columns, one row per test case

Rules for Regulated Advice and Content Guardrails are hardcoded for stable ordering.
Rules for all other categories are discovered dynamically from criteria_results in the events.

Usage:
  python3 build_excel.py --events /tmp/bt_events.json --output report.xlsx [--exp-name ba2f49c6]
"""
import argparse
import json
import os
from collections import OrderedDict, defaultdict

try:
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("openpyxl is required: pip install openpyxl")
    raise SystemExit(1)

# ── Category ordering ─────────────────────────────────────────────────────────

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

MATRIX_NAMES = {
    "regulated-advice":      "RA Matrix",
    "content-guardrails":    "CG Matrix",
    "crisis-safety":         "Crisis Safety Matrix",
    "pii-protection":        "PII Matrix",
    "abuse-misuse":          "Abuse Matrix",
    "jailbreak-injection":   "Jailbreak Matrix",
    "anti-money-laundering": "AML Matrix",
}

# Stable rule ordering for RA and CG; other categories discovered from data
RA_RULES = ["A-01", "A-02", "A-03", "A-04", "A-05", "L-01", "L-02"]

CG_RULES = [
    "C-CLF-01",
    "C-GLOSS-01", "C-GLOSS-02", "C-GLOSS-03", "C-GLOSS-04",
    "C-GLOSS-05", "C-GLOSS-06", "C-GLOSS-07",
    "C-GNS-01",  "C-GNS-06",  "C-GNS-07",  "C-GNS-08",  "C-GNS-09",  "C-GNS-10",
    "C-GNS-11",  "C-GNS-12",  "C-GNS-13",  "C-GNS-14",  "C-GNS-15",  "C-GNS-16",  "C-GNS-17",
    "C-GRAM-01", "C-GRAM-02", "C-GRAM-03", "C-GRAM-04", "C-GRAM-05",
    "C-GRAM-06", "C-GRAM-07", "C-GRAM-08", "C-GRAM-09",
    "C-POV-01",  "C-POV-02",
    "C-VOICE-01", "C-VOICE-02", "C-VOICE-03", "C-VOICE-04",
]

HARDCODED_RULES = {
    "regulated-advice":   RA_RULES,
    "content-guardrails": CG_RULES,
}

# ── Styles ────────────────────────────────────────────────────────────────────

HDR_FILL   = PatternFill("solid", fgColor="1F4E79")
PASS_FILL  = PatternFill("solid", fgColor="C6EFCE")
FAIL_FILL  = PatternFill("solid", fgColor="FFC7CE")
AMBER_FILL = PatternFill("solid", fgColor="FFEB9C")
NA_FILL    = PatternFill("solid", fgColor="F2F2F2")

HDR_FONT  = Font(bold=True, color="FFFFFF", size=10)
BOLD_F    = Font(bold=True, size=10)
NORMAL_F  = Font(size=10)
WRAP_TOP  = Alignment(wrap_text=True, vertical="top")
CTR_TOP   = Alignment(horizontal="center", vertical="top", wrap_text=True)
THIN      = Side(style="thin", color="CCCCCC")
BORDER    = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COMMENT_AUTHOR = "Coach Eval"

STYPE_ORDER = {"block": 0, "pass": 1, "escalate": 2, "": 3}


def acc_fill(rate: float | None) -> PatternFill:
    if rate is None:
        return NA_FILL
    if rate >= 0.9:
        return PASS_FILL
    if rate >= 0.7:
        return AMBER_FILL
    return FAIL_FILL


def pass_fill(v) -> PatternFill:
    return PASS_FILL if v is True else (FAIL_FILL if v is False else NA_FILL)


def plabel(v) -> str:
    return "PASS" if v is True else ("FAIL" if v is False else "—")


def wcell(ws, row, col, value, fill=None, bold=False, center=False, comment_text=None):
    c = ws.cell(row=row, column=col, value=value)
    c.fill = fill if fill is not None else PatternFill()
    c.font = BOLD_F if bold else NORMAL_F
    c.alignment = CTR_TOP if center else WRAP_TOP
    c.border = BORDER
    if comment_text and comment_text.strip():
        c.comment = Comment(comment_text.strip(), COMMENT_AUTHOR)
    return c


def write_header(ws, labels, row=1):
    for ci, label in enumerate(labels, 1):
        c = ws.cell(row=row, column=ci, value=label)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.alignment = CTR_TOP
        c.border = BORDER


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def pct_str(p: int, t: int) -> str:
    if t == 0:
        return "—"
    return f"{100 * p / t:.0f}%  ({p}/{t})"


def result_preview(v, reasoning: str, max_chars: int) -> str:
    label = plabel(v)
    if not reasoning or not reasoning.strip():
        return label
    preview = reasoning.strip()
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "…"
    return f"{label}\n\n{preview}"


# ── Extraction ────────────────────────────────────────────────────────────────

def get_groups(meta):
    if not isinstance(meta, dict):
        return []
    if "groups" in meta:
        return meta["groups"]
    if "Assertions" in meta:
        return meta["Assertions"].get("groups", [])
    return []


def extract_records(events: list) -> list:
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
            if gid not in GROUP_NAMES:
                continue
            records.append({
                "group_id":        gid,
                "category":        GROUP_NAMES[gid],
                "test_id":         task.get("test_id", ""),
                "scenario_type":   task.get("scenario_type", ""),
                "user_query":      task.get("user_query", ""),
                "mock_user":       task.get("mock_user", ""),
                "response":        task.get("response", ""),
                "group_pass":      grp.get("pass"),
                "threshold":       grp.get("pass_rate_threshold"),
                "criteria_results": [
                    {
                        "criteria":  cr.get("criteria", ""),
                        "pass":      cr.get("pass"),
                        "reasoning": cr.get("reasoning", "") or "",
                    }
                    for cr in (grp.get("criteria_results") or [])
                    if isinstance(cr, dict)
                ],
            })

    return records


def discover_rules(records: list, group_id: str) -> list:
    seen: OrderedDict = OrderedDict()
    for rec in records:
        if rec["group_id"] != group_id:
            continue
        for cr in rec["criteria_results"]:
            rid = cr.get("criteria", "")
            if rid:
                seen[rid] = True
    return list(seen.keys())


def get_rules(records: list, group_id: str) -> list:
    if group_id in HARDCODED_RULES:
        return HARDCODED_RULES[group_id]
    return discover_rules(records, group_id)


def sort_key(rec):
    return (
        STYPE_ORDER.get(rec.get("scenario_type", ""), 3),
        rec.get("group_pass") is True,
        rec.get("test_id", ""),
    )


# ── Summary sheet ─────────────────────────────────────────────────────────────

def make_summary_sheet(wb, records: list):
    ws = wb.create_sheet("Summary")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

    write_header(ws, [
        "Category", "Threshold",
        "Block Tests", "Block Accuracy",
        "Pass Tests", "Pass Accuracy",
        "Escalate Tests", "Escalate Accuracy",
        "Total",
    ])
    set_widths(ws, [28, 12, 12, 18, 12, 18, 14, 20, 8])

    stats: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    thresholds: dict = defaultdict(set)
    for rec in records:
        gid = rec["group_id"]
        stype = rec.get("scenario_type", "")
        stats[gid][stype][1] += 1
        if rec.get("group_pass") is True:
            stats[gid][stype][0] += 1
        t = rec.get("threshold")
        if t is not None:
            thresholds[gid].add(t)

    row = 2
    for gid in GROUP_ORDER:
        if not stats[gid] and not thresholds[gid]:
            continue
        gname = GROUP_NAMES[gid]
        ts = thresholds.get(gid, set())
        if len(ts) == 1:
            threshold_str = str(round(list(ts)[0], 2))
        elif len(ts) > 1:
            threshold_str = f"{min(ts):.2f}–{max(ts):.2f}"
        else:
            threshold_str = "—"

        bp, bt = stats[gid]["block"]
        pp, pt = stats[gid]["pass"]
        ep, et = stats[gid]["escalate"]
        total = sum(v[1] for v in stats[gid].values())

        brate = bp / bt if bt > 0 else None
        prate = pp / pt if pt > 0 else None
        erate = ep / et if et > 0 else None

        wcell(ws, row, 1, gname, bold=True)
        wcell(ws, row, 2, threshold_str, center=True)
        wcell(ws, row, 3, bt if bt > 0 else "—", center=True)
        wcell(ws, row, 4, pct_str(bp, bt), fill=acc_fill(brate), center=True)
        wcell(ws, row, 5, pt if pt > 0 else "—", center=True)
        wcell(ws, row, 6, pct_str(pp, pt), fill=acc_fill(prate), center=True)
        wcell(ws, row, 7, et if et > 0 else "—", center=True)
        wcell(ws, row, 8, pct_str(ep, et), fill=acc_fill(erate), center=True)
        wcell(ws, row, 9, total, center=True)
        ws.row_dimensions[row].height = 20
        row += 1


# ── Detail sheet ──────────────────────────────────────────────────────────────
# Cols: Test ID | Scenario Type | Mock User | Question | Agent Response | Overall | Rule | Result & Reasoning

def make_detail_sheet(wb, sheet_name: str, records: list, group_id: str, rule_ids: list):
    ws = wb.create_sheet(sheet_name)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

    write_header(ws, [
        "Test ID", "Scenario Type", "Mock User", "Question",
        "Agent Response", "Overall", "Rule", "Result & Reasoning",
    ])
    set_widths(ws, [36, 14, 22, 48, 75, 10, 14, 52])

    recs = sorted([r for r in records if r["group_id"] == group_id], key=sort_key)

    row = 2
    for rec in recs:
        crs_map = {cr["criteria"]: cr for cr in rec["criteria_results"] if cr.get("criteria")}
        of = pass_fill(rec.get("group_pass"))
        resp = (rec.get("response") or "")[:1200]
        first = True
        for rid in rule_ids:
            cr = crs_map.get(rid)
            if cr is None:
                continue
            reasoning = cr.get("reasoning", "") or ""
            rv = cr.get("pass")
            wcell(ws, row, 1, rec["test_id"] if first else "", fill=of if first else None, bold=first)
            wcell(ws, row, 2, rec.get("scenario_type", "") if first else "")
            wcell(ws, row, 3, rec.get("mock_user", "") if first else "")
            wcell(ws, row, 4, rec.get("user_query", "") if first else "")
            wcell(ws, row, 5, resp if first else "")
            wcell(ws, row, 6,
                  plabel(rec.get("group_pass")) if first else "",
                  fill=of if first else None, center=True)
            wcell(ws, row, 7, rid)
            wcell(ws, row, 8,
                  value=result_preview(rv, reasoning, 350),
                  fill=pass_fill(rv), comment_text=reasoning)
            ws.row_dimensions[row].height = 60
            row += 1
            first = False


# ── Matrix sheet ──────────────────────────────────────────────────────────────
# Cols: Test ID | Scenario Type | Mock User | Question | Agent Response | [rules…] | Overall
# Freeze: col F (cols A-E pinned — Test ID, Scenario Type, Mock User, Question, Agent Response)

def make_matrix_sheet(wb, sheet_name: str, records: list, group_id: str, rule_ids: list):
    ws = wb.create_sheet(sheet_name)
    ws.sheet_view.showGridLines = False

    n = len(rule_ids)
    RS = 6          # first rule column (1-indexed)
    OC = RS + n     # Overall column

    ws.freeze_panes = f"{get_column_letter(RS)}2"

    write_header(ws, [
        "Test ID", "Scenario Type", "Mock User", "Question", "Agent Response",
    ] + rule_ids + ["Overall"])

    rule_col_w = 26 if n <= 10 else 20
    set_widths(ws, [36, 14, 22, 50, 80] + [rule_col_w] * n + [10])

    recs = sorted([r for r in records if r["group_id"] == group_id], key=sort_key)

    row = 2
    preview_chars = 200 if n > 10 else 300
    for rec in recs:
        crs_map = {cr["criteria"]: cr for cr in rec["criteria_results"] if cr.get("criteria")}
        of = pass_fill(rec.get("group_pass"))
        wcell(ws, row, 1, rec["test_id"], fill=of, bold=True)
        wcell(ws, row, 2, rec.get("scenario_type", ""))
        wcell(ws, row, 3, rec.get("mock_user", ""))
        wcell(ws, row, 4, rec.get("user_query", ""))
        wcell(ws, row, 5, (rec.get("response") or "")[:2000])
        for i, rid in enumerate(rule_ids):
            cr = crs_map.get(rid)
            rv = cr.get("pass") if cr else None
            reasoning = (cr.get("reasoning", "") or "") if cr else ""
            wcell(ws, row, RS + i,
                  value=result_preview(rv, reasoning, preview_chars) if cr else "—",
                  fill=pass_fill(rv) if cr else NA_FILL,
                  comment_text=reasoning)
        wcell(ws, row, OC, plabel(rec.get("group_pass")), fill=of, center=True, bold=True)
        ws.row_dimensions[row].height = 80
        row += 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate 15-tab guardrail Excel workbook")
    parser.add_argument("--events", required=True, help="Path to events JSON file")
    parser.add_argument("--output", required=True, help="Output path (.xlsx)")
    parser.add_argument("--exp-name", default="", help="Experiment name/fragment for logging")
    args = parser.parse_args()

    print(f"Loading events from {args.events}...")
    with open(args.events) as f:
        events = [e for e in json.load(f) if e]
    print(f"  {len(events)} events loaded")

    print("Extracting guardrail records...")
    records = extract_records(events)
    print(f"  {len(records)} guardrail records extracted")

    wb = Workbook()
    wb.remove(wb.active)

    print("Building Summary tab...")
    make_summary_sheet(wb, records)

    for gid in GROUP_ORDER:
        cat_records = [r for r in records if r["group_id"] == gid]
        if not cat_records:
            print(f"  Skipping {GROUP_NAMES[gid]} — no records found")
            continue
        rule_ids = get_rules(records, gid)
        if not rule_ids:
            print(f"  Skipping {GROUP_NAMES[gid]} — no rules discovered")
            continue

        sheet_name = GROUP_NAMES[gid]
        matrix_name = MATRIX_NAMES[gid]
        print(f"Building {sheet_name} ({len(cat_records)} records, {len(rule_ids)} rules)...")
        make_detail_sheet(wb, sheet_name, records, gid, rule_ids)
        make_matrix_sheet(wb, matrix_name, records, gid, rule_ids)

    output = os.path.expanduser(args.output)
    wb.save(output)
    print(f"\nSaved: {output}")
    for ws in wb.worksheets:
        data_rows = ws.max_row - 1
        print(f"  {ws.title}: {data_rows} data rows")


if __name__ == "__main__":
    main()
