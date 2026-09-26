---
title: 'Working style: document tools + keep toolchain/harness permanently upgradeable
  (2026-07-24)'
type: note
permalink: main/feedback/working-style-document-tools-keep-toolchain-harness-permanently-upgradeable-2026-07-24
tags:
- feedback
- documentation
- toolchain
- harness
- maintenance
- '2026-07-24'
---

# Working style: document tools + keep the estate permanently upgradeable

Owner directive (2026-07-24), standing:

- **ALWAYS write findings to basic-memory as I go** — continuous documentation, not just at milestones. (I have been; keep it up every session.)
- **Keep a USAGE doc for every tool I build** — "documentation for this specific tool and how to use it." Each durable tool (e.g. the Codex-Databricks fan-out harness) needs a README/USAGE that a fresh context can follow: what it is, how to run each phase, the gotchas.
- **Keep the toolchain + harness up to date and PERMANENTLY UPGRADEABLE** — rules, hooks, skills, MCPs, agent configs. Not a one-shot; an ongoing maintenance posture.
- **Use the maintenance skills** for this: `/deep-research` (research upgrades), `/grill-me-extensive` (adversarial scoping), `/mcp-fleet-curation` (MCP hygiene), and similar. "and so" = the general family of upkeep tooling.

**Why:** tools rot and context is lost across sessions/compaction; durable docs + continuous basic-memory capture + an upgradeable toolchain are how the estate compounds instead of decaying. A tool with no usage doc is a tool the next session can't run.

**How to apply:**
- When I build/change a durable tool → write/update its USAGE doc in the repo AND a basic-memory note.
- Capture findings/gotchas to basic-memory continuously during the work, not only at the end.
- Periodically (or when relevant) run the maintenance skills to keep rules/hooks/skills/MCPs current.
- Treat every tool as a living artifact with a version + changelog, not a throwaway.

Related: [[Codex-Databricks fan-out harness + Program E — v3 plan & gate history (2026-07-24)]], [[Desired agent character]], [[Maintain full rigor]].
