---
title: 'Per-project intelligence: projid identity keystone + project-card inject'
type: note
permalink: main/projects/per-project-intelligence-projid-identity-keystone-project-card-inject
tags:
- claude-harness
- projid
- event-ledger
- continuous-learning-v2
- capability-catalog
- per-project-intelligence
---

# Per-project intelligence (projid keystone)

Built 2026-06-29 to make terse prompts auto-apply per-project context. Rides existing SessionStart carriers (capability-catalog inject) — ZERO new always-on hooks. All fail-open, additive, reversible. Tests pass (27 + 22 + 13 checks across 3 suites); ruff clean.

## Files
- `~/.claude/hooks/_shared/projid.py` — UNIFIED repo-identity resolver (NEW). `canonical_id = sha256(cred-stripped remote, else git toplevel, else raw cwd)[:12]`. Reproduces continuous-learning-v2's exact 12-hex id (verified 5/5 homunculus remotes MATCH) so "both import ONE resolver" without orphaning CL-v2 stores. Precedence: `<root>/.claude/project-id` pin -> remote -> toplevel -> cwd; `CLAUDE_PROJECT_DIR` picks root. `ledger_slug()` = `{name}-{canonical[:8]}` for git, EXACT legacy `{name}-{sha256(rawcwd)[:8]}` for non-git (zero churn). `detect_project()` = CL-v2-compatible shim.
- `~/.claude/hooks/_shared/projid_migrate.py` — `python projid.py migrate [--apply]` (DRY-RUN default). Back-merges fragmented ledger shards by resolving each shard's stored path; "commit-rescue" for gone paths (merge only if recorded git head is a real commit in a resolvable repo — verifiable, not a name guess). `--apply` re-sequences events by ts, rebuilds state.json (incl. milestone-supersedes remap), records every source cwd in `aliases`, MOVES sources to `<root>/.migrated/` (never deletes).
- `~/.claude/hooks/event-ledger/ledger.py` — EDITED `_slug` to delegate to `projid.ledger_slug` with lazy fail-open fallback to `_legacy_slug`.
- `~/.claude/hooks/capability-catalog/project_card.py` — NEW. Per-project card (<=40 line / <=3200 char) + read-only "where we left off" resume-strip (last milestone + open failures + `.beads/context/execution-state.md`; goal as filler). `seed` CLI auto-detects stack/entrypoints + ledger-derived left_off. Card at repo `.claude/project-card.json` (wins) or `~/.claude/projects/<canonical_id>/project-card.json` (override via `CLAUDE_PROJECT_CARDS_DIR`).
- `~/.claude/hooks/capability-catalog/inject.py` — EDITED to append the card after the global catalog, reusing existing dedup/skip-compact/fail-open. NO settings.json change (already wired).

## Fragmentation FIX (the documented bug)
event-ledger keyed by cwd-hash -> one repo split across shards. Live migrate DRY-RUN: 66 shards -> 51 canonical. Reframe **10 shards -> 1** (2 case-variant checkouts `Documents/GitHub` vs `Documents/github` + monorepo subdirs components/features/src/sidecar/media_studio + 3 commit-rescued gone worktrees). battlecats-toolkit 4->1, agent-skills-toolchain 3->1, research-repo 2->1; 5 relabels; 20 unresolved (gone paths, kept). Applied to a temp COPY: unified Reframe shard = 259 events / 10 aliases / 13 open failures.

## Decisions
- Normalization is MINIMAL (creds only) — stripping `.git`/case would change every existing CL-v2 id (mass orphan). Deeper ssh/https unification deferred (needs coordinated re-key).
- Monorepo subdirs collapse to the repo by remote-precedence (intended; matches CL-v2). Escape hatch: `<subdir>/.claude/project-id` pin.
- migrate NOT applied to live ledger — user's call (folds a 90-event media-studio + 177-event phenibut). DRY-RUN default; reversible.

## How to use
- Run `python ~/.claude/hooks/_shared/projid.py migrate` to preview, `--apply` to unify (sources backed up to `.migrated/`).
- Seed a card: `python ~/.claude/hooks/capability-catalog/project_card.py seed --cwd <repo>` then edit invariants/tools/skills/quality_bar.
