# Sidekick

AI debugging toolkit for the cashflow-optimizer team. Provides Coralogix log investigation, CI failure analysis, and production debugging through Claude Code skills and commands.

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

### 2. Launch Claude Code with sidekick

From any cashflow-optimizer worktree:

```bash
claude --add-dir ~/code/sidekick
```

This loads sidekick's CLAUDE.md, skills, and commands while keeping your worktree as the working directory (so code search works).

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
