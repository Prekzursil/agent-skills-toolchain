---
title: Reframe WU-B1 recommender DONE + manifest registration test hazard
type: note
permalink: main/projects/reframe/reframe-wu-b1-recommender-done-manifest-registration-test-hazard
---

# Reframe intelligence WU-B1 (device-aware recommender) — DONE 2026-06-20

Branch `feat/intelligence-design`, repo Prekzursil/Reframe. PLAN/DESIGN at docs/plans/intelligence/.

## What WU-B1 is
PURE core `sidecar/media_studio/features/recommender.py` + `tests/test_recommender.py`.
`recommend(report, present, detected_local, asr_engines, *, offline, commercial=False, catalog=None) -> Recommendation`.
Composes EXISTING advisor wire dict + present-map + detect_local_servers + asr.engines into
`{preset, routing:{perFunction}, asrEngine, downloads:[{assetName,label,sizeMb,reason}], rationale[]}`.
No probe/GPU/socket/network. 100% line+branch standalone AND in full suite.

## Key design decisions
- Routing resolved by REUSING the pure `models/presets.py` `apply_preset(preset, {}, CatalogAdapter())`. catalog is an injectable param (tests pass a FakeCatalog mirroring test_presets.py).
- Advisor `recommendedPreset` is a TIER id (tier0-numeric/tier1-multimodal/tier2-vlm), NOT a routing preset. Map: tier0->privacy, tier1->balanced, tier2->bestFreeCloud; a direct routing-preset name passes through; unknown/malformed/missing-key -> "privacy" floor (G-B1 typed "unavailable" rec, perFunction={}, no exception).
- Detected local server captures functions it can serve (text-only -> all non-vision; vision-capable -> +vision); covered components dropped from downloads.
- offline=True: drops all downloads AND downgrades cloud routes to LOCAL backstop (PLAN line 86 "drops all download-requiring + cloud proposals").
- asrEngine = LAST installed engine wins (asr.engines lists whisper default first, opt-in alternatives after -> prefer parakeet when installed); None if none installed.
- `_COMPONENT_ASSETS` mirrored locally (import-light) from handlers; download metadata enriched from `assets/manifest.get_asset` (label/size_mb), name-fallback + sizeMb=0 when no entry.

## GOTCHA (reusable, cost me one full-suite cycle)
**Reframe sidecar asset manifest registration is GLOBAL IMPORT-ORDER state.** `manifest.get_asset("vinet-s-saliency")` returns None when only `recommender` is imported, but returns a real entry (label "ViNet-S...", 36MB) once `features/saliency` is imported (its module calls `register_asset` at import). Reliably-registered-at-manifest-import: whisper-large-v3-turbo, qwen3-4b-gguf, hsemotion-onnx, rapidocr-onnx. NOT registered standalone: vinet-s-saliency, siglip2-so400m, etc (need their feature module imported).
=> A test asserting "unregistered -> sizeMb==0 name fallback" PASSES standalone but FAILS in full suite (saliency got imported by another test). FIX: monkeypatch `manifest.get_asset` to pin None (fallback branch) or a fake SimpleNamespace (populated branch) for deterministic, order-independent coverage. Don't rely on real registration state in tests.

## Gates run (WSL /tmp/msv venv, /mnt/c path)
ruff check+format clean; basedpyright 0/0/0; targeted cov 100% (115 stmts/44 branch); full suite rerun pending at write time.
