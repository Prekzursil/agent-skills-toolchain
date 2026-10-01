---
name: toolchain-skills-not-registered-here
description: "In this Codespace the user's /skills from agent-skills-toolchain are NOT in the Skill tool listing; load them by reading the repo files"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca9aa7a4-16ad-4e9d-bafe-00eed0171063
  modified: 2026-09-19T00:11:39.842Z
---

When the user types a slash command such as `/grill-me-extensive` that is not in the registered skill list, do not refuse or guess:
the skill lives in the repo at `/workspaces/agent-skills-toolchain/skills/<name>/SKILL.md` (often with `references/*.md`), with a
thin wrapper at `commands/<name>.md` and, for the grill family, a shared contract at `.agents/workflows/grill.yaml`. Read those files
and follow them. The repo holds ~370 skills (`ls skills/`); `skills/SKILLS-MANIFEST.md` is the index.

The grill contract asks to persist decisions to an "event ledger" and "Basic Memory" — those MCP tools are part of the user's main
(Windows) box fleet and are not reachable from this Codespace; use a decision-log file plus this file memory instead and say so.

Related: [[qwen38-heretic-space-grill]], [[user-prefers-grill-before-build]]
