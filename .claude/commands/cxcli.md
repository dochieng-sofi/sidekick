---
description: Query and export logs from Coralogix using SoFi's cxcli tool
allowed-tools: Bash(cxcli:*)
argument-hint: <action> [service|query|trace_id] [time] - help|query|errors|dedupe|group|trace|count|docs
---

Query production logs from Coralogix using SoFi's cxcli tool.

## Argument Parsing

Parse `$ARGUMENTS` to identify:
1. **Action** - First word: `help`, `query`, `errors`, `dedupe`, `group`, `trace`, `count`, `docs`
2. **Service/Query/TraceID** - Service name (for query/errors/dedupe/group), DataPrime query (for query), trace ID (for trace)
3. **Time range** - Duration like `1h`, `30m`, `2h`, `1d` (default: 1h)
4. **Limit** - Max logs (default: 100)

**Default service**: If no service is specified and the action expects one, default to `cashflow-optimizer`.

## Actions

### help
Print usage and exit:
```
cxcli Slash Command Usage:

Interactive queries (stdout, NDJSON format):
/cxcli query [service] [time] [limit]       Query logs (raw NDJSON to stdout)
/cxcli query "<dataprime>" [time]            Run custom DataPrime query
/cxcli errors [service] [time]               Error summary (stdout)
/cxcli dedupe [service] [time]               Dedupe all logs by message (stdout)
/cxcli group [service] [time]                Severity breakdown (stdout)
/cxcli trace <trace_id> [time] [limit]       Find logs by Datadog trace ID
/cxcli count [service] [time]                Get total error count

Background queries (for bulk data):
/cxcli query "<dataprime>" [time] --background    Async query, poll for results

Reference:
/cxcli docs                                  Scrape Coralogix docs
/cxcli help                                  Show this help

Default service: cashflow-optimizer
Time formats: 30m, 1h, 2h, 6h, 1d (default: 1h)
Limit: number of logs (default: 100)

Examples:
  /cxcli query 2h 50
  /cxcli errors 1h
  /cxcli dedupe 30m
  /cxcli group 1h
  /cxcli query "source logs | filter $d ~~ 'timeout'" 30m
  /cxcli trace "695744b6..." 2h
  /cxcli count 1h
  /cxcli docs
```

### query
Query logs for a service or run a custom DataPrime query. Results go to **stdout** as NDJSON.

**If the argument looks like a service name** (no spaces, no pipes): `[service] [time] [limit]`

1. Parse service (default `cashflow-optimizer`), time (default 1h), and convert to ISO dates:
   - START_DATE = now - time
   - END_DATE = now
2. Run:
```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' | limit <limit>" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

**If the argument looks like a DataPrime query** (contains spaces, pipes, or filter keywords): `"<dataprime_query>" [time]`

```bash
cxcli query \
  "<dataprime_query>" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

### errors
ERROR-level log summary for a service.

Arguments: `[service] [time]`

```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' && \$m.severity == 'Error' | limit 2000" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

### dedupe
Dedupe all logs (any severity) by message for pattern analysis. Uses DataPrime `groupby` to collapse duplicates and show counts.

Arguments: `[service] [time]`

```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' | groupby \$d agg count() as _dedupe_count | orderby _dedupe_count desc" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

### group
Severity breakdown for a service. Shows log counts grouped by severity level.

Arguments: `[service] [time]`

```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' | groupby \$m.severity agg count() as log_count" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

### trace
Find logs by Datadog trace ID (for cross-service correlation). Results go to **stdout**.

Arguments: `<trace_id> [time] [limit]`

```bash
cxcli query \
  "source logs | filter \$d ~~ '<trace_id>' | limit <limit>" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

**Use case:** Follow a request across multiple services using the shared `dd.trace_id` field.

### count
Get total count of error logs matching a filter.

Arguments: `[service] [time]`

```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' && \$m.severity == 'Error' | count" \
  -s "<START_DATE>" \
  -e "<END_DATE>"
```

**Note:** Use `| count` - NOT `summarize count()` or `countdistinct` (these don't exist in DataPrime)

### docs
Scrape Coralogix documentation in markdown format.

```bash
cxcli docs scrape
```

This fetches the full Coralogix docs. Use it when you need DataPrime syntax reference or Coralogix API details.

## Time Parsing

Convert user-provided duration to ISO dates using macOS BSD `date`.

**IMPORTANT:** BSD date units are case-sensitive. Hours = `H`, Minutes = `M`, days = `d`.

- `30m` -> `date -u -v-30M '+%Y-%m-%dT%H:%M:%SZ'`
- `1h` -> `date -u -v-1H '+%Y-%m-%dT%H:%M:%SZ'`
- `2h` -> `date -u -v-2H '+%Y-%m-%dT%H:%M:%SZ'`
- `6h` -> `date -u -v-6H '+%Y-%m-%dT%H:%M:%SZ'`
- `1d` -> `date -u -v-1d '+%Y-%m-%dT%H:%M:%SZ'`

Map user input to BSD units: `m` -> `M` (minutes), `h` -> `H` (hours), `d` -> `d` (days).

## Output Format

cxcli outputs **NDJSON** (newline-delimited JSON). Each line is a JSON object:

- First line: `{"queryId":{"queryId":"<uuid>"}}` (always present)
- Subsequent lines: `{"result":{"results":[...]}}` containing log entries
- If no results, only the queryId line appears

Each log entry has:
- `metadata[]` - timestamps, severity, logid
- `labels[]` - subsystemname, applicationname
- `userData` - JSON string containing the log body (attributes, resource info)

To extract readable messages from NDJSON, parse each result line and extract `userData.attributes.message`, `userData.attributes.level`, and `metadata[timestamp]`.

## DataPrime Query Reference

| Filter Type | Syntax | Example |
|-------------|--------|---------|
| By subsystem | `$l.subsystemname == 'name'` | `$l.subsystemname == 'cashflow-optimizer'` |
| Full text (CASE-SENSITIVE!) | `$d ~~ 'text'` | `$d ~~ 'Circuit Breaker'` (exact case!) |
| By severity | `$m.severity == 'LEVEL'` | `$m.severity == 'Error'` |
| By trace ID | `$d ~~ '<trace_id>'` | `$d ~~ '695744b6...'` |
| By DD service | `$d ~~ 'cashflow-optimizer'` | Full-text search for service name |
| Count total | `\| count` | NOT `summarize count()` |
| Limit | `\| limit N` | `\| limit 50` |
| Group by | `\| groupby <field> agg count() as N` | `groupby $m.severity agg count() as log_count` |
| Order by | `\| orderby <field> desc` | `orderby _dedupe_count desc` |

**Severity values** (for `$m.severity`, title case): `Debug`, `Verbose`, `Info`, `Warning`, `Error`, `Critical`

**IMPORTANT:** The `~~` text match operator is **CASE-SENSITIVE**. `'circuit breaker'` will NOT match `'Circuit Breaker'`.

## Notes
- API key from env: `CORALOGIX_API_KEY`
- Default region: `cx498` (SoFi)
- `cxcli query` outputs NDJSON to stdout (synchronous, hot tier)
- `cxcli query --background` submits async query, polls for completion
- The `-s` flag is short for `--start-date`, `-e` for `--end-date`
