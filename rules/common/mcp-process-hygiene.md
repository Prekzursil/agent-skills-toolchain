---
title: MCP process & orphan hygiene (G-99)
scope: common
loads: on-demand (referenced from AGENTS-RUNTIME §12); read before ANY workflow/fleet/second-session
  launch
verified: 2026-09-25 (VM OFFLOAD-W2025); ports G-99 from home ~/AGENTS.md (2026-09-20)
paths:
- '**/.claude/**'
- '**/.agents/**'
- '**/*mcp*'
permalink: dqverify-repo-20261013/rules/common/mcp-process-hygiene
---

# MCP process & orphan hygiene (G-99)

Every agent session instantiates the full global MCP registry (~80 servers → 60–100 processes, 10–25 GB commit). The box freezes on **COMMIT** (RAM + pagefile), not OOM. This is the rule the harness references but never had a file for — here it is.

## Reaper registry (P3, 2026-09-25) — authoritative ONE PER CLASS

There are two distinct problem classes and they need different tools. Four implementations
existed with three incompatible safety policies; this is the declared set.

| Class | Authoritative tool | Detects |
|---|---|---|
| **Orphans** (root session dead) | `scripts/reap_orphan_mcp.ps1` | ancestry chain reaching no live root |
| **Duplication** (live, per-session pile-up) | `scripts/mcp_reap_duplicates.py` | process-pileup, independent of parentage |

- `scripts/orphan_sweep.ps1` — **SUPERSEDED-BY** `reap_orphan_mcp.ps1` (same class, weaker policy).
- `scripts/agentic-perfection/cursor-orphan-reaper.ps1` — **SUPERSEDED-BY** `reap_orphan_mcp.ps1`
  (tool-specific case of the general orphan class; a retired copy already sits in `backups/`).

**Reaping is NOT the cure.** Measured 2026-09-25: the VM held 333 MCP processes / 20.51 GB with
only ~10 dead-parent, because ~97% belong to 4 live sessions — an orphan reaper is structurally
incapable of helping. HOME, with the same registry but a shared-daemon shape (0 npx, 22 HTTP
hubs), held 109 processes and 0 session-owned. **The cure is process SHAPE, not a bigger reaper.**

## Pre-flight (HARD — before ANY workflow / fleet / second session)
- Run `scripts/mcp_ram_audit.ps1`. **If MCP-class procs > 150 OR free RAM < 4 GB → run `scripts/reap_orphan_mcp.ps1` FIRST.**
- The reaper is SAFE: ancestry-chain kill only (dead-root ancestry), whitelists persistent daemons (mcp-hub / basic-memory / agent-mail / socat / auth2api / actions-runner / cc-gateway / zai-anon), conhost is never a victim, `-WhatIfOnly` dry-run available (hardened after the 2026-09-22 silent-kill audit).
- **NEVER reap mid-fleet** — it will kill the live subagent/workflow processes of the run you are in.

## RAM gates
- **NO multi-agent fleets / Workflows while free RAM < 8 GB** (extends G-26/G-99 to Workflows).
- **NEVER fix RAM or context by DISABLING MCP servers in configs — curation is load-bearing; reap ORPHANS instead.** Tool Search already de-fangs the *token* cost of idle connectors; what remains is processes + RAM + each server's instruction prose.

## Automation
- The **`MCPOrphanReaper`** scheduled task reaps every 30 min. If missing, re-register (elevated):
  `Register-ScheduledTask -TaskName MCPOrphanReaper -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)) -Action (New-ScheduledTaskAction -Execute pwsh.exe -Argument '-NoProfile -File C:\Users\Prekzursil\.agents\scripts\reap_orphan_mcp.ps1') -RunLevel Highest -Force`

## Tool-Search killers (context blow-up, NOT RAM)
- **A custom `ANTHROPIC_BASE_URL` disables Tool Search** → the whole deferred surface (~3000 tools here) loads UPFRONT. Gateway / GLM-plane / cc-529 / key-failover sessions are the risk. The SessionStart guard (`hooks/scripts/context-guard.ps1`) warns.
- **`ENABLE_TOOL_SEARCH=auto:N` is context-window-relative** (`auto:5` = 5% of the window). On a 1M model that is ~50 K tokens, so a mid-size surface can silently load back upfront. Prefer explicit `ENABLE_TOOL_SEARCH=true`.

## Known drift / health (VM, measured 2026-09-25)
- **354 MCP-class processes** (> 150), **`MCPOrphanReaper` task MISSING**, and the hub layer is **down**: `McpHub` SSE `:24680` and CyberStrike HTTP hubs `:31110–:31116` all refused. Backends are then unavailable (not context-inflating), but bring the hubs up via their start scripts when needed.
- **`.mcp-disabled-defaults.json` lists `cloud-hub`/`social-hub` as parked/dead while both run live** — reconcile at USER scope (never per-tree copies), never destroy enabled/disabled state.

## DOCTRINE LOCK — what "match HOME" does and does not mean (owner decision, 2026-09-25)

**Match HOME on process SHAPE. Do NOT match HOME on the server LIST.**

Measured the day this was written, from home's real `.claude.json` pulled over the tailgate —
not inferred from process counts:

| | HOME | VM |
|---|---|---|
| mcpServers | 28 | 88 |
| http / npx / direct | 22 / **0** / 6 | 20 / 23 / 45 |
| servers HOME has that the VM lacks | **0** | — |

Home is a **strict SUBSET**, it was 38 commits behind, and it was BEHIND on the discipline
layer (no §12, no five registers, 22 deployed rules vs 25). So "home has 0 npx" was never a
better *wiring* — home simply does not run any of those 23 servers. There is nothing to copy.
Home is a valid reference for **how many processes per server** and an INVALID reference for
**what should exist**. Applied literally, "match HOME" would DELETE working capability.

- The VM's **RE stack** (ghidra / ida / jadx / apktool / frida / angr / hexstrike) and
  **research stack** (arxiv / crossref / openalex / pubmed / scholarly) are deliberate VM
  specialisation and must survive a host move intact.
- **Reachability is a SNAPSHOT, not a verdict.** The RE stack is *backend-on-demand* by design
  (`~/.local/opt/re-harness/` starts those backends), so it reads "dead" while being perfectly
  good. Classify every unreachable entry by WHY before deleting any:
  `package-gone` → delete · `backend-on-demand` → KEEP + document the start procedure ·
  `retired/superseded` → delete · `unknown` → QUARANTINE, never delete on a snapshot.
- The hub-multiplex tier is **home-only and live there; absent here by design** — that is
  doctrine, not a defect.
- Instruments: `scripts/mcp_triage.py` (registered vs reachable vs at-home) and
  `scripts/mcp_probe.py` (rung ladder — distinguishes *package-gone* from *backend-on-demand*,
  because rung 1 answers "does the entrypoint exist" independently of whether it starts).

Evidence: home ~/AGENTS.md G-99 (2026-09-20, measured 397 orphaned MCP procs / 115.8 GB thrash) + the verified 2026-09-25 audit. Sibling: `rules/common/context-reduction.md`.