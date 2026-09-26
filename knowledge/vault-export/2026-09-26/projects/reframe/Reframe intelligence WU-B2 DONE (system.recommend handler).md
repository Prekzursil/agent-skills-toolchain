---
title: Reframe intelligence WU-B2 DONE (system.recommend handler)
type: note
permalink: main/projects/reframe/reframe-intelligence-wu-b2-done-system.recommend-handler
---

# Reframe intelligence WU-B2 — DONE (2026-06-20)

Branch `feat/intelligence-design`, commit **ef3c214** (pushed). WU-B2 = `system.recommend` handler + RPC registration (metaswarm IMPLEMENT+VALIDATE).

## What
- New `Services.system_recommend({commercial?}) -> {recommendation:{...}}` (DIRECT-return, ZERO provider calls). Composes existing cheap probes: `system_advisor.advise_for_hardware` (wire'd via `_advisor_report_to_wire`) + `_models_present_map` + local-server detect + `asr.engines`, then runs PURE `recommender.recommend` (WU-B1) over them. Forwards `offline` from `offline.is_offline(settings)` and `commercial` from params (default settings.commercial).
- New helper `Services._detect_local_servers(settings)` + new constructor seam `local_detector` (tests inject canned PoolEntry dicts; default = real `local_detect.detect_local_servers` over `provider.urllib_get_json` GET transport). Returns `[]` fail-open.
- Registered `reg("system.recommend", svc.system_recommend)` in `register_all` (handlers.py, after system.advisor).
- Tests: `sidecar/tests/test_handlers_recommend.py` (8 tests): registration, envelope shape, probe-forwarding spy, offline=True passthrough, commercial-from-settings, G-B1 unavailable (monkeypatch `_advisor_report_to_wire` to drop recommendedPreset → no crash), zero-provider-calls (ExplodingProvider), default-detector-uses-urllib (fake GET transport).

## Gotchas
- `detect_local_servers` returns `list[PoolEntry]` (TypedDict, INVARIANT) → basedpyright `reportReturnType` vs `list[dict[str,Any]]`. Fixed with `cast("list[dict[str, Any]]", ...)`.
- `advise_for_hardware` ALWAYS sets `recommended_preset` → can't trigger recommender's G-B1 unavailable via probe alone; must monkeypatch the wire helper.

## Gates (all PASS)
SIDECAR_COV 100% line+branch (handlers.py 893/156, 0 miss; full suite 3024 passed). RENDERER_COV N/A (sidecar-only WU). ruff check+format clean, basedpyright 0 errors, pre-commit (ruff/oxlint/biome/gitleaks) pass.

## Next
WU-B3 = renderer recommendation card in ModelsSystemPanel.tsx (Apply via existing applyPreset/setFunctionModel/settings.set/assets.ensure). Clone path was `C:\Users\Prekzursil\AppData\Local\Temp\wu-b2-1781966693\Reframe`. WSL gate: `cd /mnt/c/.../sidecar && /tmp/msv/bin/python -m pytest --cov=media_studio --cov-branch --cov-fail-under=100 -q`.
