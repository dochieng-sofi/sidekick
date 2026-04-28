---
description: "Diagnose production issues: pull logs, trace through code, identify root cause, and suggest fixes"
model: opus
allowed-tools: Bash(cxcli:*), Read, Grep, Glob
argument-hint: "[error|party <id>|trace <id>|description] [service] [time]"
triggers:
  - "diagnose"
  - "root cause"
  - "investigate error"
  - "what's causing"
  - "check production logs"
  - "trace this request"
  - "why is this failing"
  - "debug this error"
  - "fix this error"
---

# Diagnose Skill

Diagnose production issues by pulling Coralogix logs, tracing them through the codebase, identifying root causes, and suggesting fixes with reproduction steps.

## Help

If `$ARGUMENTS` is `help` or empty, print this usage and stop:

```
Diagnose - Production issue investigation

Pulls Coralogix logs, traces through the codebase, identifies root cause,
and suggests fixes with reproduction steps.

Usage:
  /diagnose "error description" [service] [time]
  /diagnose party <party_id> [time]
  /diagnose trace <trace_id> [time]
  /diagnose help

Arguments:
  error description   Text to search for in logs (error messages, keywords, exception names)
  party <party_id>    Look up logs for a specific user/member by party ID
  trace <trace_id>    Follow a specific request by Datadog trace ID
  service             Service name (default: cashflow-optimizer)
  time                Time window: 30m, 1h, 2h, 6h, 1d (default: 1h)

Examples:
  /diagnose "NullPointerException in TopicService" 2h
  /diagnose party 17074861 1h
  /diagnose trace 695744b6a3e2f1d0 1h
  /diagnose "timeout errors" sofi-bff 30m
  /diagnose "latency spike in account creation"

What it does:
  1. Queries Coralogix logs (deduped errors + severity breakdown)
  2. Analyzes error patterns and extracts identifiers
  3. Traces log messages to source code locations
  4. Identifies root cause with confidence rating
  5. Suggests fix, reproduction steps, and unit test skeleton
```

## Argument Parsing

Parse `$ARGUMENTS` (or the natural language trigger) to extract:

1. **Party ID** - If the input contains the word "party" followed by a numeric ID, treat it as a party/user ID lookup
2. **Trace ID** - If the input contains a hex string (16+ chars) or the word "trace", treat it as a trace ID query
3. **Service name** - If a known service name is mentioned, use it. Otherwise default to `cashflow-optimizer`
4. **Time range** - Look for patterns like `1h`, `2h`, `30m`, `1d`. Default: `1h`
5. **Keywords** - Any remaining text becomes search keywords for log filtering
6. **Error class** - If an exception class name is mentioned (e.g., `NullPointerException`, `TimeoutException`), note it for targeted searching

## Phase 1: Parse & Query

### 1a. Determine query strategy

Based on the parsed input, choose the approach:

- **Party ID provided**: Query all logs for that user/member across the service
- **Trace ID provided**: Query by trace to follow a specific request
- **Error class provided**: Query errors filtered by the class name
- **Keywords provided**: Query with full-text search
- **No specifics**: Start with deduped error summary

### 1b. Run cxcli queries

Always run at least two queries for context:

**Primary query** (depends on strategy):

**Time conversion:** Map user time specs to BSD date units (case-sensitive): `m` -> `M` (minutes), `h` -> `H` (hours), `d` -> `d` (days). Example: `1h` -> `-v-1H`, `30m` -> `-v-30M`, `1d` -> `-v-1d`.

For party ID:
```bash
START=$(date -u -v-<TIME> '+%Y-%m-%dT%H:%M:%SZ')
END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' && \$d ~~ '<party_id>' | limit 200" \
  -s "$START" -e "$END"
```

For trace ID:
```bash
START=$(date -u -v-<TIME> '+%Y-%m-%dT%H:%M:%SZ')
END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
cxcli query \
  "source logs | filter \$d ~~ '<trace_id>' | limit 200" \
  -s "$START" -e "$END"
```

For error investigation:
```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' && \$m.severity == 'Error' | limit 2000" \
  -s "$START" -e "$END"
```

For keyword search:
```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' && \$d ~~ '<keyword>' | limit 200" \
  -s "$START" -e "$END"
```

**Context query** (always run):
```bash
cxcli query \
  "source logs | filter \$l.subsystemname == '<service>' | groupby \$m.severity agg count() as log_count" \
  -s "$START" -e "$END"
```

**Output format:** cxcli outputs NDJSON (newline-delimited JSON). First line is `{"queryId":...}`, subsequent lines contain `{"result":{"results":[...]}}`. Parse each result to extract `userData.attributes.message`, `userData.attributes.level`, and `metadata[timestamp]`.

### 1c. Display summary

Before proceeding, display what was found:
- Number of log entries retrieved
- Severity breakdown
- Top error patterns (if deduped)
- Time range covered

## Phase 2: Analyze Logs

Analyze the retrieved logs to identify:

1. **Error patterns** - Group similar errors, note deduped counts
2. **Stack traces** - Extract exception class names, messages, and key stack frames
3. **Severity progression** - WARN entries before ERROR entries may indicate escalation
4. **Timestamp clustering** - Burst (sudden spike) vs steady (ongoing issue)
5. **Identifiers** - Extract:
   - User IDs (patterns: `userId=`, `user_id`, `memberId`)
   - Trace IDs (`dd.trace_id`, `traceId`)
   - Entity IDs (`actionId`, `topicId`, `accountId`)
   - Request context (endpoints, HTTP methods, status codes)

