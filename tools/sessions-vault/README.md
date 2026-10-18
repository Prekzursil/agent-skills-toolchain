---
title: README
type: note
permalink: dqverify-repo-20261013/tools/sessions-vault/readme
---

# sessions-vault — zero-loss agent-session preservation

**Vault (content, NOT in git):** `D:/agent-sessions-vault`
**Repo owns:** this tooling + `stores.yaml` (the source registry). Manifests live in the
vault (`manifest.jsonl`), deliberately outside git per the vendored-tree-bloat rule;
content-in-git is an explicit owner opt-in, not a default.

## What it preserves

Every AI-agent session store on C: and D: — Claude Code (live + 2 archives), Codex
(live `.jsonl.zst` + 2026-06-21 archive + 2026-03-15 seed tar + extracted seed), ZCode
(rollout/exec/image-cache/db/v2/memories/workspace), Grok (dir-per-session live + desktop),
Gemini CLI, Cursor (chats/acp/globalStorage + ~20 auth-state snapshots in Cowork/private),
OpenCode, Cline, Copilot, CyberStrike TUI, VS Code globalStorage/workspaceStorage,
Continue, agentchattr, Claude Desktop (code-sessions/agent-mode/backup), and the
Downloads AI exports + VM backups. 55 stores total (see `stores.yaml`).

## Zero-loss contract

* Every source file gets a manifest record keyed by its own sha256 — **no file-lineage
  assumptions** (control fact: a prior merge bug dropped 47.1% of the Codex store; that
  failure mode is structurally impossible here).
* Dedup: identical sha256 across stores = one physical copy + `alias_of` lines.
  If a canonical copy later grows (session resumed), drifted aliases rematerialize
  their own copy from their own source.
* Incremental: `size+mtime_ns` match keeps the cached hash (no re-read). Grown files
  recopy with `gen+1` and keep `prev={sha256,size}`. Vanished files flip to
  `status="missing"` and are NEVER dropped.
* Verification tiers (owner-specified): files <50MB are re-hashed on verify;
  >=50MB are verified by size+mtime. Every copy is hashed during the copy pass itself.
* Sources are strictly read-only, with ONE owner-approved exception:
  `D:/codex-sessions-archive-20260621` is same-volume **renamed** into
  `D:/agent-sessions-vault/stores/codex-archive-20260621` (no bytes copied, tree intact).

## Usage

```bash
python tools/sessions-vault/agent_sessions_sync.py sync            # incremental sync
python tools/sessions-vault/agent_sessions_sync.py sync --dry-run  # preflight only
python tools/sessions-vault/agent_sessions_sync.py sync --stores codex-live,claude-code
python tools/sessions-vault/agent_sessions_sync.py verify          # zero-loss proof pass
```

`stores.yaml` fields: `id`, `tui`, `path` (or `files` pipe-list), `mode`
(`tree|accepted|accepted_top|accepted_top2|files|move`), optional `prune` (comma list),
`walk` (for move stores). Store order = dedup priority.

## Vault layout

```
D:/agent-sessions-vault/
  manifest.jsonl        # one line per source file (schema fixed; see agent_sessions_sync.py)
  stores/<store-id>/…   # content, relative paths preserved
  state/state.json      # incremental cache   state/last-run.json  # run stats
  logs/sync-current.log # streaming progress
```

Cross-references: the store registry reconciles with
`tss/tsis-deepdive/corpus/build_corpus.py` ROOTS (control enumeration) and
`ai-sessions-render/llm_anthology/discover.py` PROVIDERS — see the audit artifact
`out/harness-audit-2026-10-18/sessions-vault.md` for the discrepancy table.