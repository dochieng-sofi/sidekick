---
description: "Guardrail eval pipeline — run evals, fetch events, generate Excel + deep analysis report, compare runs, save baselines"
model: opus
allowed-tools: >
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/resolve_experiment.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/summarize_results.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/format_slack.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/fetch_events.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/extract_guardrails.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/build_excel.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/compare_runs.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/save_baseline.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/run_batch.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/aggregate_runs.py*),
  Bash(PYENV_VERSION=3.12.0 python3 $SKILL_DIR/compare_batches.py*),
  Bash(PYENV_VERSION=3.12.0 python3 -c "import openpyxl, httpx" 2>/dev/null || PYENV_VERSION=3.12.0 python3 -m pip install openpyxl httpx -q),
  Bash(mkdir:*),
  Bash(BRAINTRUST_TAG_FILTER=* PYENV_VERSION=* */evaluation/runners/run_evals.sh*),
  Bash(PYENV_VERSION=* */evaluation/runners/run_evals.sh*),
  Bash(cd */sierra-mock-clone*),
  Bash(node:*),
  Write
argument-hint: "<experiment-url|id> [--output report.xlsx] [--events events.json] | run [--tag guardrails|all] | batch --phase pre|post|current --runs N [--parallel N] [--tag guardrails|all] | compare <b1.json> <b2.json> | compare-batches <left.json> <right.json> | baseline <events.json>"
triggers:
  - "run guardrail evals"
  - "guardrail eval report"
  - "fetch braintrust events"
  - "compare guardrail runs"
  - "save eval baseline"
  - "guardrail excel"
  - "eval-braintrust"
  - "analyze guardrail"
  - "guardrail analysis"
  - "guardrail results"
  - "guardrail report"
  - "run the guardrails"
  - "eval report"
---

# Eval Braintrust

Guardrail eval pipeline for the openai-member-agent. Six modes:
- **analyze** (default): fetch events → generate Excel workbook → generate markdown deep analysis report
- **run**: run guardrail evals, then automatically proceed to analyze
- **batch**: run N evals with controlled concurrency, label them as `pre`, `post`, or `current`, fetch baselines, and aggregate the batch
- **compare**: compare two saved baselines, show accuracy deltas
- **compare-batches**: compare two batch aggregate JSON files
- **baseline**: save a baseline from an events file for future comparison

## Skill Directory

The skill ships with pre-built scripts. The harness sets `$SKILL_DIR` at the top of every invocation to the skill directory. Reference scripts as:
```
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/resolve_experiment.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/fetch_events.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/summarize_results.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/format_slack.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/extract_guardrails.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/build_excel.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/compare_runs.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/save_baseline.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/run_batch.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/aggregate_runs.py
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/compare_batches.py
```
**Never use curl. Never write inline python3 -c. Every API call and data transformation goes through a shipped script.** This is not just style — inline commands and curl with env vars trigger permission prompts every time.

## Help

If `$ARGUMENTS` is `help` or empty, print this usage and stop:

```
Eval Braintrust — guardrail eval pipeline

Modes:
  /eval-braintrust <url|id>            Fetch events + generate Excel + analysis report
  /eval-braintrust run [--tag guardrails|all]  Run evals, then analyze
  /eval-braintrust batch --phase pre|post|current --runs N [--parallel N] [--tag guardrails|all]
                                             Run repeated evals concurrently and combine the results
  /eval-braintrust compare <b1> <b2>   Compare two saved baselines
  /eval-braintrust compare-batches <left.json> <right.json>
                                             Compare aggregated batch summaries
  /eval-braintrust baseline <events>   Save a baseline for future comparison

Options (analyze mode):
  --output path.xlsx     Excel output path (default: ~/Desktop/guardrail_<fragment>.xlsx)
  --report path.md       Markdown report path (default: ./guardrail-report-<fragment>.md)
  --events path.json     Skip fetch, use existing events file

Experiment ID formats accepted:
  Full URL:   https://www.braintrust.dev/app/SoFi/p/CI%20Regression%20Tests/experiments/test-cases-super-merge-train-ba2f49c6
  Full UUID:  550e8400-e29b-41d4-a716-446655440000
  Short ID:   ba2f49c6  (last 8 chars of experiment name)

Scoring model:
  Block Accuracy   — compliance risk — % of block scenario tests passing threshold
  Pass Accuracy    — member friction — % of pass scenario tests passing threshold
  Escalate Accuracy — crisis handling — % of escalate scenario tests passing threshold
  Thresholds are per-category (e.g., Regulated Advice: 0.83, Jailbreak: 0.95)

Prerequisites:
  BRAINTRUST_API_KEY in .env: set -a && source .env && set +a
  Sierra mock (run and batch modes only): cd .../sierra-mock-clone/api/server && npm start
```

