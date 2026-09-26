---
title: Round-3 deep-research adopted + admin updates + Python restore 2026-06-15
type: milestone
permalink: main/projects/learnings/round-3-deep-research-adopted-admin-updates-python-restore-2026-06-15
tags:
- deep-research
- round3
- security
- mutation-testing
- admin-updates
- python
---

# Round-3 deep-research adopted + admin updates + C:\Python314 restored — 2026-06-15

**Third deep-research scan implemented** (committed `44536dd` + the RTV/PDR workflow separately, on `feat/optimal-agentic-workspace` in agent-skills-toolchain; NOT pushed). Doc: `docs/round3-adoptions-2026-06-15.md`. Each item was empirically verified — which caught three wrong assumptions:

1. **#1 dependency cooldown APPLIED.** npm key is **`min-release-age`** (the research's `minimum-release-age` was a silent no-op — verify keys!). Set `npm config set min-release-age 1440` (~/.npmrc) + `pnpm config set minimumReleaseAge 1440`, both read-back confirmed. yarn here is **Classic 1.22** (no cooldown; that's Berry 4.x). Low real risk: `@latest`/range installs (incl. npx MCP launches) just resolve to newest ≥1-day version, don't fail.
2. **#2 mutation gate.** StrykerJS template at `tools/mutation-gate/stryker.config.template.json` (TS/jest, runs via npx). Python = **cosmic-ray** (installed, Windows-native) — **mutmut is WSL-ONLY** (issue #397), rejected. Grades assertion strength (the reward-hack coverage+test-tamper can't detect).
3. **#3 RTV/PDR** (test-time-compute scaling, arXiv:2604.16529, Opus 4.5 SWE-bench +6.7 / Terminal-Bench +12.2) — built as `workflows/rtv-pdr.js` + `skills/rtv-pdr/`, gated behind ESE.
4. **#4 mcp-scan** — OSS tool **acquired/renamed by Snyk → `snyk-agent-scan`** (installed). Verified runs LOCAL, masks secret env values (`***`), consent-gates each server (no auth/cloud on default `scan`; `evo`=cloud-push, `guard`=proxy — avoid). On-demand audit, not a hook.
5. **#5 OTel traces** — `tools/otel-traces/enable-otel-traces.ps1` (on-demand Jaeger+env enabler; beta; prefer cc-trace for killable runs).

**Admin updates (elevated session):**
- **C:\Python314 RESTORED** (python.org 3.14.6 installer, in-place): python.exe back at 3.14.6, the 2.66 GB ML/data site-packages survived (aiohttp imports OK). The decapitation (from the earlier failed winget Python upgrade) is fixed.
- JDK 21 / gh / Python(AppData winget) — winget reports already-current. uv NOT winget-managed (stays 0.10.4). deno 2.8.3, npm 11.17.0.
- **Node 24 LTS migration ABORTED** — `winget uninstall OpenJS.NodeJS` HUNG ~20min: can't remove node.exe while ~250 live node.exe processes (MCP servers) lock it. Killed winget surgically; **Node 25.2.1 left intact + working**. LESSON: never migrate Node mid-session with MCP servers running — needs a clean no-node state (close everything / fresh boot) or just stay on 25 (works fine).

**dx-velocity = honest null** (nothing net-new). See [[deep-research-batch-2nd-scan-implemented-crash-recovery-2026-06-15]].