---
description: "Investigate CI pipeline failures, find root causes, and propose fixes"
model: opus
allowed-tools: Bash(glab:*), Bash(git:*), Bash(unset GRADLE_USER_HOME*), Read, Grep, Glob
argument-hint: "[pipeline-id|job-url] or leave empty for auto-detect"
triggers:
  - "CI failed"
  - "pipeline failed"
  - "build is broken"
  - "fix the pipeline"
  - "why did CI fail"
  - "build broke"
  - "pipeline broke"
---

# Investigate CI Skill

Investigate failed CI pipelines, identify root causes, and propose fixes. Uses the `/glab-ci` command for data fetching and performs analysis locally.

## Help

If `$ARGUMENTS` is `help`, print this usage and stop:

```
Investigate CI - Pipeline failure investigation

Fetches CI pipeline data, correlates failures with code changes,
identifies root cause, and proposes fixes.

Usage:
  /investigate-ci                              Auto-detect latest failed pipeline for current branch
  /investigate-ci <pipeline-id>                Investigate a specific pipeline
  /investigate-ci <pipeline-url>               Investigate from a GitLab URL
  /investigate-ci <job-url>                    Investigate a specific failed job
  /investigate-ci help                         Show this help

Examples:
  /investigate-ci
  /investigate-ci 2361772811
  /investigate-ci https://gitlab.com/sofiinc/advice/cashflow-optimizer/-/pipelines/2361772811
  /investigate-ci https://gitlab.com/sofiinc/advice/cashflow-optimizer/-/jobs/13341198389

What it does:
  1. Resolves target pipeline (auto-detect or from argument)
  2. Discovers failed jobs (navigates parent + child pipelines)
  3. Fetches and parses job logs (classifies failure type)
  4. Correlates errors with code changes (MR diff)
  5. Root cause analysis with confidence rating
  6. Proposes concrete fix with verification command

Failure types detected:
  Compilation errors, test failures, spotless/lint violations,
  dependency resolution, infrastructure/runner, OOM, timeouts
```

## Argument Parsing

Parse `$ARGUMENTS` (or the natural language trigger) to determine the investigation target:

1. **No arguments**: Auto-detect the latest failed pipeline for the current branch
2. **Numeric value** (e.g., `12099`): Treat as a pipeline ID
3. **URL containing `/pipelines/`**: Extract pipeline ID from the URL
4. **URL containing `/jobs/`**: Extract job ID and investigate that specific job

## Working Directory

**All glab commands must run from within a cashflow-optimizer git repo directory.** The `:id` shorthand resolves from the current git remote; running from a non-git directory (like the sidekick toolkit at `/Users/foothill/code/sidekick`) will fail.

Before any glab command, cd to the repo:
```bash
cd /Users/foothill/code/cashflow-optimizer
```

## Phase 1: Resolve Target Pipeline

### Auto-detect (no arguments)

Get the current branch name, then use `/glab-ci` to find the latest failed pipeline:

```
/glab-ci pipelines --status=failed
```

Filter results to the current branch (`git rev-parse --abbrev-ref HEAD`). If no failed pipeline exists for the current branch, check for pipelines with any non-success status (running, pending) and report it.

### From argument

If the argument is a pipeline ID or URL, fetch pipeline metadata:

```bash
glab api "/projects/:id/pipelines/<PIPELINE_ID>"
```

Extract and display: status, ref (branch), sha, commit message, web_url, created_at, duration.

## Phase 2: Discover Failed Jobs

Use `/glab-ci` to navigate the pipeline hierarchy:

```
/glab-ci jobs <PIPELINE_ID>
```

This handles parent pipelines with bridge jobs that create downstream child pipelines. Focus on jobs where `status` is `"failed"`.

### Edge cases
- If all bridges are "success" but parent is "failed", check for `allow_failure: false` jobs that failed
- If a job was **skipped** because a preceding job failed (e.g., test skipped because compile failed), note it as a consequence, not a separate root cause
- Ignore jobs where `allow_failure: true` (like `service-maturity-baseline`)
- If no actionable failures are found, report what was observed and stop

## Phase 3: Fetch and Parse Job Logs

For each failed job, fetch the log trace:

```
/glab-ci trace <JOB_ID>
```

The `/glab-ci` command handles cleaning (ANSI codes, section markers, timestamps). Now **classify the failure type**.

Check patterns in this order (first match wins):

**1. Kotlin/Java Compilation Error**
- Pattern: `e: file:///builds/sofiinc/advice/cashflow-optimizer/<path>:<line>:<col> <message>`
- Also: `compileKotlin FAILED`, `compileTestKotlin FAILED`
- Extract: file path (strip `/builds/sofiinc/advice/cashflow-optimizer/` prefix to get repo-relative path), line number, column, error message

**2. Test Failure (JUnit)**
- Pattern: `ClassName > test method name() FAILED`
- Also: `X tests completed, Y failed`, `There were failing tests`
- Extract: class name, method name, assertion error, expected vs actual values

**3. Spotless/Lint Violation**
- Pattern: `spotlessKotlinCheck FAILED`, `The following files had format violations:`
- Extract: list of files with violations and the diff showing the formatting issue

**4. Dependency Resolution Failure**
- Pattern: `Could not resolve`, `Could not find`, `Failed to resolve dependencies`
- Extract: dependency coordinates, which repository was searched

**5. Infrastructure/Runner Failure**
- Pattern: `Job failed (system failure)`, `stuck or timeout`, `Runner system failure`
- Pattern: `ERROR: Job failed: command terminated` without a preceding Gradle failure