## How To Use

Use batch mode when you want repeated samples that can be combined later.

### 1. Run a pre-change batch

Use this before making or switching to the branch changes you want to evaluate:

```bash
/eval-braintrust batch \
  --phase pre \
  --runs 5 \
  --parallel 5 \
  --tag guardrails \
  --provider super \
  --project "OpenAI POC" \
  --output-dir /tmp/guardrails-pre
```

The batch runner defaults `--project-root` from:
1. `OPENAI_MEMBER_AGENT_ROOT`
2. `~/code/openai-member-agent`

The post-processing Python binary defaults from:
1. `--python-bin`
2. `EVAL_BRAINTRUST_PYTHON`
3. `~/.pyenv/versions/3.12.0/bin/python3`
4. `python3` on `PATH`

This writes:
- `/tmp/guardrails-pre/manifest.json`
- `/tmp/guardrails-pre/aggregate.json`
- `/tmp/guardrails-pre/logs/`
- `/tmp/guardrails-pre/events/`
- `/tmp/guardrails-pre/baselines/`

### 2. Run a post-change batch

Use this after the code change is present in the current branch:

```bash
/eval-braintrust batch \
  --phase post \
  --runs 5 \
  --parallel 5 \
  --tag guardrails \
  --provider super \
  --project "OpenAI POC" \
  --output-dir /tmp/guardrails-post
```

### 3. Compare pre vs post

```bash
/eval-braintrust compare-batches \
  /tmp/guardrails-pre/aggregate.json \
  /tmp/guardrails-post/aggregate.json
```

This compares the mean batch accuracy for each category/scenario and reports percentage-point deltas.

### 4. Run only the current branch without pre/post framing

Use `current` when you just want repeated sampling of whatever is checked out now:

```bash
/eval-braintrust batch \
  --phase current \
  --runs 3 \
  --parallel 3 \
  --tag guardrails \
  --provider super \
  --project "OpenAI POC" \
  --project-root "$OPENAI_MEMBER_AGENT_ROOT" \
  --python-bin "$EVAL_BRAINTRUST_PYTHON" \
  --output-dir /tmp/guardrails-current
```

### 5. Run every test instead of guardrails only

Use `--tag all` to disable tag filtering:

```bash
/eval-braintrust batch \
  --phase current \
  --runs 3 \
  --parallel 3 \
  --tag all \
  --provider super \
  --project "OpenAI POC" \
  --output-dir /tmp/all-tests-current
```

### 6. Use a different Braintrust project

Override `--project` when the experiments are expected somewhere other than the local-run default:

```bash
/eval-braintrust batch \
  --phase current \
  --runs 3 \
  --parallel 3 \
  --tag guardrails \
  --provider super \
  --project "CI Regression Tests" \
  --output-dir /tmp/guardrails-ci-project
```

### 7. Recommended operating pattern

For change evaluation:
1. Run `pre` on the base branch or before the edit.
2. Make the code change.
3. Run `post` on the changed branch.
4. Compare the two aggregate files with `compare-batches`.
5. Keep the two output directories together when sharing results so the manifest and logs remain inspectable.

### 8. What the artifacts mean

- `manifest.json` — run metadata, branch/SHA, project, output paths, and per-run success state
- `aggregate.json` — combined batch statistics across successful runs
- `logs/` — stdout/stderr from each eval child process
- `events/` — fetched Braintrust events per run
- `baselines/` — extracted normalized baseline JSON per run

## Argument Parsing

Parse `$ARGUMENTS` to detect mode:

1. **run** — starts with `run`. Extract optional `--tag` (default: `guardrails`).
2. **batch** — starts with `batch`. Extract:
   - `--phase pre|post|current` — required
   - `--runs N` — required
   - `--parallel N` — optional, defaults to `N`
   - `--tag guardrails|all` — optional, defaults to `guardrails`
   - `--provider super|openai` — optional, defaults to `super`
   - `--project PROJECT` — optional, defaults to `OpenAI POC`
   - `--output-dir PATH` — optional
