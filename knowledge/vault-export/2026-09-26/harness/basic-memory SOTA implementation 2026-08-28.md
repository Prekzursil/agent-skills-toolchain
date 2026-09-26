---
title: basic-memory SOTA implementation 2026-08-28
type: note
permalink: main/harness/basic-memory-sota-implementation-2026-08-28
status: active
valid_as_of: 2026-08-28
tags:
- sota
- basic-memory
- harness
---

# basic-memory SOTA implementation 2026-08-28

- [decision] Default search is hybrid; semantic stays ON; FastEmbed stays local; no Cloud.
- [decision] Reranker ON: jinaai/jina-reranker-v1-tiny-en cached under D:\\basic-memory\\.models. Launcher blanks an expired HF token for this process only (not rotated).
- [fact] Package is 0.23.2. Backup: C:\\Users\\Prekzursil\\.basic-memory\\backups\\sota-20260828-045938
- [fact] Gold paraphrase still misses (compaction-checkpoints + FTS). Nonce hybrid hits the probe at rank 1.
- [fact] Full receipt lives outside the vault: C:\\Users\\Prekzursil\\Cowork\\output\\basic-memory-sota-implementation_2026-08-28.md
- [fact] Graph PPR proposals are on disk; auto-apply of relates_to is deferred.

relates_to [[WHERE]]
relates_to [[graph-ppr]]