---
title: 2026-03-10-ops-skill-expansion
type: note
permalink: dqverify-repo-20261013/docs/plans/2026-03-10-ops-skill-expansion
---

# Ops Skill Expansion

## Summary

This change adds an operations-first live skill wave to `agent-skills-toolchain`. The new live skills focus on cross-host Codex recovery, long-running migrations, VMware and WSL incident handling, and reboot-safe continuation. Everything else from the broader workstation-skills backlog enters the repo as incubating skill notes rather than fake live artifacts.

## Live skill policy

The first wave uses mixed packaging:

- script-backed live skills for deterministic read-only discovery or recommendation work
- reference-heavy live skills for workflows that still depend on judgment and stop rules

Script-backed v1 skills:

- `codex-runtime-recovery`
- `codex-session-reunion`
- `long-copy-orchestrator`

Reference-heavy v1 skills:

- `wsl-vmware-cutover`
- `offline-linux-disk-surgery`
- `windows-virtualization-conflict-triage`
- `codex-vscode-host-routing`
- `reboot-safe-ops-continuation`

## Promotion and backlog handling

The remainder of the workstation incident backlog lands under `docs/incubating/skills/`. Each note captures a real trigger, likely scope, and planned resources while explicitly stating why the concept is not a live skill yet.

This keeps the repo consistent with its existing rule: `skills/` is for installable, validated artifacts only, while incubation docs hold ideas that still need repeated evidence or tighter runtime boundaries.

## Validation expectations

Every live skill should validate with the repo-wide skill validator. Script-backed skills should also prove one success path and one stop-rule path before being treated as stable promotion candidates.

## Non-goals

- adding MCP-native or web-tool projects in the same batch
- storing raw session exports or machine-specific secrets in the repo
- collapsing all ops workflows into one generic WSL or debugging skill