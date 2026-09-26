---
title: Reframe intelligence WU-A4 DONE (semantic_index PURE core)
type: note
permalink: main/projects/reframe/reframe-intelligence-wu-a4-done-semantic-index-pure-core
---

# Reframe intelligence WU-A4 — DONE (2026-06-20)

Branch `feat/intelligence-design`, commit `b6c9c29` (pushed, on top of df7fa66 WU-A3).

## What
`features/semantic_index.py` PURE core (G-A: semantic search math half). NEW files only; SIDECAR-ONLY (no renderer).
- `build_corpus(transcript) -> list[str]`: `str(seg.get("text",""))` over `transcript.get("segments") or []`; corpus length always == segment count.
- `search(query_vec, segment_vecs, segments, top_k) -> list[Hit]`: cosine via EXISTING `diarize.cosine_similarity` (imported `from . import diarize`, referenced as `semantic_index.diarize.cosine_similarity` so tests can monkeypatch); stable sort desc on score (ties keep source order → lowest-index-first); `top_k<=0 -> []`; `zip(strict=False)`; dimension mismatch propagates cosine_similarity's ValueError (NOT re-guarded).
- `Hit` TypedDict: segmentIndex/start/end/text/score.

## Gates
- Module 100% line+branch (24 stmts, 4 branch, 0 miss), 15 tests.
- Full sidecar suite: 3165 passed, 100% line+branch TOTAL (134s).
- ruff check + format: clean (no reformats). basedpyright: 0 errors/warnings on new files.

## Gotchas
- `diarize.cosine_similarity` is length-guarded (diarize.py:75) and returns 0.0 for zero vectors — reused directly, no math re-derived.
- Monkeypatch the spy at `semantic_index.diarize.cosine_similarity` (module-object attr), not `diarize.cosine_similarity` global.

## Next
WU-A5 (`index.*` handlers + RPC reg in register_all + sidecar persistence `projects/<videoId>.index.json`; dep on A1-A4). index.build = long job; index.search/status = direct-return; search egress gated by WU-A1 text-consent + budget ack.