If the initial query returned too few results, broaden the search:
- Increase time window
- Remove keyword filters
- Try different severity levels

## Phase 3: Trace Through Code

For each significant error or log message found:

### 3a. Find the source location

Search for the log message string in the service source:
```
Grep for the message text in service/src/main/kotlin/
```

Tips for matching:
- Log messages often use string interpolation: `"Error for userId=$userId"` - search for the static part
- Logger calls use: `log.info(...)`, `log.error(...)`, `log.warn(...)`
- The project uses `logger()` extension from `utils/Logger.kt`

### 3b. Read the code path

Once the source file and line are found:
1. Read the containing function/method
2. Identify the class and its role (controller, service, repository, client, job)
3. Trace the call chain:
   - **Controller** (`web/controller/`) - Entry point, request validation
   - **Service** (`service/`) - Business logic, orchestration
   - **Repository** (`repository/`) - Database operations
   - **Client** (`client/`) - External service calls
   - **Queue** (`queue/`) - Message handlers (Kafka, ActiveMQ)
   - **Jobs** (`jobs/`) - Scheduled tasks

4. For each hop in the chain, read the relevant code to understand:
   - What data flows through
   - Where null checks or validations exist (or are missing)
   - Error handling: try/catch blocks, exception types thrown
   - Retry logic, circuit breakers, timeouts

### 3c. Map the error chain

Connect the dots from logs to code:
- Log entry with ERROR -> source file:line -> function -> what condition triggered it
- If multiple related logs, map the sequence through the code path

## Phase 4: Root Cause Analysis

Based on the evidence from Phases 2 and 3:

1. **Identify the triggering condition** - What specific data state, timing, or external response caused the issue?

2. **Check for common patterns**:
   - Null or missing data from an upstream service
   - Timeout from an external dependency
   - Database constraint violation
   - Race condition between concurrent requests
   - Configuration mismatch between environments
   - Missing error handling for an edge case
   - Stale cache or stale data

3. **Rate confidence**:
   - **High** - Direct code-to-error link with clear triggering condition
   - **Medium** - Probable link but some assumptions made
   - **Low** - Insufficient data, needs more investigation

4. **Note what's still unclear** - What additional data would help confirm the root cause?

## Phase 5: Report

Use the appropriate format based on the query type.

### Party ID or "what did this user do" queries

```
Activity Report for Party <party_id>
Service: <service>
Time Window: <start> to <end> (last <duration>)
Total Log Entries: <N> (Info: <N>, Warning: <N>, Error: <N>)

User Profile
Detail          Value
<key detail>    <value>
...

Known accounts:
- <account type> (<account name>) - <short-uuid>

Activity Timeline (UTC)
Session <N> - <start time> to <end time> (<trigger description>)

Triggered by: <triggering class/queue/event>. <Brief explanation of what kind of activity this is - background job, direct user interaction, etc.>

<Bulleted narrative of what happened in this session, in chronological order:>
- <action at timestamp>
- WARN: <any warnings encountered>
- <evaluation outcomes - money movements built, foundations built, etc.>
- <downstream events posted - Kafka, CDP, etc.>

<Repeat for each session>

Key Observations
<Bullet each significant finding - no errors, duplicate processing, transient data gaps, account/eligibility patterns, anomalies. Be specific: name the class, queue, account, or condition.>

Want me to dig deeper into any of these - for example, <mention 1-2 specific threads worth investigating>?
```

Extract for the User Profile table: feature flags seen in logs, device IDs, account UUIDs with their types, account counts from log messages like "X eligible accounts". For known accounts, truncate UUIDs to first 8 and last 6 chars.

Group logs into sessions by time proximity (< 5 min gap = same session). Name sessions by what triggered them (queue name, class name, or event). Distinguish background jobs from user-initiated interactions.

### Error investigation, keyword, or trace queries

```
Debug Investigation Report
Service: <service>
Time Window: <start> to <end> (UTC)
Query: <what was searched>

Log Summary
- Total entries: <N>
- Errors: <N> | Warnings: <N> | Info: <N>
- Top error patterns:
  1. <pattern> (count: <N>)
  2. <pattern> (count: <N>)

Error Details
<Key log entries with timestamps, formatted for readability>

Code Trace
- Source: <file>:<line> - <function name>
- Code path: <controller> -> <service> -> <repository/client>
- What the code does: <explanation>
- What went wrong: <specific condition>

Root Cause
<Clear explanation connecting logs to code to the triggering condition>

Confidence: <High | Medium | Low> (<reason>)

Reproduction Steps
1. Preconditions: <data state, feature flags, timing needed>
2. API call: <curl/httpie example to trigger the issue>
3. Expected result: <what should happen vs what does happen>

Suggested Unit Test
<Kotlin test skeleton using JUnit 5 + mockito-kotlin that captures the failure condition>
```

## Error Handling

- **No logs found**: Suggest broadening the time window or checking the service name. Try without keyword filters.
- **Too many logs**: Add more specific filters (severity, keywords). Use DataPrime `groupby` to collapse duplicates.
- **Can't find source**: The log message may come from a library or framework. Check dependencies.
- **cxcli not found**: Check if `~/.local/bin/cxcli` exists. If not, refer user to `sidekick/docs/coralogix-setup-guide.md`.
- **cxcli authentication failure**: Report "Coralogix API key not configured." Check both `~/.zshrc` and `~/.bashrc` for `CORALOGIX_API_KEY`. Users may use different shells.
