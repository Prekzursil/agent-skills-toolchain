---
title: codex-store-auditor
type: note
permalink: dqverify-repo-20261013/docs/incubating/skills/codex-store-auditor
---

# codex-store-auditor

## Purpose

Potential future skill for workflows that inventory `.codex`, `.codex-vscode`, auth roots, session counts, memory files, config drift, and lock-sensitive state across hosts.

## Why this is not a live skill yet

- The trigger is real, but the workflow needs more repeated pressure-tested evidence before promotion.
- The current first wave already covers the higher-frequency incidents more directly.

## Likely scope

- inventory `.codex`, `.codex-vscode`, auth roots, session counts, memory files, config drift, and lock-sensitive state across hosts.
- define stop rules and evidence requirements for the workflow
- identify whether the value is mostly references, scripts, or both

## Planned resources

- one concise reference on discovery and guardrails
- one workflow checklist or scoring rubric
- scripts only after a repeated deterministic task is proven