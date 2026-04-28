---
description: Query GitLab CI pipelines, jobs, and traces using glab
allowed-tools: Bash(glab:*), Bash(git:*)
argument-hint: <action> [args] - help|pipelines|jobs|trace|diff
---

Query GitLab CI pipeline data, job logs, and MR diffs using glab.

## Working Directory

**All glab commands must run from within a cashflow-optimizer git repo directory.** The `:id` shorthand in `glab api` resolves the project from the current git remote. If run from a non-git directory (e.g., the sidekick toolkit), it will fail with an error.

Before running any command, ensure you are in the right directory:
```bash
cd /Users/foothill/code/cashflow-optimizer
```

Or prefix each command with `cd /Users/foothill/code/cashflow-optimizer && glab ...`

## Argument Parsing

Parse `$ARGUMENTS` to identify:
1. **Action** - First word: `help`, `pipelines`, `jobs`, `trace`, `diff`
2. **Arguments** - Pipeline ID, job ID, URL, or flags depending on the action

If the argument is a URL:
- Contains `/pipelines/` -> extract pipeline ID
- Contains `/jobs/` -> extract job ID

## Actions

### help
Print usage and exit:
```
glab-ci Slash Command Usage:

/glab-ci pipelines [--status=STATUS] [--per-page=N]   List pipelines for current branch
/glab-ci jobs <pipeline-id>                             List jobs (handles parent + child pipelines)
/glab-ci trace <job-id>                                 Fetch and clean a job's log trace
/glab-ci diff                                           Get MR diff for current branch
/glab-ci help                                           Show this help

Examples:
  /glab-ci pipelines
  /glab-ci pipelines --status=failed
  /glab-ci jobs 2361772811
  /glab-ci trace 13341198389
  /glab-ci diff
  /glab-ci jobs https://gitlab.com/sofiinc/advice/cashflow-optimizer/-/pipelines/2361772811
```

### pipelines
List pipelines for the current branch.

Arguments: `[--status=STATUS] [--per-page=N]`

1. Get the current branch:
```bash
git rev-parse --abbrev-ref HEAD
```

2. List pipelines:
```bash
glab ci list --per-page=<N|10> -F json
```

3. Filter results to the current branch. Display: pipeline ID, status, ref, sha (short), duration, created_at, web_url.

If `--status` is provided, also pass it to glab:
```bash
glab ci list --status=<STATUS> --per-page=<N|5> -F json
```

### jobs
List jobs in a pipeline, including child/downstream pipelines.

Arguments: `<pipeline-id>` or `<pipeline-url>`

This project uses **multi-project trigger pipelines**. The parent pipeline contains bridge jobs that create downstream child pipelines. Actual build/test/lint jobs run in child pipelines.

**Step 1: Fetch bridge jobs to find child pipelines**
```bash
glab api "/projects/:id/pipelines/<PIPELINE_ID>/bridges"
```

For each bridge, extract: name, status, `downstream_pipeline.id`.

**Step 2: Fetch jobs from child pipelines**

For each downstream pipeline ID:
```bash
glab api "/projects/:id/pipelines/<CHILD_PIPELINE_ID>/jobs"
```

Record for each job: ID, name, stage, status, duration, failure_reason, allow_failure, web_url.

**Step 3: Also fetch parent pipeline jobs**
```bash
glab api "/projects/:id/pipelines/<PIPELINE_ID>/jobs"
```

**Output**: Display all jobs grouped by pipeline (parent first, then each child), with failed jobs highlighted. Include:
- Job ID, name, stage, status, duration
- For failed jobs: failure_reason
- Note jobs where `allow_failure: true` (these don't block the pipeline)
- Note skipped jobs that were consequences of earlier failures

### trace
Fetch and clean a job's log trace.

Arguments: `<job-id>` or `<job-url>`

1. Fetch the raw trace:
```bash
glab api "/projects/:id/jobs/<JOB_ID>/trace"
```

2. Clean the output by stripping:
   - ANSI escape codes: pattern `\x1b\[[0-9;]*m`
   - GitLab section markers: lines starting with `section_start:` or `section_end:`
   - Timestamp prefixes: pattern `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z`

3. If the trace exceeds 10000 lines, extract only failure context:
   - Search for markers: `FAILED`, `error:`, `Exception`, `Caused by:`, `BUILD FAILED`
   - Take 50 lines before and 10 lines after each marker

4. Display the cleaned trace.

### diff
Get the MR diff for the current branch.

**Step 1: Find the MR**

Try open MRs first, then merged:
```bash
glab mr list --source-branch="$(git rev-parse --abbrev-ref HEAD)" -F json
```

If no open MR found, check merged MRs (use `--merged` / `-M` flag):
```bash
glab mr list --merged --source-branch="$(git rev-parse --abbrev-ref HEAD)" -F json
```

**Step 2: Get the diff**
```bash
glab mr diff <MR_IID>
```

If no MR exists (open or merged), fall back to git diff against the merge base:
```bash
git diff $(git merge-base HEAD origin/main)..HEAD
```

Display: files changed summary, then the full diff.

## Error Handling

- **glab authentication failure**: Report "GitLab authentication failed. Run `glab auth status` to verify your token." and stop.
- **Pipeline not found**: Report "Pipeline <ID> not found." and stop.
- **Job trace too large**: Extract only failure context (search for markers and take surrounding lines).
- **No MR found**: Fall back to git diff and note that no MR was found.

## Notes
- All glab API calls use the `:id` shorthand which resolves to the current project
- Pipeline IDs are numeric; if a URL is provided, extract the numeric ID from the path
- Child pipelines are found via the `/bridges` endpoint, not directly from the parent
- Jobs with `allow_failure: true` do not cause pipeline failure (e.g., `service-maturity-baseline`)