3. **compare** — starts with `compare`. Extract two baseline paths.
4. **compare-batches** — starts with `compare-batches`. Extract two aggregate JSON paths.
5. **baseline** — starts with `baseline`. Extract events file path and optional `--output`.
6. **analyze** (default) — any other input. Extract:
   - Experiment identifier (URL, UUID, or short ID)
   - `--output PATH` — Excel output path
   - `--report PATH` — Markdown report path
   - `--events PATH` — existing events file to skip fetch

## Prerequisites Check

Before any network or file operations:

### BRAINTRUST_API_KEY

The key must be set in the shell environment. Run `resolve_experiment.py` — it will fail fast with a clear message if the key is missing or points to the wrong org. No separate check needed.

**Braintrust has two orgs — `SoFi` and `sofi-dev`.** Experiments from the openai-member-agent CI run in `sofi-dev`. If `resolve_experiment.py` can't find the experiment, the key is for the wrong org. Get a `sofi-dev` key from `braintrust.dev/app/sofi-dev/settings/api-keys` and `export BRAINTRUST_API_KEY=<key>`.

### Prod evals project logs

Keep `BRAINTRUST_API_KEY` for normal experiment resolution and event fetching. Use
`BRAINTRUST_API_KEY_EVALS_PROD` only when the task explicitly targets project-log
data from `coach-live-traffic-evals-prod`, such as a Braintrust trace URL with
`object_type=project_logs` for that project. Do not substitute the prod-evals key
for ordinary CI experiment workflows.

### Python dependencies (analyze/run modes)

```bash
PYENV_VERSION=3.12.0 python3 -c "import openpyxl, httpx" 2>/dev/null || PYENV_VERSION=3.12.0 python3 -m pip install openpyxl httpx -q
```

---

## Mode: Run

Run one guardrail eval, then proceed to analyze.

### Step 1: Check Sierra mock
```bash
cd "${OPENAI_MEMBER_AGENT_ROOT:-$HOME/code/openai-member-agent}/sierra-mock-clone/api/server" && node dist/index.js &
```
Wait 5s, then check with:
```bash
PYENV_VERSION=3.12.0 python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3001/health', timeout=5); print('Mock ready')" 2>/dev/null || echo "Mock not responding"
```
If not responding after 10s, stop and tell the user to run `./run.sh mock` from the repo root.

### Step 2: Run evals

**With tag filter (default: guardrails):**
```bash
PYENV_VERSION=3.12.0 "${OPENAI_MEMBER_AGENT_ROOT:-$HOME/code/openai-member-agent}/evaluation/runners/run_evals.sh" --tag "<tag>"
```

**Without tag filter (all categories):**
```bash
PYENV_VERSION=3.12.0 "${OPENAI_MEMBER_AGENT_ROOT:-$HOME/code/openai-member-agent}/evaluation/runners/run_evals.sh"
```

Stream all output live. The run takes ~25 minutes for the full guardrail suite.

### Step 3: Capture experiment name

After the run completes, find the most recently created experiment:
```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/resolve_experiment.py \
  --identifier "test-cases-super" \
  --project "OpenAI POC"
```
The script lists experiments newest-first; the first match for `test-cases-super` is the one just created. If the eval exited non-zero, stop and report the error.

### Step 4: Proceed to analyze mode

Use the captured experiment name as the input identifier. Continue to **Mode: Analyze** below.

---

## Mode: Batch

Use batch mode for repeated pre-change, post-change, or current-branch sampling.
Each child run receives a unique `BRAINTRUST_EXPERIMENT_NAME`, so concurrent
runs can be resolved exactly instead of relying on "newest experiment" ordering.

Example:
```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/run_batch.py \
  --phase pre \
  --runs 5 \
  --parallel 5 \
  --tag guardrails \
  --provider super \
  --output-dir "/tmp/eval-pre-guardrails"
```

Behavior:
- launches up to `--parallel` eval processes at once
- treats `--tag all` as no tag filter
- uses `MOCK_SERVICE_URL=http://127.0.0.1:3001` by default so mock health checks avoid the localhost/IPv6 mismatch
- resolves local batch experiments against Braintrust project `OpenAI POC` by default; pass `--project` to override
- writes per-run logs under `<output-dir>/logs/`
- resolves each experiment deterministically
- fetches events and saves one baseline per run
- writes `<output-dir>/manifest.json`
- writes `<output-dir>/aggregate.json`

