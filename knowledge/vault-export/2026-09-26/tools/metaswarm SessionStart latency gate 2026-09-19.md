---
title: metaswarm SessionStart latency gate 2026-09-19
type: note
permalink: main/tools/metaswarm-session-start-latency-gate-2026-09-19
tags:
- harness
- claude-code
- hooks
- metaswarm
- latency
- fix-receipt
---

# metaswarm SessionStart latency gate 2026-09-19

- [fact] SessionStart per-hook durations are recorded in session transcript JSONL (`attachment.type=hook_success` carries `durationMs`) — diagnose hook latency from `~/.claude/projects/<proj>/<session>.jsonl` without re-running anything. SessionStart hooks start concurrently: wall-clock = max, not sum.
- [fact] metaswarm plugin 0.12.0 `hooks/session-start.sh` Phase-1 (BEADS dedup) scanned `~/.claude/plugins/cache` + `~/.codex/plugins/cache` (529 plugin.json, one jq spawn each; finds alone 25s + 9.5s) BEFORE checking whether the cwd is a metaswarm project — 140.5s dead work at every non-metaswarm cwd, because `beads_standalone` is only consumed when `.metaswarm/project-profile.json` exists. Local `_dispatch` (git-hygiene 28.8s) and remember (8.6s) were within budget — not the cause.
- [decision] Patched the live marketplace cache copy with the `sessionstart-latency-gate v1` marker (gate Phase 1 behind `[ -f .metaswarm/project-profile.json ]`). Verified both states: fast path 140.5s → 0.305s with identical output; real-project path still scans (64.6s, exit 0). Canonical patch + idempotent `reapply.py` committed to [[agent-skills-toolchain]] `harness-patches/metaswarm-sessionstart/` (commit 3c9cece7f, pushed to GitHub). Plugin updates clobber the cache copy — re-run reapply.py after any metaswarm update.
- [decision] Deliberately NOT done: no `timeout` added to metaswarm hooks.json (would kill legit 35-65s scans at real metaswarm projects); legacy npm copy `~/.claude/plugins/metaswarm/` left untouched (slated for `/metaswarm:migrate`); no settings.json changes. Upstream PR to dsifry/metaswarm drafted, NOT submitted (outward-facing, awaiting owner approval).
