---
title: 'Codex fan-out: safe pattern + fragility (Windows local)'
type: guide
permalink: main/harness/codex-fan-out-safe-pattern-fragility-windows-local
tags:
- codex
- fan-out
- orchestration
- windows
- gotcha
---

# Codex fan-out: safe pattern + fragility (Windows local, 2026-07-17)

**valid_as_of: 2026-07-17.** Proven during the PrimariRo build (Codex built 9/10 units).

## The pattern (user-proven; NOT mcp__codex__codex, which blocks + shares a worktree)
`nohup codex exec --dangerously-bypass-approvals-and-sandbox -c 'features.multi_agent_v2.enabled=false' "$(cat spec)" </dev/null > log 2>&1 &` — each agent in its OWN fresh `git clone` → its OWN branch `codex/<unit>`, pushing independently. Model gpt-5.6-sol at ultra (config default). Orchestrator merges each `codex/*` branch as it lands.

## Fragility — each cost real time this session
- **RAM:** 9 concurrent OOM'd; **3-concurrency is RAM-safe**. Stagger launches ~4s.
- **Shared app-server cascade:** killing ONE codex process tree kills ALL codex sessions — you CANNOT selectively kill a stalled agent. (Extends [[Codex shared app-server cascade]].)
- **Shared auth.json:** concurrent agents contend on OAuth refresh → "refresh token already used" breaks all → needs `codex login`. Staggering reduces it.
- **ctx-100% stalls:** heavy units (live-fetch/research/big enforcement-spine) stall at full context; pure-code + self-contained units succeed. **Two-strikes fix:** split a unit that dies twice into smaller sub-units (pipe-core → schema + gates succeeded where the whole died twice at ctx-100%).
- **STALE origin/main starves fresh clones (my error):** agents clone origin/main; merging LOCALLY without pushing means later agents clone a main MISSING deps → they stall complaining files are "absent". **ALWAYS push origin/main after each merge.**
- **Signal:** pushed branches are the only real deliverable — poll with a background `git ls-remote` watcher; the codex-monitor shows thread state but "done" ≠ "pushed".
- **Verify before merge:** never blind-merge agent output — check scope (only its files), real-vs-fabricated data, PII, and run the tests yourself (orchestrator = independent verifier, not self-cert).