For current-branch-only sampling, use `--phase current`.

If the user asks for multiple runs but does not specify phase, ask whether they want `pre`, `post`, or `current`.

---

## Mode: Analyze

### Phase 1: Resolve experiment ID

Pass the identifier (URL, name, or short fragment) to the shipped script:

```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/resolve_experiment.py \
  --identifier "<url-or-name-or-fragment>" \
  --project "CI Regression Tests"
```

Output is `<uuid> <experiment-name>` on one line. Parse it:
- `EXP_ID` = first token (full UUID)
- `EXP_FRAGMENT` = last 8 chars of the experiment name (e.g. `aa18ec60`)

If the script exits 1, it prints the available experiments — tell the user which experiment to pick or that they need the `sofi-dev` API key.

### Phase 2: Fetch events

If `--events` was provided and the file exists, skip this phase and use that file.

Create scratch dir:
```bash
mkdir -p /tmp/braintrust-$EXP_FRAGMENT
```

Fetch all events:
```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/fetch_events.py --exp-id "$EXP_ID" --output "/tmp/braintrust-$EXP_FRAGMENT/events.json"
```

Report page-by-page progress as it runs. This typically takes 1-3 minutes for 296 guardrail tests (~20K events).

### Phase 3: Generate Excel workbook

Default output path: `~/Desktop/guardrail_$EXP_FRAGMENT.xlsx`

```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/build_excel.py \
  --events "/tmp/braintrust-$EXP_FRAGMENT/events.json" \
  --output "$EXCEL_OUTPUT" \
  --exp-name "$EXP_FRAGMENT"
```

Report the tab-by-tab build progress. Print the saved path when done.

### Phase 4: Extract records for analysis

```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/extract_guardrails.py \
  --events "/tmp/braintrust-$EXP_FRAGMENT/events.json" \
  > "/tmp/braintrust-$EXP_FRAGMENT/records.json"
```

Compute all analysis stats needed for the report:
```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/summarize_results.py \
  --records "/tmp/braintrust-$EXP_FRAGMENT/records.json" \
  > "/tmp/braintrust-$EXP_FRAGMENT/summary.json"
```

The output is saved to `summary.json`. Read it to get `category_summary`, `rule_stats`, `failures`, and `top_failing_rules`.

### Phase 5: Generate deep analysis report

Build a markdown report and save it to `$REPORT_OUTPUT` (default: `./guardrail-report-$EXP_FRAGMENT.md`) using the Write tool.

**Report structure:**

#### Title + link
```markdown
# Guardrail Eval Report: <experiment_name>

[Braintrust →](<permalink>)  |  Generated: <date>
```

#### Summary table

All 7 categories × 3 accuracy scores. For each cell: `XX% (N/M)`. Color in Excel; in markdown use ✅ ≥90%, ⚠️ 70-89%, ❌ <70%.

```markdown
| Category | Threshold | Block Accuracy | Pass Accuracy | Escalate Accuracy | Total |
| :--- | :---: | ---: | ---: | ---: | ---: |
```

#### Per-category sections (for categories with failures)

For each category that has at least one failure, generate a section. Order: worst Block Accuracy first.

**Section header:** `## <Category Name>`

**Accuracy breakdown:**
```markdown
Block Accuracy: XX% (N/M)  |  Pass Accuracy: XX% (N/M)  |  Threshold: 0.83 (6/7 rules must pass)
```

**Per-rule failure table** (only rules with at least one failure, sorted by failure count descending):
```markdown
| Rule | Failures | Pass Rate | Notes |
| :--- | ---: | ---: | :--- |
| A-03 | 12 | 42% | No predictions or guarantees about outcomes |
```

Build this by scanning `criteria_results` across all records for this category.

**Common patterns** — 2-3 sentences describing the dominant failure themes. Look for clustering in:
- Which scenario_type (block vs pass) is failing more
- Which rules are the top 3 offenders
- Any shared patterns in reasoning text

**Deep-dives** — 3-5 representative failures, prioritizing:
- Different scenario_types
- Different rules
- Most egregious or clearest failures

```markdown
***"<user_query truncated to ~80 chars>" (<scenario_type>, <rule>, score <pass_rate>)***

<2-3 sentences: what the agent did, why it fails this rule, specific quote from response if helpful.>
```

