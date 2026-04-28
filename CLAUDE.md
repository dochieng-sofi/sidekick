# Sidekick

Team debugging toolkit for cashflow-optimizer. Provides AI-powered log investigation, CI failure analysis, and production debugging.

> **Setup:** Load sidekick alongside a worktree with `claude --add-dir ~/code/sidekick`

## Service Context

- **Service name**: `cashflow-optimizer`
- **Coralogix subsystem**: `cashflow-optimizer`
- **Datadog service tag**: `cashflow-optimizer`
- **Logging**: Logstash JSON encoder (production), Spring Boot colored console (dev)
- **Error tracking**: Rollbar
- **Trace correlation**: OpenTracing via `dd.trace_id`

### Key Dependencies

| Service | Purpose |
|---------|---------|
| Aggregation Service | Financial data aggregation |
| CSM Core | Customer service management |
| Funds Transfer | Money movement operations |
| Account Gateway | Account operations |
| Rewards Service | Rewards/cashback |
| Experimentation Service | Feature flags |

### cashflow-optimizer Source Code Layout

```
service/src/main/kotlin/com/sofi/cashflowoptimizer/
  config/          Spring configuration
  web/controller/  REST controllers
  service/         Business logic
  repository/      Spring Data JPA repositories
  mapper/          DTO mappers
  model/           DTOs and enums
  queue/           Kafka and ActiveMQ handlers
  client/          External service clients
  jobs/            Scheduled/cron tasks
  exception/       Custom exceptions
  utils/           Helpers (including Logger.kt)
```

## Debugging Methodology

When investigating a production issue, follow these steps in order:

1. **Identify the time window** - When did the issue start? Get a precise PST-to-UTC conversion. Always confirm the time range before querying.

2. **Query logs** - Start broad, then narrow:
   - `/cxcli errors cashflow-optimizer <time>` for deduped error summary
   - `/cxcli group cashflow-optimizer <time>` for severity breakdown
   - `/cxcli query cashflow-optimizer <time>` for raw logs with context
   - `/cxcli trace <trace_id> <time>` to follow a specific request

3. **Analyze patterns** - Look for:
   - Error frequency (deduped counts)
   - Severity progression (WARN before ERROR = escalation)
   - Affected identifiers (user IDs, entity IDs, trace IDs)
   - Timestamp clustering (burst vs steady)

4. **Trace through code** - Map log messages to source locations:
   - Grep for the log message string in `service/src/`
   - Follow the code path: controller -> service -> repository/client
   - Identify exception handlers, retry logic, null checks
   - Check for known patterns: missing data, timeout cascades, race conditions

5. **Root cause and repro** - Synthesize findings:
   - Identify the specific triggering condition
   - Rate confidence (High/Medium/Low)
   - Suggest API calls to reproduce
   - Propose a unit test that captures the failure

## Coralogix Reference

### DataPrime Query Patterns

| Filter | Syntax | Example |
|--------|--------|---------|
| By subsystem | `$l.subsystemname == 'name'` | `$l.subsystemname == 'cashflow-optimizer'` |
| Full text (CASE-SENSITIVE) | `$d ~~ 'text'` | `$d ~~ 'NullPointerException'` |
| By severity | `$m.severity == 'Level'` | `$m.severity == 'Error'` |
| By trace ID | `$d ~~ '<trace_id>'` | `$d ~~ '695744b6...'` |
| Group by | `\| groupby <field> agg count() as N` | `groupby $m.severity agg count() as log_count` |
| Limit results | `\| limit N` | `\| limit 50` |
| Count total | `\| count` | NOT `summarize count()` |

### Severity Values

Valid values for `$m.severity` (title case, not all-caps):

| Level | Use |
|-------|-----|
| Debug | Development only |
| Verbose | Detailed tracing |
| Info | Normal operations |
| Warning | Potential issues |
| Error | Failures requiring attention |
| Critical | Severe failures |

## Braintrust MCP - Mandatory Rules

The Braintrust MCP tools have sharp edges that cause silent data loss, timeouts, and misclassification if called naively. These rules apply **every time** you call a Braintrust MCP tool, whether following a skill, doing your own research, or as part of any other task.

### Skills (use when the user asks, or when you need a full report)

| Task | Skill | Example |
|------|-------|---------|
| Analyze an existing experiment | `analyze-braintrust` | `/analyze-braintrust <braintrust-url>` |
| Run evals and generate report | `run-and-analyze` | `/run-and-analyze guardrails` |

### Constraints (apply to ALL Braintrust MCP calls, always)

**sql_query:**
- **Always** pass `shape: "summary"`. Without it you get individual scorer spans (4 per test case), not traces. You will miscount everything.
- **Always** pass `preview_length: 500`. The default (1024) produces responses that exceed output limits and get saved to temp files. Values above 1000 cause HTTP timeouts.
- **Always** name specific columns in `select`. `SELECT *` produces 200K+ char responses.
- **Always** `count(*)` first before fetching rows. Experiments have 300+ traces. The default limit of 10 returns a tiny fraction.
- **Always** set `limit: 100`. Paginate with `ORDER BY created ASC` + `WHERE created > '<last_timestamp>'` if you need more. There is no cursor pagination.
- **Never** use `WHERE ... LIKE '%text%'` on the `expected` field. It returns empty. Filter in Python instead.
- **Never** call `infer_schema`. It returns 70K+ char payloads that exceed output limits.

**Data structure:**
- Categories are in the `tags` array, NOT `metadata`. Metadata is empty in summary view.
- Filter out `"guardrails"` and `"product"` from tags to get the category name.
- The `expected` field is truncated by preview_length. Do NOT `json.loads()` it - use substring matching: `"Expected outcome: BLOCK" in str(expected)`.
- `scores.Assertions` can be 0.5 (partial pass), not just 0 or 1.
- The `input` field can be a dict OR a JSON string. Always handle both: `isinstance(inp, dict)` first, then `json.loads(inp)` as fallback.

**Processing large results:**
- When a tool result says "Output saved to: /path/...", the data is in a temp file. Process it with `python3 -c` and `json.load()`. **Never use the Read tool** on these files - the JSON lines are too long and will exceed token limits.

## Quick Reference

| Task | Say | Invocation |
|------|-----|------------|
| Query service logs | "get recent logs" | `/cxcli query cashflow-optimizer 1h` |
| Error triage | "show errors" | `/cxcli errors cashflow-optimizer 2h` |
| Dedupe patterns | "dedupe log patterns" | `/cxcli dedupe cashflow-optimizer 1h` |
| Severity breakdown | "severity breakdown" | `/cxcli group cashflow-optimizer 1h` |
| Trace a request | "trace this request" | `/cxcli trace <id> 2h` |
| Error count | "how many errors" | `/cxcli count cashflow-optimizer 1h` |
| Coralogix docs | "show Coralogix docs" | `/cxcli docs` |
| Full investigation | "debug this error" | auto-triggers `diagnose` skill |
| CI failure | "CI failed" | auto-triggers `investigate-ci` skill |
| Eval analysis | "analyze braintrust" | auto-triggers `analyze-braintrust` skill |
| Run + analyze evals | "run evals" | auto-triggers `run-and-analyze` skill |
| CI pipelines | "list failed pipelines" | `/glab-ci pipelines` |
| CI job trace | "get job logs" | `/glab-ci trace <job-id>` |
| Create worktree | "create worktree <name>" | `/worktree <name> [base-branch]` |
| Per-worktree context | (edit manually) | `CLAUDE.local.md` in the worktree root |
