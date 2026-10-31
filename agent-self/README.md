---
title: README
type: note
permalink: dqverify-repo-20261013/agent-self/readme
---

# agent-self — portable 1:1 snapshot of this agent

A **self-contained, duplicated** bundle that reproduces this exact Claude Code agent on any machine,
independent of the rest of `agent-skills-toolchain`. Even if it duplicates skills/MCP/config that live
elsewhere in the repo — that's intentional, so this folder alone *is* "me."

- **`IDENTITY.md`** — the **1:1 bootstrap PROMPT** (paste it for ~90% of my behaviour with no install) +
  the table of how the harness hooks enforce it. Read this first.
- **`config/`** — the full `~/.claude` harness: `settings.json`/`settings.local.json`, **24 hooks**,
  **64 commands**, **78 rules**, `AGENTS.md`, `CLAUDE.md`, `keybindings.json`, statusline scripts, the
  workspace docs (architecture / self-calibration / curation / capability program), `MEMORY.md` + memories,
  and `mcp/` (user-scope MCP servers). Home paths are templatized to `{{USER_HOME}}` / `{{USER}}`.
- **`skills/`** — my 10 skills, duplicated: `handoff`, `grill-me`, `caveman`, `hacktricks`, `hacktricks-api`,
  `reframe`, `autoresearch`, `context-sandbox`, `simplest-probe-first`, `fresh-context-verify`.
- **`bootstrap.ps1`** — deploy onto a new machine (backs up any existing `~/.claude` first; non-destructive
  on `~/.claude.json`).
- **`sync-self.ps1`** — re-snapshot the live `~/.claude` back into `config/` (templatized, secret-flagged).
- **`secrets.example.json`** — the env-var names to set (never commit real values).

## Quick start (new machine)
```
git clone https://github.com/Prekzursil/agent-skills-toolchain.git
pwsh agent-skills-toolchain/agent-self/bootstrap.ps1
# set the secret env vars from secrets.example.json, then:
claude   ->   /login
```
SessionStart hooks replay the event-ledger as ground truth; `MEMORY.md` auto-loads. You're me.

## Keep it current
After evolving the live config, run `pwsh agent-self/sync-self.ps1` and commit — this folder stays a true
mirror of the running agent.