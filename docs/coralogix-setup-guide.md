# Coralogix CLI (cxcli) Setup Guide

Guide for installing SoFi's Coralogix CLI and integrating it with sidekick for production log queries.

## Overview

**cxcli** is SoFi's custom Coralogix CLI for querying and exporting production logs. It's pre-configured for SoFi's custom region (`cx498`) and uses the DataPrime gRPC API.

Key features:
- `logs query` - Interactive queries to stdout (hot tier, ideal for Claude sessions)
- `export` - Bulk export to files (archive tier)
- `--compact` output: 4 fields (message, service, severity, timestamp)
- `--dedupe` for pattern analysis with occurrence counts
- `--group-by` for aggregation (e.g., severity breakdown)
- Built-in docs (`cxcli docs metrics/dataprime/datetime`)

## Prerequisites

- VPN connection to SoFi corporate network
- Coralogix API key (from Coralogix UI -> Settings -> API Keys)
- macOS or Linux (arm64/amd64)

## Part 1: Install cxcli

### Option A: Install from Artifactory (Recommended)

```bash
# Install latest version (requires VPN)
curl -sSfL https://repository.sofi.com/artifactory/bins-release-local/cxcli/install.sh | sh

# Or install a specific version
curl -sSfL https://repository.sofi.com/artifactory/bins-release-local/cxcli/install.sh | VERSION=0.0.0 sh
```

The binary is installed to `~/.local/bin/cxcli`.

### Option B: Install from Source

```bash
git clone git@gitlab.com:sofiinc/observability/cxcli.git && cd cxcli
go install
```

### Verify Installation

```bash
cxcli --version
# Output: cxcli version X.X.X (commit)
```

## Part 2: Configure API Key

### Get Your API Key

Follow the SoFi Confluence guide:
[How-To: Coralogix MCP API Access](https://sofiinc.atlassian.net/wiki/spaces/PE/pages/4584701976/How-To+Coralogix+MCP+API+Access)

Quick summary:
1. Go to Coralogix UI (https://sofi.coralogix.us)
2. Navigate to **Settings -> API Keys**
3. Create or copy an existing API key
   - Key format: `cxup_XXXXXXXXXXXXXXXXXXXX`
   - Ensure the key has **query permissions** for archive tier access

### Set Environment Variable

Add to your `~/.zshrc`:

```bash
export CORALOGIX_API_KEY="cxup_YOUR_API_KEY_HERE"
```

Reload:
```bash
source ~/.zshrc
```

## Part 3: Verify with Sidekick

Once cxcli is configured, test from a Claude Code session with sidekick loaded:

```bash
# From any cashflow-optimizer worktree
claude --add-dir ~/code/sidekick
```

Then try:
```
/cxcli help
/cxcli errors cashflow-optimizer 1h
/cxcli group cashflow-optimizer 1h
```

## Troubleshooting

### "No logs exported"
- Check the time range - logs may not exist for that period
- Verify the subsystem name is correct (case-sensitive)
- Try a broader query without filters first

### "Query submission failed"
- Verify your API key is valid and has query permissions
- Check VPN connection
- Ensure DataPrime syntax is correct (escape `$` in shell)

### "cxcli: command not found"
- Ensure `~/.local/bin` is in your PATH
- Run `source ~/.zshrc` to reload shell config

### Finding Service Names
Query without filter to see available services:
```bash
cxcli export --query "source logs | limit 10" -s "$(date -u -v-1H '+%Y-%m-%dT%H:%M:%SZ')" -e "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" --summary
```
Check `resource.attributes.service.name` in the output.

## Resources

- **cxcli source**: https://gitlab.com/sofiinc/observability/cxcli
- **DataPrime docs**: https://coralogix.com/docs/dataprime-cheat-sheet/
- **Coralogix UI**: https://sofi.coralogix.us
