---
title: research CSIE compute backends 2026-07-24
type: note
permalink: main/research/research-csie-compute-backends-2026-07-24
tags:
- research
- csie
- compute-backend
- databricks
- modal
- github-actions
- fan-out
- '2026-07-24'
- confidence-high
---

# Compute backends for the CSIE fan-out (deep-research 2026-07-24)

**Brief:** pick the next pluggable backend(s) after Databricks for ~48 concurrent AI coding agents
(clone repo, install, test+cov, write code, git-push agent/ branch). 3 parallel researchers (Exa+SearXNG),
graded confidence, cited. Full workflow: `wf_5f3ff0f1-0c5`.

## HEADLINE: two-tier, because two needs pull opposite directions
- **BUILD tier** (fast bulk Linux coding fan-out) and **VERIFY tier** (cross-platform CI matrix) are
  DIFFERENT problems. No single backend does both well. → the CSIE `Backend` interface gets ≥2 impls.

## Ranked recommendation (top-2 to build after Databricks)
1. **GitHub Actions matrix — the CROSS-PLATFORM VERIFY tier.** [High] The ONLY turnkey backend running a
   repo's real `ubuntu-latest + windows-latest + macos-latest (+arm64)` matrix — directly fixes the proven
   "Linux fix passed ubuntu, failed windows-latest" gap (env-inspector #145). Cold start sec-to-30s (vs DBX
   3-5min); fully ephemeral; secrets first-class; `workflow_dispatch` to submit (⚠️ 204 = NO run-id, poll
   list-runs to correlate). Concurrency PLAN-GATED: Free 20 / Pro 40 / Team 60 / Ent 500; **macOS separate
   cap 5 (free/pro/team) / 50 (ent)**. **Public repos = FREE + unlimited (concurrency-capped only)** — the
   estate's repos are mostly public + already run GHA CI → natural fit. Private cross-platform ≈ $56/night.
   Runners only 2-core/8GB. **Depot / Namespace** (GHA-runner resellers) = UNLIMITED concurrency + full
   Linux/Win/macOS matrix + low setup (swap runs-on) → the drop-in upgrade past the caps.
2. **Modal — the FAST bulk-Linux BUILD tier.** [High] Sub-0.5s median sandbox scheduling (v2) vs DBX 3-5min;
   50k-concurrent platform ceiling (Starter $0=100 containers, Team $250=1000); **already exposed as
   cloud-hub `modal_sandbox_*` MCP tools** with the exact submit/poll/harvest primitive
   (create/exec/poll/wait/read_file/terminate); strongest secrets (named + OIDC + short-lived JWT
   injection); scale-to-zero. COST: Sandbox tier has a 3.01x non-preempt premium baked in →
   ~$5.7-11.4/night (2-4core/8-16GiB × 48 × 15min), ~$170-340/mo. Purpose-built for untrusted AI code.

## Alternates (graded)
- **Fly.io Machines** [High]: ~4x cheaper than Modal (~$1.4-2.8/night), STRONGER Firecracker microVM
  isolation, ~300ms-1s start — BUT no queue/map primitive (you build submit/poll/harvest). Cost-down BUILD alt.
- **e2b.dev** [High]: AI-native Firecracker sandboxes, <200ms cold start; Pro $150/mo=100-1100 concurrent. Linux-only.
- **AWS Batch(EC2)/Fargate** [High]: solid generic Linux batch; Fargate ~30s provision, new-acct 6-vCPU cap
  (bump to 4000). GCP Batch similar (2000 concurrent VMs/job; VM-boot minutes). Both Linux-only, more setup.
- **OpenAI Codex Cloud** [High]: genuine native agent-in-cloud (submit→isolated container clones repo, runs
  1-30min, returns diff/PR via `codex cloud exec`); native git harvest; zero infra. BUT **linux/amd64-only**
  (codex-universal) + runs OPENAI's agent/model, NOT our pinned gpt-5.6-sol harness → WEAK for a pinned
  self-modifying toolchain; niche Linux-repo lane, not the cross-platform backend. Per-5h task quotas, not a
  clean concurrency number.
- **RunPod** [Medium]: GPU-first, default 3 workers/endpoint (60 acct cap, >60=support) → out-of-box blocker; skip.
- **CodeSandbox/Together** [Med-High]: sub-1s VM FORKING (best-of-N agent A/B), Linux-only.

## Confidence & gaps
- Backend platform facts: High (official docs cited). Specific $/hr for Fargate/GCP-VM/Namespace: order-of-
  magnitude (rates not cleanly extracted). GHA cold-start SLA: none official (sec-to-30s inferred from Depot).
  Codex-Cloud instantaneous parallel ceiling: UNVERIFIED (only 5h-window quotas official). Modal live plan
  tier: `modal_whoami` MCP timed out — assumed public pricing caps.

## Design implication for CSIE
- `Backend` interface (submit/poll/harvest), impls: Databricks (built), **Modal (BUILD, next)**, **GitHub
  Actions (VERIFY, next)**. Execution = BUILD-then-VERIFY: fast Linux fan-out → full-CI-matrix verify before
  adopt/merge. Modal's MCP tools mean the BUILD impl is low-effort; GHA VERIFY reuses the repo's own CI.

Related: [[Codex-Databricks fan-out harness + Program E — v3 plan & gate history (2026-07-24)]], [[Fan-out node is Linux-only — node-green != CI-green for cross-platform repos (2026-07-24)]].
