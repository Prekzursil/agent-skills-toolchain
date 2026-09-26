---
title: BC bc-offsets resilience build complete + 15.4.1 handled 2026-06-11
type: note
permalink: main/checkpoints/bc-bc-offsets-resilience-build-complete-15.4.1-handled-2026-06-11
tags:
- battlecats
- bc-offsets
- 15.4.1
- resilience
- checkpoint
- reverse-engineering
---

# BC bc-offsets resilience build COMPLETE + 15.4.1 handled — 2026-06-11

Repo: `D:/ReverseTools/Android/battlecats-toolkit` (branch ralph-hardening). Commit **ff30cc4**.

## bc-offsets resilience system — BUILT, VERIFIED, COMMITTED
The update-resilience architecture (designed + gated earlier: 5-agent design gate, 3-agent plan gate x2, plan v3) is now fully built (was cut off mid-build; I completed WU8 canary + integrated + committed this session):
- `tools/offsets/`: `schema.py` + `bc_offsets.py` loader (**verified-gates-writes**: `static` offsets refuse writes via `.off()` until `bc_confirm` flips them to `frida`; reads ungated; `NullOffset` for live-only) + `bc_confirm.py` state machine + manifests `en-15.3.0/15.4.0/15.4.1.json`.
- `tools/frida-trainer/bc_offsets.js`: thin runtime verifier (live getGlobal-fingerprint check) + **node CLI** (`node bc_offsets.js <live> <expected>` -> {ok,reason}); `bc_offsets_inject.py`: host `%PLACEHOLDER%` injection seam; `bc_canary.py`: fail-closed canary controller (fatal/missing-handshake = hard abort; I wrote this from its TDD test, 100% cov).
- Migrated BOTH trainers (`bc_battle_trainer_agent.js` + `bc_battle_trainer_mod_agent.js`) + hosts + divergent tools (speed_probe/outbreak_clamp/stage_unlock) to read offsets from the manifest; reconciled guard tests; gated the no-15.4-source code_sites (RA_RENDERER/FORGE/LISTBUILDER, OUTBREAK_ANCHORS, CAP_PATCH_RVA).
- `signature_rediscovery.py` generalized (manifest-derived sigs + SPEED disp32 decode). `bcsfe_loader.py` warn-on-fallback.
- VERIFIED: coverage gate **100%** (297 tests, 8 modules) + 403 frida-trainer/offsets/signature + 14 JS + 12 bcsfe_bridge. `.coverage-thresholds.json` rewritten (multi-cov, includes bc_canary).
- Excluded from commit (per rules): `tools/frida-trainer/bc_adb_device.py` (other session WIP), `saves/`, `tools/save-tools/_workspace/`.

## 15.4.1 HOTFIX — handled as a pure data refresh (the architecture's first live win)
Device auto-updated to **15.4.1** (versionCode 1504010). Probed: the 15.4.1 `.so` (D:/ReverseTools/Android/BattleCats/apk-15.4.1/...) has **same size 12666808** but **different build-id d907e66ecce8388948f9ff4cde96a93735acbe92 + sha 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676**. ~221K bytes differ but ALL in data/string regions. **Per-function byte diff: EVERY trainer function body byte-identical to 15.4.0** (getCash/setCash/getCap/getWorker/setWorker/getCooldown/setCooldown/SPEED_fn/event-gates); wallet disp 0x23E0 count 319=319; getGlobal fingerprint 488d0599fe5b00c3 MATCH. So `en-15.4.1.json` = copy of en-15.4.0 offsets + new identity. The build-id canary correctly distinguishes builds (fail-closed on stale); the fingerprint verify confirms offsets hold. **No RE re-work needed for 15.4.1.**

## DEVICE GOTCHA
BlueStacks drops the adb bridge on app-update/restart -> `adb` shows no device. FIX = `adb connect 127.0.0.1:5555` (re-establishes). Then versionName/pull work.

## PENDING (device, was blocked on emulator-offline, now reconnected)
- **Save push (unlock+max all cats + equip best orbs on 179 cats)**: the combined edit is BUILT + verified on a copy (`tools/save-tools/{unlock_max_cats,equip_best_orbs}.py`, committed bd6c3d7/ba7a780; staged output SAVE_UNLOCK_MAX_ORBS_test.bin). Device now online -> do: force-stop BC -> pull FRESH 15.4.1 save -> backup -> apply edit -> push in-place -> relaunch -> re-event-unlock. Reversible via backup. User explicitly requested; confirm before force-stopping their live session.
- Optional: live frida-confirm flips 15.4.x offsets static->frida to write-enable the trainer (getGlobal first, poll/patchCode never per-frame hook).

## Prior docs (committed earlier this session)
bcsfe 3.4.0+orbs.2 (14e76ce); docs/game-knowledge/BC-15.4-ROSTER.md + BC-ORB-META.md (bcece90, orb doc CSV-corrected on 9 cats incl 71 Yukimura=Massive BLACK not Red). Relates to [[bc-15.4-bcsfe-3.4.0-upgrade-checkpoint-2026-06-10]].