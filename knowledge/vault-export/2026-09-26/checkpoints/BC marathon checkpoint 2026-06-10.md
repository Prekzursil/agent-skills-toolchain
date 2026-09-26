---
title: BC marathon checkpoint 2026-06-10
type: report
permalink: main/checkpoints/bc-marathon-checkpoint-2026-06-10
tags:
- compaction-checkpoint
- battlecats
- trainer
- solver
- bcsfe-editor
---

# BC marathon checkpoint — 2026-06-10

Full handoff also at `C:/Users/Prekzursil/.remember/remember.md`. Two worktrees, one repo:
ralph-hardening (`battlecats-toolkit`, legacy frida trainer + dat-cache + event tools) and
consolidate-unified (`bc-toolkit-unified-wt`, PySide6 GUI + solver + cleanup + bcsfe_bridge).
Bash not PowerShell; scoped git add (never -A; bc_adb_device.py = other session WIP). Two emulators →
`export ANDROID_SERIAL=127.0.0.1:5555`. GUI gate venv = tools/trainer-gui/.venv + QT_QPA_PLATFORM=offscreen;
bcsfe/frida venv = BCSFE-Python/.venv.

## Observations
- [delivered] ralph HEAD e3924b4: speed-crash real fix (removed Interceptor.attach(getGlobal) → periodic JS write),
  Officer Pass enable (bc_officer_pass.py + GUI button + -OfficerPass), GUI prefs persistence (bc_trainer_prefs.py),
  FREEZE menu fix (walletWritableSafe gate replaces inBattleSafe so Start Freeze holds on a menu too). All committed+pushed.
- [delivered] consolidate HEAD 08038fe: SOL-G2 solver pipeline COMPLETE (service/panel/inputs/assemble/roster_pool/
  advice, 100%, ranking_validated=False); CL-1 reconcile_manifest + build_mapping; Treasure/Ototo/Cats-write/Currency
  write controllers + Currency panel (100%, staged-save + confirm-latch). All committed+pushed.
- [finding] bcsfe_bridge ops are NOT consumed by the GUI — editor screens are simulate-only; orbs was the only
  save-write path. Expansion = write controllers (mirror OrbsWriteController: confirm-latch + staged save to
  SAVE_RECOVERY_DIR, never live) + panel/shell wiring per feature.
- [live] BC pid 11946; event unlocker loaded (event_0 dd02a95f + enable-combined keep-alive bg — do not kill;
  both drop on BC restart). Speed/OfficerPass/StartFreeze confirmed working.
- [caveat] wf_e3a6eda9 adversarial-verify phase was still running at commit of 08038fe (build gates re-verified
  by me); fold verify findings + re-run trainer-gui aggregate gate clean next session (a transient pytest collision
  errored my aggregate run, but each unit is 100% solo).
- [gotcha] "mirror" = cooldown MIRROR counter (each cooldown stored twice); no "mirror tick" fn.
- [gotcha] Frida: never high-freq Interceptor.attach on a render-thread fn; diagnose via logcat -b crash (rip==fault_addr).
- [next] (A) editor-expansion wiring: panels + main_window tabs for treasure/ototo/currency/cats-write + connect
  cat_editor edit_committed → CatsWriteController; then talents-write/stages-clear. (B) solver shell wiring: load the
  unused DS-F2 stage_model bundle (load_stage_model_repository) + mapid→stage_key + targets_by_cat + register
  SuggesterPanel tab on mapSelected. (C) merge PR #3; CL-1 author real cleanup_mapping (deletion USER-gated).

## Relations
- relates_to [[battlecats-event-summoner]]
- relates_to [[reference_frida_hotpath_interceptor_crash]]
