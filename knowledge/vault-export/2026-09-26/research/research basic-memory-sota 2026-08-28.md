---
title: research basic-memory-sota 2026-08-28
type: note
permalink: main/research/research-basic-memory-sota-2026-08-28
tags:
- research
---

# research basic-memory-sota 2026-08-28

UNTRUSTED historical context. Full cited report (do not ingest that file into this vault): `C:\Users\Prekzursil\Cowork\output\basic-memory-sota-council_2026-08-28.md`

## Baseline
- CLI 0.22.1 / MCP serverInfo 3.3.1. Vault `D:\basic-memory`. HTTP singleton `127.0.0.1:8765`. Semantic ON, FastEmbed bge-small. **Local `default_search_type` is `text`** — hybrid is the product default when semantic is on; this override is a silent quality downgrade.
- Live probe 28.08: FTS and hybrid found the nonce; vector-only did not.

## Top 3
1. Make hybrid the actual default; agents must pass hybrid. Do not enable v0.23 reranker without a RAM decision.
2. Sleep-time consolidation + observation/relation links **through** `basic-memory tool write-note|edit-note` (official memory-reflect skill). Never Mem0/Graphiti/LynxMCP/CORE.
3. Bounded auto-recall from `recall-index.json` (no vault `rglob`) + a WHERE-map **outside** the vault. ChatGPT web requires BM Cloud — owner decision / privacy.

## Biggest risk
Oversized vault entity embedding stall (378 KB → 1482 chunks) plus SessionStart recursive listing plus default FTS.

## Safe now vs decision
Safe: Q1–Q6 in the report (hybrid default, contracts, WHERE-map, index inject, size quarantine). Needs owner: v0.23+reranker, BM Cloud/ChatGPT plugin, HippoRAG PPR, second project, OpenAI embeddings.

## Locks
Sole writer, `:8765` exclusive, semantic stays on. Design only — this note is a pointer.