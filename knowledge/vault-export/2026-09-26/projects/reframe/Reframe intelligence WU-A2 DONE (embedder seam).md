---
title: Reframe intelligence WU-A2 DONE (embedder seam)
type: note
permalink: main/projects/reframe/reframe-intelligence-wu-a2-done-embedder-seam
tags:
- reframe
- intelligence
- milestone
- embedder
---

# Reframe intelligence WU-A2 — DONE (2026-06-20)

Branch `feat/intelligence-design`, commit `bddcae1` (pushed, on top of e69ffc0 WU-A1).

## What (G-A1, embedder seam — feeds G-A3/WU-A4/A5)
NEW module `sidecar/media_studio/models/embedder.py` (PLAN picked NEW module over extending provider.py to keep the chat transport untouched):
- `Embedder` runtime-checkable Protocol: `embed(texts) -> list[list[float]]`.
- `EmbedderError(RuntimeError)` typed error.
- `CloudEmbedder`: OpenAI-compatible `POST {base_url}/v1/embeddings`, body `{input:[...], model}`, parse `data[].embedding`. stdlib urllib only, injectable 4-arg `Transport` (same shape as provider.Transport) so tests never open a socket. Empty input → `[]` with NO transport call. HTTP/parse/shape errors → typed `EmbedderError` (count-mismatch guard incl.). Default transport = `functools.partial(_urllib_post_json, secrets=(api_key,))` — mirrors provider.py so the ONLY uncovered line is the real socket (`# pragma: no cover`); NO closure-body line to leave uncovered (initial closure version left line 190 uncovered → switched to partial).
- `LocalEmbedder`: deterministic socket-free backstop (sha256 bag-of-words hashing into `dim`=384 buckets, unit-normalized, empty text → zero vector). Privacy/offline floor; WU-A3 pins the real local embedding asset as the upgrade.
- `get_embedder(settings, transport=)` factory: Cloud when useCloud+cloudApiKey else Local (mirrors provider.get_provider fall-through). Reads `cloudEmbedModel`/`cloudBaseUrl`.

Tests: new `test_embedder.py` (23) — AC(a) one POST + parse, AC(b) empty no-call, AC(c) typed errors (transport/missing-data/non-list/non-object/non-list-embedding/non-numeric/count-mismatch), AC(d) 100%; + local determinism/norm/zero, Protocol conformance, factory routing.

## Scope note
Cloud egress consent+budget gating is composed UPSTREAM in handlers (WU-A1 `_text_consented_settings` + `_enforce_cloud_budget_ack`) at WU-A5; this module is purely transport+parse+local-fallback, no consent/budget logic itself.

## Gates
- embedder.py 100% line+branch (82/0/22/0). Full sidecar suite 3142 pass, 100.00% total (128s).
- ruff check+format clean; basedpyright 0/0/0 on changed files; pre-commit (ruff/gitleaks) Passed, oxlint/biome skipped (no renderer files).
- Renderer untouched (sidecar-only WU) → RENDERER_COV N/A.

## Env gotcha (next Windows agent)
The Bash tool runs in a DIFFERENT WSL filesystem than the real WSL — `/tmp/msv/bin/python` exists ONLY via `wsl -e bash -lc '...'`, not in the Bash tool's `/tmp`. Run all sidecar gates via `wsl -e bash -lc 'cd /mnt/c/.../sidecar && /tmp/msv/bin/python -m pytest ...'`. basedpyright = `/tmp/msv/bin/basedpyright` (not on non-login PATH). pre-commit = `/tmp/msv/bin/pre-commit`; commit needs `export PATH=/tmp/msv/bin:$PATH` so the hook finds it.

## Next
WU-A2 (with A1/A3/A4) converges at WU-A5 (`index.*` handlers): A5 reuses `embedder.embed` for the build job + the inline search query embedding.
