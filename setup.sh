#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
fail() { echo -e "${RED}[missing]${NC} $1"; }

echo ""
echo "Sidekick setup check"
echo "===================="
echo ""

# 1. Claude Code
if command -v claude &>/dev/null; then
  ok "claude is installed ($(claude --version 2>/dev/null || echo 'version unknown'))"
else
  fail "claude not found. Install Claude Code: https://claude.ai/download"
fi

echo ""

# 2. cxcli
if command -v cxcli &>/dev/null; then
  ok "cxcli is installed"
else
  fail "cxcli not found"
  warn "Install from Artifactory or build from source. See docs/coralogix-setup-guide.md for instructions."
fi

echo ""

# 3. CORALOGIX_API_KEY
if [[ -n "${CORALOGIX_API_KEY:-}" ]]; then
  ok "CORALOGIX_API_KEY is set"
else
  fail "CORALOGIX_API_KEY is not set"
  warn "Get your API key from Coralogix > API Keys, then add to your shell profile:"
  echo ""
  echo "    export CORALOGIX_API_KEY='your-key-here'"
  echo ""
fi

# 4. glab
if command -v glab &>/dev/null; then
  ok "glab is installed"
else
  fail "glab not found. Install with: brew install glab"
fi

echo ""

# 5. Print the alias
SIDEKICK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Add this alias to your shell profile (~/.zshrc or ~/.bashrc):"
echo ""
echo "    alias claude-cfo='claude --add-dir ${SIDEKICK_DIR}'"
echo ""
echo "Then reload your shell and use 'claude-cfo' from any cashflow-optimizer worktree."
echo ""
