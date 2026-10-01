---
name: always-version-work-products
description: "The user wants every work product staged, committed, pushed and PR'd continuously so a Codespace interruption loses nothing"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca9aa7a4-16ad-4e9d-bafe-00eed0171063
  modified: 2026-09-19T01:16:57.481Z
---

Version everything produced in a session — decision logs, evidence, subagent reports, research, scripts — in a git branch on GitHub
with an open PR, and keep syncing while work continues. On 2026-09-19 the grill artifacts live in
`/home/codespace/grills/2026-09-19-qwen38-heretic-space/` and are auto-synced by `save-to-repo.sh` (rsync + commit + push every
5 min) into `docs/grills/2026-09-19-qwen38-heretic-space/` on branch `grill/qwen38-heretic-space-2026-09-19` of
`Prekzursil/agent-skills-toolchain` (PR #336).

**Why:** "everything we do here please stage commit push and PR them so in case the codespaces interrupts nothing is lost" —
the Codespace home dir and /tmp are volatile.
**How to apply:** branch from main first (repo rule), commit only the work-product paths (never stray files like the Codacy
`.gitignore` edit), scan for secret shapes before every push (CI runs gitleaks over history), end commits with the required
Co-Authored-By line and PR bodies with the Claude Code footer, and restart the sync loop after any session restart.

Related: [[qwen38-heretic-space-grill]], [[keep-full-subagent-output-and-wait]]
