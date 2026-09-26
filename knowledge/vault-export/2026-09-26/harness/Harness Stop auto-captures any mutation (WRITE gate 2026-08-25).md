---
title: Harness Stop auto-captures any mutation (WRITE gate 2026-08-25)
type: guide
permalink: main/harness/harness-stop-auto-captures-any-mutation-write-gate-2026-08-25
tags:
- harness
- basic-memory
- hooks
- stop
- spool
---

valid_as_of: 2026-08-25

## Landed
Shared `RecallModule` + `ClaimWarningModule` (not Grok-only):
- READ: vault digest on SessionStart AND first UserPromptSubmit with **split markers** (`-ss` vs `-up`) so Grok dropping SessionStart stdout cannot mute the portable first-prompt path.
- WRITE: Stop spools a session note when **any** file mutation happened and this session did not `write_note`. Hook-owned spool at `state/bm-spool/<session>.json`; CLI flush is best-effort and skipped under pytest. SessionStart retries unflushed spool.
- Tests: `test_recall_first_prompt_injects_digest_even_after_session_start`, `test_basic_memory_nudge_fires_on_any_mutation_and_spools_note`, `test_recall_session_start_retries_unflushed_spool` + FIX-N suite green.

Do not Exit 2 on missing vault. Do not add mem0.
