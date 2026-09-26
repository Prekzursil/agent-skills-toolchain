---
title: BC Phase-5 DELIVER save-grant delivery (WU complete)
type: note
permalink: main/projects/bc-phase-5-deliver-save-grant-delivery-wu-complete
tags:
- battlecats
- phase-5
- de-gacha
- save-grant
- work-unit
---

# BC Phase-5 DELIVER — save-grant DELIVERY (the de-gacha keystone)

Built 2026-06-20 on `D:/ReverseTools/Android/bc-toolkit-build-wt` (HEAD a311981), no commit.

## What it is
DELIVER = the P1/P5 FALLBACK that makes a de-gacha unlock/form stage actually GRANT
the cat/form into the save — probe-INDEPENDENT + HGT-safe (spec §7C "save-grant always works").

## Files (NEW + 1 SHARED)
- `tools/trainer-gui/trainer_gui/services/data/grant_resolver.py` (NEW, 92 stmts/10 branch, 100%)
- `tools/trainer-gui/tests/services/data/test_grant_resolver.py` (NEW, 24 tests)
- `.coverage-thresholds.json` (SHARED — one additive DELIVER key under `files`)

## Architecture (reuses W-A + W-D verbatim, forks neither)
Sits BETWEEN W-A stage_emitter (`EmittedStage.drop_chara/reward_materials/form`) and
W-D safety_harness (`EditSet`/`apply_editset`). Pipeline:
`cleared stage_id -> build_grant_index(EmitResult)[mapid] -> GrantSpec -> grant_to_editset -> deliver_grant routes clone->apply->HGT-detect->diff`.
- unlock stage -> CAT_UNLOCK -> one `cat.owned` op
- form stage -> FORM_UPGRADE -> one `material.amount` op per (item,amount) + one `form.flag` op
- EVERY op `forced_field_write=False` (G-8 HGT-safe staged path; Aku-altar class structurally unreachable)
- live BCSFE save-write = injected `applier` SEAM (the # pragma device boundary); tested over fixture saves with a BCSFE-free fixture applier (save GAINS the cat after a fixture clear).

## Key facts / gotchas
- W-D `_verdict_for_op` routes ONLY upgrade.base/plus, material.amount, talent_np_total, treasure, orb_id. My `cat.owned`/`form.flag` are OPAQUE -> SAFE-but-recorded; `material.amount` runs the live R5 band. Independently PROVEN: forced-write trips, negative material trips, safe grant passes.
- `GrantEditOp` subclasses `safety_harness.EditOp` (slotted frozen) + adds `after_material_id` for the per-item material id (harness EditOp keys per-cat only). Harness predicate ignores the extra field.
- FAIL-LOUD: GrantResolverError (bad emitter kind at index), UnknownStageError (clear of a non-emitter stage).
- DEVICE-DEFERRED: native unlock-grant (P1) + native form-grant (P5) are the device-enhancement tiers DELIVER is the fallback FOR; only the live save-write transport is device-bound.

## SHARED-WORKTREE CONTAMINATION (live during this WU)
Parallel sibling agents had uncommitted files in the same worktree (stage_marquee, dojo_authoring, offline_runtime, build_recipe, service/cli.py) AND had already edited `.coverage-thresholds.json`. My DELIVER entry is purely additive (separate key), coexists with their MARQUEE entry, no clobber. Made NO commit -> orchestrator reconciles. Em-dash/§ in my entry are clean UTF-8 (the â€"/Â§ seen was console-codec rendering, not file corruption).
