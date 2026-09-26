---
title: Codex alpha hook rollout workspace-gate v2 decision 2026-08-19
type: decision
permalink: main/projects/agent-skills-toolchain/codex-alpha-hook-rollout-workspace-gate-v2-decision-2026-08-19
tags:
- agent-skills-toolchain
- hooks
- workspace-integrity
- codex-alpha
- superseded-design
---

# Codex alpha hook rollout workspace-gate v2 decision

valid_as_of: 2026-08-19

## Milestones

- Public Codex shim resolves to 0.149.0-alpha.1 through the side-by-side v2 package tree; legacy npm metadata remains 0.147.0 because live processes still hold the npm-managed binary.
- The event-ledger presence-file lock cascade was replaced by an OS-backed byte lock and validated under crash recovery and contention.
- Fresh hook telemetry after the repair shows no PreToolUse/PostToolUse failures in the checked window; later 45-80s outer delays occur between hook events rather than inside hook bodies.

## Superseded failure

The first workspace hard-gate implementation is retired. Production probes showed:
- request-time repository scans consumed or exceeded the 1.4s dispatcher budget;
- same-target divergent concurrent writes could both be allowed;
- Update+Move self-collided while secondary symbols could bypass duplicate detection;
- daemon-thread timeout could return while the worker still mutated state;
- fake .git markers were accepted as repository identity.

It was briefly activated live without an approved freeze, blocked the current session, wrote an invalid composite manifest, and was fully rolled back to the exact predeployment live hashes. The activating process identity is UNVERIFIED; settle via session transcript or process-creation audit for 2026-08-19 12:59:50-13:00:42 UTC.

## Current decision

Implement source-only v2 before any live activation:
1. per-physical-repository SQLite index under the harness state root;
2. full scan only on explicit refresh/SessionStart, never PreToolUse;
3. real sanitized git identity;
4. exact immutable postimage mutation plans;
5. owner+operation+payload/postimage-bound reservations;
6. all supported top-level symbols and duplicate doc/source claims;
7. transactional nested file/directory/depth budgets;
8. advisory hook work in a killable child process/job, with confirmed exit before terminal result;
9. known-good/known-broken, concurrency, mutation, lint, and p95/p99 latency gates;
10. targeted live merge preserving Grok and sticky session behavior; no source-tree wholesale deployment.

Do not remove the legacy file-scope hook or enable shell allowance until the v2 gate and protected attestation are independently proven in both states.

## Rollback anchor

Dedicated preincident backup:
C:\Users\Prekzursil\.agents\deploy-backups\codex-alpha-hook-rollout-live-20260819T125950Z