**6. Out of Memory**
- Pattern: `java.lang.OutOfMemoryError`, `GC overhead limit exceeded`, `Metaspace`

**7. Timeout**
- Pattern: `Job exceeded maximum execution time`

### Extract relevant context
- The last 50 lines before `BUILD FAILED` or the failure marker
- All lines containing `FAILED`, `error:`, `Exception`, or stack traces (`at `, `Caused by:`)
- For compilation errors, all lines starting with `e: `

## Phase 4: Correlate with Code Changes

### 4a. Get the diff

Use `/glab-ci` to get the MR diff:

```
/glab-ci diff
```

### 4b. Cross-reference errors with changed files

- **Compilation errors**: Check if the error file was modified in the diff, or if it references symbols from modified files
- **Test failures**: Check if the failing test class or the code under test was modified
- **Spotless violations**: Check if the violating file was modified in the MR

### 4c. Read implicated source files

For each file implicated in the failure, use Read to examine the relevant lines with surrounding context (10 lines before and after).

If the error references a missing symbol (e.g., "Unresolved reference: foo"):
- Use Grep to search the codebase for where `foo` is defined or was recently used
- Check if it was renamed, moved, or deleted in the MR diff

For test failures, also read the test file and the production class being tested.

## Phase 5: Root Cause Analysis

Synthesize findings from Phases 3 and 4. For each failed job, determine:

1. **What failed**: The specific task, test, or check
2. **Why it failed**: The underlying cause connected to code changes
3. **Confidence**: High (direct code-to-error link), Medium (probable), Low (unclear, may be flaky/infra)

### Common root cause patterns for this project

- **Compilation error in test code**: Test references a property or method renamed/removed in production code
- **Compilation error in main code**: Import ordering, missing dependencies, type mismatches from OpenAPI codegen changes
- **Spotless violation**: Import ordering (Kotlin convention violations), trailing commas, whitespace. Caused by new imports breaking required order
- **Test assertion failure**: Changed business logic but test expectations not updated
- **Flaky test**: Same test passes on retry or other pipelines. Check recent pipeline history:
  ```bash
  glab ci list --per-page=10 -F json
  ```
- **Dependency resolution**: Newly published internal library version incompatible or not yet available

## Phase 6: Propose Fix

Based on root cause analysis, propose concrete fixes. **Do not apply fixes automatically.** Present them for the developer to review.

### For compilation errors
- Show the exact file path and line number
- Show the current code at that location
- Explain what the code is trying to reference and what is missing
- Propose the specific code change (before/after snippets)
- Suggest verifying:
  ```bash
  unset GRADLE_USER_HOME && ./gradlew :service:compileTestKotlin 2>&1 | tail -30
  ```

### For test failures
- Show the test method that failed
- Show the assertion that failed and expected vs actual values
- Show the production code the test exercises
- Propose updated test code

### For spotless violations
- Show which files need formatting
- Propose running the auto-fix:
  ```bash
  unset GRADLE_USER_HOME && ./gradlew :service:spotlessApply
  ```

### For dependency issues
- Show the dependency that failed to resolve
- Check if the version exists
- Propose updating the version

### For infrastructure/flaky failures
- Recommend retrying:
  ```bash
  glab ci retry <PIPELINE_ID>
  ```
- Note the flaky test for tracking

## Output Format

Present the investigation results in this exact structure (plain text headers, not markdown `##`):

```
CI Failure Investigation Report
Pipeline: #<IID> (<pipeline-id>)
Branch: <ref>
Status: <status>
Commit: <short-sha> - <commit-title>
User: <author name>
Duration: <duration>s
Link: <web_url>

Failed Jobs:

| Job | Stage | Pipeline | Duration | Link |
|-----|-------|----------|----------|------|
| <name> | <stage> | child (<child-pipeline-id>) or parent | <duration>s or "skipped" | [job](<web_url>) or (consequence of <job> failure) |

Failure Classification
Type: <Compilation Error (main code) | Compilation Error (test code) | Test Failure | Spotless Violation | Dependency Issue | Infrastructure | Timeout | OOM>
Severity: <Blocking (must fix) | Non-blocking (allow_failure) | Flaky (intermittent)>

Error Details

<Relevant error output, cleaned of ANSI codes and timestamps>

Root Cause
<Full narrative explanation: what failed, why, which commit introduced it, what the relationship is between the changed code and the error. Be specific - name the class, property, or method involved.>

Changed files involved:
- `path/to/file.kt` (line X) - <what changed and why it caused the failure>

Confidence: <High | Medium | Low> (<reason>)

Proposed Fix
<Specific, actionable explanation of the change needed>

// Before (line N):
<current code>

// After:
<fixed code>

Verification command:
<Gradle command to verify the fix locally>

Resolution Status
<Whether this is already fixed on the branch/main, or still needs fixing. If already fixed, cite the commit SHA and title.>
```

Include skipped jobs in the Failed Jobs table only when they were skipped as a direct consequence of a real failure - mark their duration as "skipped" and the link column as "(consequence of `<job>` failure)". Do not list `allow_failure: true` jobs.

If multiple independent jobs failed, present a separate Root Cause + Proposed Fix block for each. Group skipped consequences under the job that caused them.

## Error Handling

1. **No failed pipelines found**: Report "No failed pipelines found for branch <branch>. Last pipeline status: <status>." and stop.
2. **Pipeline still running**: Report "Pipeline #<IID> is still running (<duration> elapsed). Wait for completion or provide a specific job ID." and stop.
3. **glab authentication failure**: Report "GitLab authentication failed. Run `glab auth status` to verify your token." and stop.
4. **Multiple independent failures**: Investigate each one separately. Present all findings in the report.
