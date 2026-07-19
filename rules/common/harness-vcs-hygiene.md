# Harness version-control hygiene (non-negotiable)

Cross-tool rule read by Claude Code · Codex CLI · Antigravity (agy). Harness work that
lives only in the live trees is **architecturally orphaned** — before `sync-from-live.ps1`
existed, 462 files / 2.73 MB of authored harness work could never reach version control at
all (the repo shipped only repo→live sync). This rule + its enforcing hook close that hole.

## The rule

- **Any artifact authored under the LIVE harness trees — a skill (`~/.agents/skills`,
  `~/.claude/skills`), a hook (`~/.claude/hooks`), a rule (`~/.claude/rules`,
  `AGENTS.md`), an agent/command, or an MCP config — MUST be reconciled into
  `agent-skills-toolchain` before the work is called done.** Live-only is drift, not
  a resting state.
- **The repo is the source of truth; the live tree is a deploy target.** Editing a
  deployed copy directly (e.g. `~/.claude/hooks/_dispatch/manifest.json`) is invisible to
  git and is OVERWRITTEN on the next deploy. Edit the repo source, then deploy — never the
  other way. (A PreToolUse hook warns on a deployed-copy edit; heed it.)
- **Reconcile with the built tool, don't hand-copy:** `scripts/sync-from-live.ps1`
  (`-Report json` to see drift, `-WhatIf`, then a scoped commit) carries live→repo with the
  nested-repo / vendored-tree / repo-owned-file guards already applied.

## Enforcement (this is the "hooks" half)

- **`hooks/git-hygiene/check.py`** (Stop hook, wired in `hooks/_dispatch/manifest.json`)
  surfaces, at turn-end: (1) live-authored harness files absent from or differing from the
  repo, and (2) YOUR repos holding uncommitted / unpushed / no-upstream work (vendored and
  agent-scratch clones excluded). Advisory — **inject only, never blocks** (AGENTS.md §6),
  self-throttled to one full scan per 15 min (`GIT_HYGIENE_THROTTLE_SEC`). Opt-out:
  `GIT_HYGIENE=off` or `hooks/git-hygiene/.disabled`.
- A weekly scheduled drift-audit is the low-frequency backstop; the Stop hook is the
  per-session nudge. Never let a "done" claim stand on harness work that the hook still
  flags as un-reconciled.
