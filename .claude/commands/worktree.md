---
description: Create a git worktree at the standard worktree directory
allowed-tools: Bash(git:*), Bash(open:*)
argument-hint: <name> [--repo <repo>] [--base <branch>] [--no-fetch] [--no-open]
---

Create a new git worktree at `<repo-root>/.claude/worktrees/<name>`.

## Argument Parsing

Parse `$ARGUMENTS` for the following:

1. **name** - First positional argument (required): the worktree name. This becomes both the directory name and the new branch name.
2. **--repo** - Named flag (optional): the repository directory name under `/Users/foothill/code/`.
3. **--base** - Named flag (optional, default: `main`): the branch to base the new worktree on.
4. **--no-fetch** - Boolean flag (optional): skip the fetch and branch sync step.
5. **--no-open** - Boolean flag (optional): skip opening Cursor after creating the worktree.

Resolve `<repo>` in this order:
1. `--repo` flag (if provided)
2. `$WORKTREE_REPO` environment variable (if set and non-empty)
3. Repo name derived from CWD: run `git rev-parse --show-toplevel`, then extract the last path component
4. Error: "Could not determine repo. Pass --repo or set $WORKTREE_REPO." and stop.

Derived values:
- `<repo-root>` = `/Users/foothill/code/<repo>`
- `<worktree-path>` = `<repo-root>/.claude/worktrees/<name>`

If no name is provided, print usage and stop:
```
Usage: /worktree <name> [--repo <repo>] [--base <branch>] [--no-fetch] [--no-open]

  name              Directory and branch name for the new worktree (required)
  --repo <repo>     Repository directory name under /Users/foothill/code/
                    (resolved from: --repo > $WORKTREE_REPO > git CWD)
  --base <branch>   Branch to base the new worktree on (default: main)
  --no-fetch        Skip fetch and branch sync (use local state as-is)
  --no-open         Skip opening Cursor after creation

Examples:
  /worktree cfo-error
  /worktree cfo-error --base some-other-branch
  /worktree add-feature --repo cfo-ci-smoke-tests
  /worktree add-feature --repo cfo-ci-smoke-tests --base develop
  /worktree quick-fix --no-fetch --no-open
```

## Creating the Worktree

**Step 1: Fetch and sync local base branch** (skip if `--no-fetch`)

```bash
git -C <repo-root> fetch origin <base>
git -C <repo-root> branch -f <base> origin/<base>
```

This ensures the local `<base>` ref is up to date before branching off it.

**Step 2: Create the worktree**

```bash
git -C <repo-root> worktree add \
  <worktree-path> \
  -b <name> \
  origin/<base>
```

**Step 3: Post-creation setup**

First, ensure Poetry and Python are findable (the skill runs in bash, which may not have the user's zsh PATH):
```bash
for p in "$HOME/.local/bin" "/opt/homebrew/bin"; do
  [[ ":$PATH:" != *":$p:"* ]] && [[ -d "$p" ]] && export PATH="$p:$PATH"
done
if [[ -d "$HOME/.pyenv" ]]; then
  export PYENV_ROOT="$HOME/.pyenv"
  [[ ":$PATH:" != *":$PYENV_ROOT/bin:"* ]] && export PATH="$PYENV_ROOT/bin:$PATH"
  [[ ":$PATH:" != *":$PYENV_ROOT/shims:"* ]] && export PATH="$PYENV_ROOT/shims:$PATH"
fi
```

Copy `.env` from the repo root into the worktree (if present):
```bash
if [[ -f "<repo-root>/.env" ]]; then
  cp "<repo-root>/.env" "<worktree-path>/"
fi
```
Print a note if copied (e.g., "Copied .env into worktree"). Skip silently if not present.

Install Python dependencies if the repo uses Poetry (best-effort, don't block on failure).
Use `POETRY_VIRTUALENVS_IN_PROJECT=true` so the virtualenv lives inside the worktree and is cleaned up when the worktree is removed:
```bash
if [[ -f "<worktree-path>/pyproject.toml" ]] && command -v poetry &>/dev/null; then
  _pyenv_python="$(pyenv which python 2>/dev/null || command -v python3)"
  if ! (cd "<worktree-path>" && POETRY_VIRTUALENVS_IN_PROJECT=true poetry env use "$_pyenv_python" && poetry install --no-interaction); then
    echo "WARNING: poetry install failed - run 'poetry install' manually in the worktree"
  fi
fi
```
If `poetry install` fails, print the warning but continue. If `poetry` is not on PATH, skip silently (the repo may not need Poetry).

**Step 4: Confirm success**

Print the full path to the new worktree and the branch it tracks:
```
Worktree created:
  Path:   <worktree-path>
  Branch: <name>
  Base:   origin/<base>
```

**Step 5: Open Cursor in the new worktree** (skip if `--no-open`)

```bash
open -a Cursor <worktree-path>
```

## Error Handling

- **Missing name**: Print usage and stop.
- **Repo not determined**: Print "Could not determine repo. Pass --repo or set $WORKTREE_REPO." and stop.
- **Worktree already exists** (exit code non-zero with "already exists" in output): Report "Worktree '<name>' already exists at that path." and stop.
- **Branch already exists** (exit code non-zero with "already exists" in git output): Try without `-b` to check out the existing branch instead:
  ```bash
  git -C <repo-root> worktree add <worktree-path> <name>
  ```
  If that also fails, report the error and stop.
- **Fetch failure**: Report "Could not fetch origin/<base>. Check the branch name and try again." and stop.
- **Branch sync failure** (`branch -f` fails): Report the git error and stop - do not proceed to create the worktree with a potentially stale base.
