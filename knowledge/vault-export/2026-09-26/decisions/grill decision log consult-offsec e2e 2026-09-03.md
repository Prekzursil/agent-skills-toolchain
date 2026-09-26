---
title: grill decision log consult-offsec e2e 2026-09-03
type: decision
permalink: main/decisions/grill-decision-log-consult-offsec-e2e-2026-09-03
name: grill decision log consult-offsec e2e
description: Converged grill decisions for the consult-offsec e2e registration wave
  (2026-09-03)
tags:
- decision-log
- grill
- consult-offsec
- models-registry
---

# Grill decisions — consult-offsec e2e wave (2026-09-03)

- [decision] Q1 Wave shape: PR-first, verify during review; red-team dissent (verify-first) mitigated by landing server fixes + evidence before PR opens.
- [decision] Q2 OLLAMA_CONTEXT_LENGTH canonical = 65536 (bench receipts: 64K held under full desktop load). Repo estate env 8192→65536 in the wave; never ship the mismatch.
- [decision] Q3 Dollar enforcement: server.py meters USD against audit-log usage (fail-closed, env ceiling); registry family sums to $2/day (featherless 1.0 + hf-router 1.0), documented shared/unenforceable. Prior state: NOTHING metered dollars — count-cap only; first overspend signal would have been account-level featherless cutoff.
- [decision] Q4 Registry rows unprobed/declared at PR open; probe receipts land as review-time amendments (probe pass scheduled DURING review).
- [decision] Q5 Hybrid topology: ZCode builds (single writer, stacked branch, git worktree); DevFleet reviews + probes (owner's Claude Code instance); Codex async via mailbox (contact pending msg#50/#51, expires 2026-09-10).
- [decision] Q6 Stanzas artifact redaction: ${HF_TOKEN}-style env-var placeholders + env mapping table.

Authoritative log: C:\Users\Prekzursil\.zcode\workspace\default\out\GRILL-DECISION-LOG-consult-offsec-e2e.md. Build plan: out/pr-lane-plan.md. Related: [[consult-offsec-mcp]], [[zcode-custom-providers]].