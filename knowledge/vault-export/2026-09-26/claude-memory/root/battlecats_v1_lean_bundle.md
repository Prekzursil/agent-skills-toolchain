---
name: battlecats-v1-lean-bundle
description: BC V1 'Lean Edition' modded-APK bundle — what's built, the toggleable-trainer
  config decision, companion architecture, and remaining follow-ups
metadata:
  node_type: memory
  type: project
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/battlecats-v1-lean-bundle
---

V1 "Lean Edition" of the personal BC EN 15.3.0 modded-APK is **built + signed** on branch `ralph-hardening` of `D:\ReverseTools\Android\battlecats-toolkit`. Save-compatible, installs alongside the stock pkg (renamed `jp.co.ponos.battlecatsen.unlock`), easy roll-forward on PONOS updates via the signature-rediscovery tool. (V2 "Definitive Edition" is a separate, NOT-yet-built track — its design still NEEDS-REVISION on 10 of 12 Codex blockers.)

**Three-layer delivery** (built by `tools/tbcml-bake/integrate.py`; APK is a gitignored regenerable artifact, NOT committed — only the manifest `reports/bc_bundle_build.json` is):
1. **APK** (`tools/apk-build/out/bc-15.3.0-bundle.apk`): bakes ONLY native patches + assets. Final build = 4 unlock gate-patches (`sub_819E20→1`, `sub_5F8DF0→1`, `sub_8A3350→0`, `sub_8A3520→1`) + Tinkerer Cat icon. apksigner v2+v3.
2. **`bundle-companion/`**: Frida agents loaded at runtime via the external harness (NOT baked in). 11 staged: battle_trainer + settings_panel (Cat Pawferences toggle host) + search_tooltips + 7 Wave 2 overlays (wallet_hud, unit_longpress_info, button_dedup, quick_restart, auto_equip, claim_all, officer_pass_refresh) + outbreaks_b2b.
3. **`bundle-runtime-data/`** (device-side push, NOT in APK): all-events `event_0.dat` (the data-only unlock — see [[battlecats-event-summoner]]), mod_settings.json, search_tooltips_data.json, cat_nicknames.json.

**UNIFIED LAUNCHER + IN-GAME CONTROL (built 2026-05-28, branch `ralph-hardening`):**
- `tools/companion-launcher/` — one-command harness (265+ tests). Reads `feature_modules.registry()`, starts frida-server, attaches to `.unlock`, loads companions in order (panel LAST). Profiles **`--clean`/`--qol`(default)/`--cheats`** = the integrity gate (data-driven: a companion is a CHEAT iff its JS emits `bc.cheats_dirty`, matched by regex). `--cheats` prints "do not play ranked". Guards: C7 `.so` fingerprint (size 12,641,624 + magic@0x653C80, NOT a SHA since device runs the patched .so), cleanup() orchestration on detach, process-death re-attach, cheats_dirty aggregation→runtime_state.json, manifest.lock drift check.
- **Cat Pawferences = 6-tab in-game panel** (`mod_settings_panel.js`): Looks/Comfort/Play/Boost/Workbench (Shenanigans hidden). Registry-driven rows. **Async cross-realm toggle bridge** (Frida scripts are isolated realms → host-mediated only): registration via rpc `registerToggles`; tap→`bc.toggle.set`→launcher→`setFlags`→`getFlags` confirm→`bc.bridge.update`→repaint; get=local snapshot; persist-on-confirm. Companions expose `toggleSurface()` (group=tab).
- **Robustness audit** (`docs/research/2026-05-28-v1-robustness-audit.md`, 8 CRIT guards) + **Claude peer review** (3 HIGH found+fixed: auto_equip defence-in-depth, panel waitForModule timeout, bridge persist-on-confirm). HGT-safety invariant verified: no companion writes save/clock/economy. Codex cross-model leg deferred (usage-capped to 2026-05-31).

**KEY DECISION — trainer is companion-only, NOT baked (`integrate.py --no-bake-trainer`).**
**Why:** user wants BOTH easy offline cheating AND clean online play (cheats must not count to score/achievements — the `cheats_dirty` integrity anchor). A baked-always-on trainer (getCap/getWorker/getCooldown patched into the `.so`) structurally can't be turned off → account always looks cheated online → defeats the clean-online goal. The `battle_trainer` companion hooks the same 3 getters (`0x37C230`/`0x37C470`/`0x37C700`) via setFlags/getFlags, so companion-only loses nothing and stays toggleable + integrity-gateable.
**How to apply:** keep `--no-bake-trainer` as the canonical V1 build flag. Do NOT re-bake the trainer unless the user explicitly wants always-on (then drop the flag). In-battle money/worker/cooldown only; persistent economy (catfood/tickets/gacha) stays untouched.

**Ring 3 cheats — reframed as toggleable Frida companions (NOT baked statics):**
- **no_energy_companion** ✅ READY — hook `sub_596440`@0x596440 onEnter args[1]=0 (HIGH-confidence RE, `docs/research/2026-05-27-ring3-offsets.md`). HGT-safe (energy@+0xBAC0 ≠ save-ts@+0x176E0).
- **auto_equip** ✅ READY (un-stubbed) — armed-getter `sub_378900`@0x378900 onLeave retval.replace(1) for OWNED slots only. **Save-corruption fail-safe PROVEN** (consume path `sub_5AC690` has no count>0 guard → defence-in-depth: agent refuses any slot without count>0). Arms the 6 battle ITEMS (not cats); spends them (default OFF).
- **treasure_3x_companion** 🔴 HELD — its effect persists to save (treasureData) = forbidden economy write; route to the BCSFE save editor instead, NOT a runtime cheat.
- **speed_up** ⏳ UNCONFIRMED — engine frame-tick is stripped statically (NOT Cocos2d-x); needs a device runtime trace (NO Stalker — hang history). Deferred.
- The old `dat-cache-decode/{no_energy,treasure_3x,speed_up,no_hgt}` Ring 3 STATIC modules stay no-op (a future baked-build option); `no_hgt` must NEVER static-patch `sub_525AB0` (drift check interleaved).

**Remaining (all device-bound — need Pie64 up):**
- **On-device validation**: smoke-gate (launcher attaches, panel renders, 1 toggle flips) → ≥3-toggle verify → settings round-trip across relaunch. V0-V5 + V4 redownload PASS already done (`a2e612e`); the bundle was rebuilt since, so re-deploy first.
- **button_dedup labels**: Frida capture got 11 ids+geometry (`captured_button_ids.json`, commit 38a451a) but NO label strings → can't map id→Cat Base/Equipment/Cat Capsule. Needs a label-resolving re-capture or tap-correlation on-device; hide-map stays empty until then (cosmetic).
- **speed_up runtime tick trace** (above).
- **logbook**: per-save runtime-regenerated (JS bakes save-derived clear-flags); generate at attach via `dat-cache-decode/logbook/cli.py --save … --catalog …`.
- **Codex cross-model review**: usage-capped to 2026-05-31; Claude review done.