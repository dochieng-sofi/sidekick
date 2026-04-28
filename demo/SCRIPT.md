# Demo Script: AI-Powered Engineering Workflow

**Audience:** Cashflow-optimizer team
**Duration:** ~15 minutes
**Format:** Live terminal + editor walkthrough

Open two windows before starting:
- Terminal in `~/code/cfo-account-linking`
- Editor with `~/.claude/CLAUDE.md` ready to view


## 1. Global CLAUDE.md (2 min)

**Framing:** "Claude reads this file at the start of every conversation, across every project. It's your standing orders."

Open `~/.claude/CLAUDE.md` and walk through:

- **Communication section** - "Always ask before acting. This means Claude proposes a plan before touching anything. No surprises."
- **Testing section** - "JUnit 5, mockito-kotlin, and the Gradle workaround. Claude knows this for every project, always."
- **Git section** - "Never commit without approval, never push --no-verify, never create worktrees on my behalf. Specific hard rules."
- **MR Template** - "The entire team template is embedded. Claude fills it out correctly every time, including reviewers."
- **Project Context** - "The tech stack is here. Even if I open a blank project, Claude knows it's Spring Boot + Kotlin + Gradle."

**Key point:** This is a one-time setup that makes every future conversation smarter. You write it once.


## 2. Per-project CLAUDE.md (2 min)

**Framing:** "Global CLAUDE.md covers your preferences. The project CLAUDE.md covers what Claude can't know from code alone."

Open `~/code/sidekick/CLAUDE.md` and show:

- **Service Context block** - "Coralogix subsystem name, Datadog tag, trace correlation field. Claude uses these when querying logs."
- **Key Dependencies table** - "Claude knows what Aggregation Service, Funds Transfer, etc. do. It uses this when tracing errors."
- **Debugging Methodology** - "A prescriptive 5-step process. Claude follows this whenever I ask it to investigate something."
- **Quick Reference table** - "Natural language on the left, exact invocation on the right. Claude knows the mapping."

**Key point:** You're giving Claude institutional knowledge it would otherwise have to ask you for every time.


## 3. CLAUDE.local.md - per-worktree context (2 min)

**Framing:** "Each feature branch has its own context - a JIRA ticket, a design doc, constraints specific to that work. CLAUDE.local.md puts that in Claude's hands without polluting the global config."

In the terminal (in `~/code/cfo-account-linking`):

```bash
cat CLAUDE.local.md
```

If it doesn't exist, create it live:

```bash
cat > CLAUDE.local.md << 'EOF'
# cfo-account-linking

JIRA: SOFI-XXXX
Branch: cfo-account-linking

## Context
Adds account linking cooldown logic to prevent rapid re-linking after a failed link attempt.

## Constraints
- Do not modify the AccountLinkingService interface - it's shared with downstream consumers.
- Cooldown duration is configured via ExperimentationService, not hardcoded.

## Related
- Design doc: [link]
- Depends on: Account Gateway client changes (separate MR)
EOF
```

**Talk through it:** "Now Claude knows the ticket, the constraints, and the dependencies for this branch. I don't have to re-explain it every session."

**Key point:** CLAUDE.local.md is gitignored by default - it's personal context, not team context.


## 4. Sidekick in action (5 min)

**Framing:** "Sidekick extends Claude with tools and skills specific to our service. Let me show you what's inside."

```bash
ls ~/code/sidekick/.claude/
# skills/  commands/  settings.local.json

ls ~/code/sidekick/.claude/skills/
# diagnose/  investigate-ci/

ls ~/code/sidekick/.claude/commands/
# cxcli.md  glab-ci.md
```

Explain the structure: "Skills are auto-triggered by natural language. Commands are explicit slash commands."

Now open a new Claude session with sidekick loaded:

```bash
cd ~/code/cfo-account-linking
claude --add-dir ~/code/sidekick
```

Type this in Claude:

> "CI failed on the invest-onboarding pipeline - can you investigate?"

Watch `investigate-ci` skill activate. Walk through what it does:
- Calls `glab` to find the failed pipeline
- Fetches job logs with `glab ci trace`
- Reads the MR diff to correlate failures with code changes
- Proposes a concrete fix

**Alternatively** (if CI is green): use the diagnose skill:

> "There are errors in production for the last 2 hours, can you investigate?"

**Key point:** You don't invoke skills manually. You describe the problem in plain English and Claude selects the right tool.

Show the `settings.local.json` permissions - "Claude only has permission to run cxcli, glab, and git. It can't touch anything else."


## 5. Making sidekick accessible (2 min)

**Framing:** "Sidekick isn't on GitLab yet - it's been living on my machine. But it's built to be shared."

Show the README:

```bash
cat ~/code/sidekick/README.md
```

Run the setup script:

```bash
cd ~/code/sidekick
bash setup.sh
```

Walk through what it checks: cxcli installed, CORALOGIX_API_KEY set, prints the alias to add.

**The plan for sharing:**
- Push sidekick to GitLab under our team namespace
- Anyone clones it and runs `setup.sh`
- One line to add to your shell profile: `alias claude-cfo='claude --add-dir ~/code/sidekick'`
- Done - every Claude session for cashflow-optimizer gets the full toolkit

**Key point:** The setup is a one-time 5-minute install. After that, sidekick is always there.


## 6. Worktrees (2 min)

**Framing:** "I work on multiple features at the same time without ever stashing or context-switching branches."

```bash
ls ~/code/
```

Show all the worktrees - each directory is a separate git branch checked out independently:

```
cfo-account-linking/       # feature branch: account linking cooldown
invest-onboarding-topic-journey/   # feature branch: topic journey
cfo-ci-smoke-tests/        # feature branch: smoke tests
cashflow-optimizer/        # main branch
...
```

"Each of these is a full working tree - its own build cache, its own editor window, its own Claude session."

```bash
# In one terminal:
cd ~/code/cfo-account-linking && claude --add-dir ~/code/sidekick

# In another terminal:
cd ~/code/invest-onboarding-topic-journey && claude --add-dir ~/code/sidekick
```

**Key point:** While Claude is running tests on one branch, I'm writing code on another. No waiting, no context loss.

Show how to create a worktree (git command only - never use Claude for this):

```bash
git -C ~/code/cashflow-optimizer worktree add ~/code/my-new-feature my-feature-branch
```


## Wrap-up (30 sec)

"To recap - five things you can set up today:"
1. Write a global CLAUDE.md with your preferences and the tech stack
2. Use CLAUDE.local.md in each branch for feature context
3. Clone sidekick and run setup.sh
4. Use `claude --add-dir ~/code/sidekick` to get the full toolkit
5. Try worktrees for your next feature branch

"Happy to pair on any of these."
