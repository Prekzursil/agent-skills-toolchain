---
name: codex-runtime-recovery
description: Use when Codex state is split across Windows, WSL, or VS Code, sessions disappear, state_5.sqlite files churn, or CODEX_HOME and launch routing drift need diagnosis before destructive repair.
---

# Codex Runtime Recovery

## Overview

Recover Codex when runtime ownership drifts across hosts or launch paths. Start read-only, identify the canonical store, and separate data-plane issues from extension-host or auth failures before touching live state.

## Reference Map

- Read [references/topology-checks.md](references/topology-checks.md) to verify active `CODEX_HOME`, candidate stores, config paths, and lock-sensitive files.
- Read [references/recovery-lanes.md](references/recovery-lanes.md) to choose between lightweight recovery, canonicalization, and reset-only-as-last-resort flows.
- Run [scripts/inspect_codex_topology.py](scripts/inspect_codex_topology.py) before making any mutation. It inventories candidate stores, session counts, and state DB presence without editing them.

## Required Discovery

1. Identify the active host and launch path: CLI, VS Code, Windows, WSL, or remote.
2. Determine the authoritative store to preserve before merging or resetting anything.
3. Separate data-plane failures from control-plane failures.
4. Inspect `auth.json`, `config.toml`, `state_5.sqlite*`, and session trees before rotating or deleting them.

## Recovery Lanes

### Lightweight lane

Use when the session exists and visibility is broken. Prefer targeted JSONL import, `codex resume`, or a path fix over broad resets.

### Canonicalization lane

Use when Windows and WSL or CLI and VS Code have diverged. Converge on one canonical `CODEX_HOME`, archive mirrors, and update launch settings to stop re-divergence.

### Reset lane

Use only after export or backup and only when migration or state DB corruption blocks startup across all launch paths.

## Stop Rules

- Do not delete live state DBs before creating a backup.
- Do not merge stores blindly while both sides are still active writers.
- Do not classify token or auth failures as missing-session incidents.
- Stop and collect evidence if the failure reproduces on both Windows and WSL after config alignment.

## Output Contract

Return `success`, `partial`, or `blocked` and list:

- active host and `CODEX_HOME`
- canonical store chosen
- evidence gathered
- exact mutation steps taken or deferred
- residual risks

## Common Mistakes

- Treating VS Code extension crashes as data loss.
- Resetting both Windows and WSL stores at once and destroying the only good copy.
- Rotating `state_5.sqlite*` without proving the store split or migration mismatch first.
