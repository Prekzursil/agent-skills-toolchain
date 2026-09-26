---
title: Reframe intelligence WU-A3 DONE (index function + embedder asset)
type: note
permalink: main/projects/reframe/reframe-intelligence-wu-a3-done-index-function-embedder-asset
---

# Reframe intelligence WU-A3 — DONE (2026-06-20)

Branch `feat/intelligence-design`, commit `df7fa66` (pushed, on top of e485c81 WU-A2 fix).

## What
Made embeddings a first-class routable Hub function + pinned a local embedder asset (resolves G-A2 + G-A3 asset). SIDECAR-ONLY WU (no renderer).

- `presets.py`: added `"index"` to FUNCTIONS (text cap via `dict.fromkeys` default); `_FUNCTION_TASK_NAMES["index"]="MOMENT_FIND"` (reuses EXISTING Task — zero catalog.py edits); added explicit `"index":"cloudSafe"` to the `balanced` preset (privacy/bestFreeCloud get it free via `dict.fromkeys(FUNCTIONS,...)`).
- `manifest.py`: registered `all-minilm-l6-v2-onnx` (384-dim = `embedder.DEFAULT_LOCAL_EMBED_DIM`, Apache-2.0), `installer="download"`, PINNED url + sha256.

## Key facts / gotchas
- PINNED sha256 = `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452` (LFS oid of `sentence-transformers/all-MiniLM-L6-v2` `onnx/model.onnx`@main, 90,405,214 B). Verified via TWO endpoints (`/raw/main/` pointer + `/api/models/.../tree/main/onnx` JSON). AC-(c) requires NON-EMPTY sha — whisper(hf)/qwen(download) had none, so I used download+sha.
- **Downstream test ripple (not in PLAN's named files but REQUIRED):** adding to `FUNCTIONS` flows into the recommender's `perFunction` map (recommender uses `apply_preset`). `test_recommender.py` hardcoded a 5-tuple `_FUNCTIONS` → would fail the `set(...)==set(_FUNCTIONS)` shape assert. Fixed by making `_FUNCTIONS = presets.FUNCTIONS` (drift-proof). Also test_presets fake catalog needed an `"index"` grade per row (mirrors `select`/MOMENT_FIND) else cloud presets collapse index→LOCAL and break the `provider != LOCAL` loop assert.
- catalog.py `_tiers()` builds all 5 Task keys for every one of 13 rows, so `entry.per_task_tier[Task.MOMENT_FIND]` never KeyErrors — confirms the bracket-lookup-resolves anchor.

## Gates
- Sidecar 100% line+branch: PASS (3150 tests, 125s). presets.py 77/14, manifest via test_assets.
- ruff check + format: clean (no reformats). basedpyright: 0 errors (44 pre-existing missing-import warnings for cv2/torch/transformers, unrelated).

## Next
WU-A4 (`features/semantic_index.py` PURE: build_corpus + cosine search via existing `diarize.cosine_similarity`) — logic-independent of A1/A2/A3. Then WU-A5 (index.* handlers, dep on A1-A4).
