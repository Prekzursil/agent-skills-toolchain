---
title: 'BC mega-program: trait/ability feature-vector (services/combat) + golden fixtures
  BUILT'
type: report
permalink: main/projects/bc-mega-program-trait-ability-feature-vector-services-combat-golden-fixtures-built
tags:
- battlecats
- trainer-gui
- mega-program
- feature-vector
- combat
- golden-fixtures
---

# BC mega-program WU-A1.4 — trait/ability feature-vector + golden fixtures

Built 2026-06-16 on `feat/mega-program-v1` worktree `D:/ReverseTools/Android/bc-toolkit-build-wt`. TDD, 100% line+branch, import-safe without PySide6, ruff-clean.

## Key load-bearing finding
The committed `unit_stats_15.3.0.json` bundle has **ZERO trait/ability columns** (verified: full key-union across all 861 = hp/atk/foreswing/area/ld/cost only — no `target_*`, `strong`, `massive`, slayers, immunities). So the **cat feature-vector MUST parse raw `unitNNN.csv`** from `C:/Users/Prekzursil/Documents/bcsfe/game_data/en/15.3.0/DataLocal`. The **enemy side is fully in `enemy_db` bundle** (enemy_data.py already maps all traits + cols 20-103 abilities). Don't expect cat trait flags in the bundle.

## What was built (greenfield services/combat/)
- `ability.py` — unified vocabulary: `Trait` (12 traits + Colossus/Behemoth/Sage classes), `AbilityKind` (~50 kinds), `AbilityBucket`, `BUCKET_OF` map, + hardcoded multiplier tables `ANTI_TRAIT_MULT` (base/full treasure) & `SLAYER_MULT`.
- `cats.py` — `parse_cat_capability(cat_id, form, int_row) -> CatCapability`; mirrors `enemy_data.parse_enemy_stats`. Column map = CONFIRMED tbcml (verified all indices match: target_red=10, target_floating=16, strong=23, massive=30, colossus=97, behemoth=105, sage=111, witch_killer=53, eva_killer=77; immunities 46-51/75/79/90/91/116). Applies col-63 `attack_1_use_ability` default=1 (get_required). Signed ld_range = Omni Strike.
- `feature_vector.py` — `resolve_counter(CatCapability, EnemyProfile) -> CounterEffect`. Anti-trait mult applied ONCE on target∩enemy match (NOT per-trait); slayer is flat class-axis (NOT trait-gated); trait×slayer compose multiplicatively (exposed separately + composed). Gates: metal (non-crit clamp, crit/metal_killer offense), zombie-revive denial, barrier-break, shield-pierce, control-immunity. `enemy_profile_from_db(entry, extra_classes=)` adapts the enemy_db dict (Colossus/Sage supplied via extra_classes — they live in the unmapped enemy tail, NOT the trait map; Behemoth IS mapped at enemy col 101).

## Multiplier constants (full treasure, from wiki/mech docs)
strong 1.8/0.4, massive 4.0, insane 6.0, resistant -/0.20, insanely_tough -/(1/7); slayers: colossus 1.6/0.7, behemoth 2.5/0.6, sage 1.2/0.5, witch_killer 5.0/0.1, eva_killer 5.0/0.2.

## Gotcha
`target_witch` (col 54) & `target_eva` (col 76) have **0 carriers in 15.3.0** — the witch_killer(53)/eva_killer(77) flag itself does targeting+multiplier. Treat killer flag as the canonical witch/eva counter.

## Deliverable 2: golden_counter_fixtures.json
`tools/trainer-gui/tests/fixtures/golden_counter_fixtures.json` — **48 cases, 19 families** (all 12 traits + Colossus/Sage/Behemoth slayer + Immunity + Area + LongRange + Barrier). Built by `build_golden_counter_fixtures.py` which parses real on-disk CSVs via `parse_cat_capability` and **self-validates every expected_effect through resolve_counter** (loud build — can't drift). Committed `computed` block per case = regression guard. Real named cats (Axe Cat 2, Bath Cat 40, Wyvern 119 colossus, Bean Cats 123 behemoth, Crane 135 sage, Madoka 288 witch_killer, Kaworu 405 eva_killer, etc.).

## Tests
`tests/services/combat/` — 64 tests, 100% line+branch on all 4 combat modules. `test_golden_counter_fixtures.py` re-runs the fixture against the resolver (skipif DataLocal absent).

## Env note
PySide6 NOT installed in the build env — the package-wide `--cov=trainer_gui --cov-fail-under=98` gate can't run here (GUI tests fail Qt import). The pure data layer (combat) runs & 100%-covers independently, which is the scoped requirement. CI with PySide6 must run the full gate.
