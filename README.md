# Sidekick

AI debugging toolkit for the cashflow-optimizer team. Provides Coralogix log investigation, CI failure analysis, production debugging, and repeatable Braintrust eval workflows through Codex and Claude-compatible skills.

## Prerequisites

- [ ] Claude Code CLI installed
- [ ] VPN connected to SoFi corporate network
- [ ] `cxcli` installed (see [Coralogix Setup Guide](docs/coralogix-setup-guide.md))
- [ ] `glab` CLI authenticated (`glab auth status`)
- [ ] `CORALOGIX_API_KEY` environment variable set

## Setup

### 1. Enable additional directory CLAUDE.md loading

Add to your `~/.zshrc`:

```bash
export CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1
```

Reload: `source ~/.zshrc`

### 2. Launch an agent with sidekick

From any cashflow-optimizer worktree:

```bash
claude --add-dir ~/code/sidekick
```

For Codex:

```bash
Codex --add-dir ~/code/sidekick
```

This loads sidekick guidance and skills while keeping your target repo as the working directory, so code search and edits still happen in the repo you opened.

### 3. Verify

```bash
# Verify cxcli
cxcli --version

# Verify glab
glab auth status

# Verify CORALOGIX_API_KEY
echo $CORALOGIX_API_KEY | head -c 10
```

## What's Included

### Commands (tool wrappers)

| Command | Tool | Usage |
|---------|------|-------|
| `/cxcli` | Coralogix CLI | `/cxcli errors cashflow-optimizer 2h` |
| `/glab-ci` | GitLab CI | `/glab-ci pipelines --status=failed` |

### Skills (investigation agents)

| Skill | Triggers on | What it does |
|-------|-------------|-------------|
| `diagnose` | "debug this", "root cause", "investigate error" | Queries logs, traces through code, identifies root cause |
| `investigate-ci` | "CI failed", "pipeline broke", "build broken" | Fetches CI data, correlates with code changes, proposes fixes |
| `eval-braintrust` | "run guardrail evals", "compare guardrail runs", "eval report" | Runs single or repeated Braintrust evals, saves artifacts, aggregates repeated runs, and compares batches |

## Quick Start Examples

```
# Natural language (skills auto-trigger)
"debug the NullPointerException in TopicService from the last 2 hours"
"why did CI fail?"
"trace request 695744b6 through the system"

# Explicit commands
/cxcli errors cashflow-optimizer 1h
/cxcli trace 695744b6... 2h
/glab-ci trace 13341198389
/investigate-ci 2361772811
```

## Eval Braintrust Skill

Use `eval-braintrust` when you want a repeatable eval workflow rather than manually launching runs, finding Braintrust experiments, fetching events, and combining results by hand.

### Required local setup

1. Clone Sidekick and make sure you have an `openai-member-agent` checkout:

```bash
git clone git@github.com:dochieng-sofi/sidekick.git ~/code/sidekick
```

Place or clone `openai-member-agent` at `~/code/openai-member-agent`, or set `OPENAI_MEMBER_AGENT_ROOT` to wherever your checkout already lives.

2. Configure where the skill should find `openai-member-agent`:

```bash
export OPENAI_MEMBER_AGENT_ROOT=~/code/openai-member-agent
```

3. Configure the Python used for post-processing scripts when needed:

```bash
export EVAL_BRAINTRUST_PYTHON=~/.pyenv/versions/3.12.0/bin/python3
```

If that variable is not set, the batch runner tries `~/.pyenv/versions/3.12.0/bin/python3`, then falls back to `python3` on `PATH`.

4. Ensure the target repo has the required Braintrust/OpenAI environment variables in its `.env`, especially:

```text
BRAINTRUST_API_KEY
OPENAI_API_KEY
```

5. Start the Sierra mock if the selected eval flow needs it:

```bash
cd "$OPENAI_MEMBER_AGENT_ROOT/sierra-mock-clone/api/server"
node dist/index.js
```

### Shareable pre/post workflow

Run the baseline sample set:

```text
/eval-braintrust batch \
  --phase pre \
  --runs 5 \
  --parallel 5 \
  --tag guardrails \
  --provider super \
  --project "OpenAI POC" \
  --output-dir /tmp/guardrails-pre
```

After making or switching to the code change, run the comparison sample set:

```text
/eval-braintrust batch \
  --phase post \
  --runs 5 \
  --parallel 5 \
  --tag guardrails \
  --provider super \
  --project "OpenAI POC" \
  --output-dir /tmp/guardrails-post
```

Compare the combined results:

```text
/eval-braintrust compare-batches \
  /tmp/guardrails-pre/aggregate.json \
  /tmp/guardrails-post/aggregate.json
```

### Current-branch sampling only

Use `current` when you want repeated sampling of the branch that is already checked out, without framing it as a pre/post comparison:

```text
/eval-braintrust batch \
  --phase current \
  --runs 3 \
  --parallel 3 \
  --tag guardrails \
  --provider super \
  --project "OpenAI POC" \
  --output-dir /tmp/guardrails-current
```

### Important flags

| Flag | Meaning |
|------|---------|
| `--phase pre|post|current` | Labels the purpose of the batch |
| `--runs N` | Number of eval runs to launch |
| `--parallel N` | Max child runs to execute concurrently |
| `--tag guardrails|all` | Use `all` for no tag filter |
| `--provider super|openai` | Eval provider |
| `--project NAME` | Braintrust project to resolve experiments against |
| `--project-root PATH` | Override the `openai-member-agent` checkout path |
| `--python-bin PATH` | Override the Python used by shipped post-processing scripts |
| `--output-dir PATH` | Where manifests, logs, fetched events, baselines, and aggregates are written |

### Outputs

Each batch writes:

| Path | Purpose |
|------|---------|
| `manifest.json` | Run metadata, branch/SHA, output paths, and per-run status |
| `aggregate.json` | Combined batch statistics across successful runs |
| `logs/` | One stdout/stderr log file per child eval |
| `events/` | Braintrust event payloads per run |
| `baselines/` | Normalized baseline JSON per run |

The skill docs under `.agents/skills/eval-braintrust/SKILL.md` contain the full operating procedure and edge-case handling.
