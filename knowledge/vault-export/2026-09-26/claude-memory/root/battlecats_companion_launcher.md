---
title: battlecats_companion_launcher
type: note
permalink: main/claude-memory/root/battlecats-companion-launcher
---

# BC Companion Launcher (tools/companion-launcher/)

BUILT 2026-05-28 on `ralph-hardening`. Core: d2efada/d8332e7/eed289d (session-hold fix). AUGMENT (audit-assigned launcher guards): 6b6e87e C7-fingerprint, 600d022 manifest+deploy-force-stop, 7a40fa5 C6/C2/C1, 99894c4 watcher+aggregation, 467a753 classifier-emission-fix, b134d65 toggle-registration leg1. One-command Frida launcher for the bundle companions. 265 tests, 99% cov, frida+adb fully mocked (frida NOT installed on host — backend lazily imports it so the package imports/tests clean).

## Panel<->companion toggle bridge (toggle_bridge.py)
The launcher is the ONLY thing that can bridge isolated Frida script realms (panel + each companion are separate scripts in one session). THREE legs were specified:
- **Leg 1 REGISTRATION (DONE b134d65):** call each companion's `toggleSurface()` rpc → map to panel's registerToggles fields (key,label,group,order,hgt_class,default,onFrame,offFrame,donorButtonId — DROP flagKey/getExport/setExport the panel ignores) → call panel's `registerToggles(provider,descriptors)` (mod_settings_panel.js:936). Plain rpc, no realm problem. Panel renders live rows. Crash-isolated per companion; panel excluded as host.
- **Legs 2 (tap relay) + 3 (initial state) BLOCKED by panel-side contract gap (reported, NOT built):** panel `handleTap` (lines 795-822) calls `desc.set()` SYNCHRONOUSLY in-realm via `global.__BC_PROVIDER_BRIDGE[provider]` and emits NO outbound tap message; `registerToggles` proxy does synchronous `get` (can't round-trip to another realm); panel names `mod_settings_host.py` (doesn't exist) as the bridge wirer but exposes NO install API (no installBridge rpc, no recv handler). Two options handed to B2: (1) panel adds installProviderBridge rpc + posts `bc.toggle.set` on tap + recv snapshot for get; (2) all-recv: `bc.bridge.install`/`bc.bridge.update` + `bc.toggle.set`. B2 picks.
- **CONTRACT MISMATCH found (Gap B, reported not fixed):** companions emit group `'Comfort'`/`'Play'` (capital) but panel TABS are lowercase `'comfort'`/`'play'` (no normalization, exact match line 427) → rows orphan from visible tabs. Launcher WARNS (relays verbatim); case decision is H<->B2's. Also: trainer provider = `bc.battle_trainer_mod`, others `bc.<module>` — B2's bridge API must key on emitted provider strings, not module ids.
- **What leg 1 achieves (precise):** panel rows render structurally with honest-false state; tapping does nothing functional yet (the in-realm bridge `desc.set()` calls is unpopulated — the documented wireTrainer honest-false fallback). Do NOT claim "toggles drive companions".
- **GENERAL LESSON:** host-mediated relay is feasible only for ASYMMETRIC pure-host-pull (registration via rpc, cheats_dirty via the agent's send→host→panel.post). It is NOT feasible for synchronous in-realm reads or for taps with no outbound signal. Verify the message direction + sync/async shape in the consumer's source before assuming a relay can bridge it — symmetry with an existing bus (cheats_dirty) does NOT imply the reverse direction exists.

## Launcher-owned guards (from V1 robustness audit)
- **C7 fingerprint (fingerprint.py)**: before loading ANY agent, probe maps libnative-lib.so size (12,641,624) + 8-byte magic at getGlobal 0x653C80 (488d05a9385c00c3, unpatched stable prologue). Mismatch → FingerprintStaleError → exit 1 "re-RE the .so". NOT a full SHA (device runs patched .so). Update = edit 4 constants. All agents share hardcoded RVAs; one PONOS update breaks all → launcher must gate.
- **manifest (manifest.py + manifest.lock.json + gen_manifest_lock.py)**: sha256 drift check vs lock; advisory warning (not the hard gate). Regenerate lock after intentional agent edits. NOTE: under concurrent agent edits the lock goes stale repeatedly — regenerate right before commit; tests must NOT couple to live-tree match (use fixtures + gen_manifest_lock.py --check for CI).
- **C6 (runtime_data.py)**: idempotently stage mod_settings.default.json to .unlock files dir if absent (push /sdcard → su cat> → chown app-uid + restorecon). Only when panel in set.
- **C2 cleanup (session._cleanup_all)**: call each loaded agent's cleanup() export (format-agnostic exports_/exports) BEFORE detach; isolated per-agent. C1 setHideMap (hidemap.py): push CONFIRMED hide-map to button_dedup; unconfirmed today → no-op (never activate unverified).
- **watcher+reattach (session.run_session_with_reattach)**: session.on('detached'); 'process-terminated'→reattach (cap 3, backoff, FRESH C7 each time); wake threading.Event coordinates with hold so Ctrl-C wins. cheats_dirty aggregation (aggregation.py): dedupe by (source,key) per audit M2, atomic write runtime_state.json (gitignored, NOT /data/local/tmp per M5), relay to panel via script.post (panel's recv('bc.cheats_dirty')).
- **deploy force-stop fix**: _run_deploy force-stops .unlock before+after push_event0.py (helper only stops STOCK pkg).

## globalThis resolvers — NOT feasible from launcher (KEY ARCHITECTURE FINDING)
Frida gives each script its OWN globalThis realm — a launcher CANNOT share a global across agents. The audit's named bridges (__BC_TRAINER_BRIDGE, __BC_PROVIDER_BRIDGE, __bcTrainerReadWallet, __BC_MOD_SETTINGS_PATH) are agent-CONSUMED in the agent's own realm; the setters (__bc*Set*, __bcQuickRestartReset) are agent-EXPORTED. Cross-realm = host-mediated message passing (script.post/recv), which is exactly the cheats_dirty relay. Remaining bridges need per-script bootstrap injection or a dedicated relay loop = scoped follow-up, NOT launcher-sized.

## CLI surface
`python -m companion_launcher [--clean|--qol|--cheats] [--spawn] [--deploy] [--dry-run]` (+ `launcher.cmd` wrapper). Profiles ARE the launch-level cheats integrity gate: clean=load nothing, qol=non-cheats only (DEFAULT), cheats=everything+loud warning. `--dry-run` = no device IO (the demo path). Exit codes: 0 ran, 1 bad-args/preflight-block/deploy-fail, 2 SessionError.

## Cheat classification is DATA-DRIVEN (no hardcoded list)
A companion is a CHEAT iff: (1) its agent JS EMITS `bc.cheats_dirty` — matched by EMISSION PATTERN `send({type:'bc.cheats_dirty'...})` via regex, NOT bare substring — OR (2) its feature_module notes contain `cheat-class`. Reclassifying = one-line edit IN THE COMPANION, never launcher code.
- **Now (after hardening agent's C4 landed):** `battle_trainer` AND `no_energy_companion` classify CHEAT (both emit). `settings_panel` = QoL (it only `recv()`s the signal as the toggle HOST).
- **BUG FOUND+FIXED (467a753):** original bare-substring matcher flagged settings_panel as CHEAT (its source REFERENCES the marker via recv/log) → wrongly EXCLUDED it from default --qol → broke in-game toggle UI. Fix = match `send(...'bc.cheats_dirty'...)` emission, not substring. LESSON: when an integrity classifier keys on a string, a sibling that RECEIVES/logs that string is a false-positive trap; key on the emission verb (send) not the token. The earlier "conservative false-positive is safe" claim was WRONG once the panel legitimately contained the string.

## Enumeration source = feature_modules.registry()
Never hardcode the companion list; read `tools/tbcml-bake/feature_modules.py registry()`. Use the `dat-cache-decode/` living paths it returns, NOT the frozen `bundle-companion/` snapshot. `outbreaks_b2b` ships a `.py` driver (not a `.js`) → loader skips it with a reason (it's still classified a cheat via its note).

## Load order (HARD RULE)
Providers first, `mod_settings_panel.js` LAST — the panel queries every other session's `rpc.exports` on install, so they must already be attached. Detect the panel by `module == "settings_panel"`, move to tail, keep providers in stable registry order.

## CRITICAL gotcha: frida session must be HELD open (eed289d)
Frida scripts only run WHILE the session is alive. The first cut detached immediately after loading → all hooks torn down before use ("10/10 loaded" then nothing). Like `frida -l` holds the terminal, `run_session` must HOLD (load → resume[spawn] → wait-until-Ctrl-C → detach in finally). Mocks did NOT catch this (FakeSession didn't model "scripts stop on detach") — caught by adversarial review. Lesson: a passing mocked test of a frida/process-lifetime orchestrator does NOT prove the live behavior; trace the real API's lifetime semantics.

## --deploy package caveat
`push_event0.py` hardcodes stock pkg `jp.co.ponos.battlecatsen` for its force-stop, but has a `--device-path` override. `--deploy` calls `push_event0.py apply --device-path /data/data/jp.co.ponos.battlecatsen.unlock/files/<md5>.dat` to reach the MODDED files dir; the in-helper force-stop still names stock (harmless if stock absent, else force-stop .unlock manually). Never re-implements the push.

## Not verified without a device
The actual frida attach/spawn/load and frida-server start. Everything is unit-proven via mocks + `--dry-run` against the real registry. Device-phase smoke test owns the live attach.