#### Aggregate-only categories

For categories with 100% pass rate across all scenario types, include a brief one-liner:
`**<Category>:** All N tests passing. ✅`

#### Priority fixes

Table of top failing rules across all categories, sorted by total failure count:
```markdown
| Rule | Category | Failures | Fail Rate | Pattern |
| :--- | :--- | ---: | ---: | :--- |
```
"Pattern" = one-sentence description of what the agent is consistently doing wrong.

### Output

Output is controlled by flags. **Default (no flag): generate both.** `--slack`: Slack summary only. `--report`: deep-dive only.

**Step 1 — run `format_slack.py` with `--output`** (unless `--report` only):
```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/format_slack.py \
  --summary "/tmp/braintrust-$EXP_FRAGMENT/summary.json" \
  --exp-name "$EXP_NAME" \
  --exp-url "$EXP_URL" \
  --excel "~/Desktop/guardrail_$EXP_FRAGMENT.xlsx" \
  --output "/tmp/braintrust-$EXP_FRAGMENT/slack_report.txt"
```

**Step 2 — read the file and print as your response text.** Do not rely on bash output being visible — Codex collapses long bash output. Read the file and echo it verbatim as your message:

```
Read: /tmp/braintrust-$EXP_FRAGMENT/slack_report.txt
```

Then print the file contents as your response.

**Step 3 — deep-dive narrative** (unless `--slack` only): follow immediately after the Slack block in the same response, per-category sections as described above.

---

## Mode: Compare

Load two baseline files and print an accuracy comparison.

```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/compare_runs.py \
  --baseline1 "$BASELINE1" \
  --baseline2 "$BASELINE2"
```

Print the output, then summarize in 2-3 sentences: which categories improved, which regressed, and the magnitude.

---

## Mode: Compare Batches

Compare two batch aggregate JSON files:

```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/compare_batches.py \
  --left "$LEFT_AGGREGATE" \
  --right "$RIGHT_AGGREGATE"
```

Use this for `pre` vs `post` comparison after each side has been run and aggregated.

---

## Mode: Baseline

Save extracted records from an events file to a persistent baseline JSON.

Prompt the user for experiment name if not provided (`--exp-name`). Prompt for output path if not provided (`--output`); suggest `~/Desktop/baseline_<fragment>.json`.

Resolve `EXP_ID` from the events file name or ask the user.

```bash
PYENV_VERSION=3.12.0 python3 $SKILL_DIR/save_baseline.py \
  --events "$EVENTS_FILE" \
  --exp-id "$EXP_ID" \
  --exp-name "$EXP_NAME" \
  --output "$OUTPUT"
```

Print the saved path and record counts per category.

---

## Error Handling

**BRAINTRUST_API_KEY missing from env** — Tell user to run `set -a && source "${OPENAI_MEMBER_AGENT_ROOT:-$HOME/code/openai-member-agent}/.env" && set +a`. Do not proceed.

**Prod project-log trace read gets 403 for `coach-live-traffic-evals-prod`** — Load
`BRAINTRUST_API_KEY_EVALS_PROD` from `${OPENAI_MEMBER_AGENT_ROOT:-$HOME/code/openai-member-agent}/.env`
and use that key only for the prod-evals project-log request. Keep
`BRAINTRUST_API_KEY` unchanged for standard eval experiments.

**Experiment not found via REST** — Show the list of recent experiments from the API response. Ask user to pick one.

**fetch_events.py exits non-zero or returns 0 events** — Report the error. Check if EXP_ID is correct. Do not proceed to Excel or report generation.

**openpyxl ImportError** — Run `pip install openpyxl -q` and retry `build_excel.py` once.

**httpx ImportError** — Run `pip install httpx -q` and retry `fetch_events.py` once.

**Sierra mock not running (run mode)** — Attempt to start it. If it fails to start, stop and tell the user to run `./run.sh mock` from `${OPENAI_MEMBER_AGENT_ROOT:-$HOME/code/openai-member-agent}`.

**Eval script exits non-zero** — Show full output. Do not proceed to analyze. Ask if user wants to investigate or retry.

**No records in a category** — Skip that category's detail and matrix tabs silently. Log it during Excel build.

**Records but no rules discovered (non-RA/CG category)** — Print a warning: "No criteria_results found for <category> — skipping tabs." This means the scorer returned group-level results only.
