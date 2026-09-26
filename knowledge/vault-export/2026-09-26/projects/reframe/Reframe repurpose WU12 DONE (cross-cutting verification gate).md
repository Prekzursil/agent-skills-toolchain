---
title: Reframe repurpose WU12 DONE (cross-cutting verification gate)
type: note
permalink: main/projects/reframe/reframe-repurpose-wu12-done-cross-cutting-verification-gate
---

# Reframe repurpose WU12 — DONE (2026-06-20)

Branch `feat/repurpose-design`, commit `0dba263` (pushed; 83f7a18..0dba263).

WU12 = cross-cutting verification + PR-readiness GATE WU (no feature source; PLAN §WU12 = "No new source; CI/verification only"). All WU1-WU11 already committed. Commit adds only `docs/plans/repurpose/WU12-VERIFICATION.md` recording the falsifiable-acceptance gate results.

## Gate results (all green)
- Sidecar: `pytest --cov=media_studio --cov-branch --cov-fail-under=100` → 3256 passed, TOTAL 100% line+branch. Three new modules: batch.py 370/120, export_presets.py 130/30, templates.py 123/46 (zero misses).
- Renderer: `vitest run --coverage` → 100% stmts/branches/funcs/lines (8290/8290, 2836/2836, 514/514).
- ruff check + ruff format → clean; basedpyright media_studio → 0 errors (30 pre-existing torch/transformers missing-import WARNINGS in unrelated ML backends, CI bare basedpyright exits 0).
- tsc app + render-cli → clean; biome 2.5.0 FORMAT (format-only; biome.json linter.enabled=false) → 163 files, no fixes; oxlint --deny-warnings → clean.
- Invariants: handlers.py diff = only the 3 module register() blocks + _video_title title-seam helper, no provider/key wiring (single RPC site holds); grep Provider/api_key/_run_ai_job/os.environ/getenv over the 3 new modules = ZERO.

## GOTCHAS for next Reframe Windows agent
- ⭐ **Windows `core.autocrlf=true` breaks `biome format`**: it reports CRLF diffs (163 "errors") on a normal clone even though committed code is LF. CI on Ubuntu (LF) passes. FIX = clone with `git -c core.autocrlf=false clone ...` to get a pristine LF working tree, then biome-format = "no fixes applied". Toggling autocrlf on an existing clone churns the whole index — don't; just re-clone clean.
- Sidecar env (matches quality.yml): `py -3.12 -m venv`; `pip install ruff==0.15.17 basedpyright==1.39.8 pytest pytest-cov`; `pip install -e sidecar[dev] --no-deps`; `pip install httpx numpy opencv-python-headless`. Heavy ML deps (faster-whisper/torch/scenedetect/onnxruntime) intentionally NOT installed — tests are heavy-ML-free via fakes.
- biome.json + .pre-commit-config + .oxlintrc live at REPO ROOT (not app/); biome file glob = `app/(main|renderer/src|render-cli/src)`. The real lint gate is `biome-format` (linter disabled) + `oxlint --deny-warnings`, NOT `biome check`.
- No local .git/hooks/pre-commit in fresh clone; pre-commit enforced only in CI (`pre-commit run --all-files`).

Repurpose bundle (WU1-WU12) now fully complete on feat/repurpose-design. Next: PR creation / self-reflect per metaswarm pre-PR knowledge capture.
