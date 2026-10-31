---
title: README
type: note
permalink: dqverify-repo-20261013/agent-self/home/readme
---

# agent-self/home — captures of HOME-ROOT harness files

This directory versions files that live directly in `%USERPROFILE%` (home root), NOT in
`~/.claude`. They had no capture location before 2026-08-27:

- `agent-self/config/` mirrors `~/.claude/*` (via `sync-self.ps1`, templatized, WIPED each run)
- the repo-root `AGENTS.md` is this REPO's own contributor guidelines — it is NOT the home file
- nothing captured `~/AGENTS.md` (the "Native Codex and Shared Control Plane Contract",
  the cross-runtime rules file every agent runtime loads)

| repo file  | live source                     | direction    |
|------------|---------------------------------|--------------|
| `AGENTS.md`| `C:\Users\<user>\AGENTS.md`     | live -> repo |

Capture is manual (copy + hash-verify) for now; `sync-self.ps1` deliberately does not touch
this directory because its wipe-and-repopulate cycle only owns `agent-self/config/`.
Live is runtime SSOT; never deploy repo -> live from here without diffing first.