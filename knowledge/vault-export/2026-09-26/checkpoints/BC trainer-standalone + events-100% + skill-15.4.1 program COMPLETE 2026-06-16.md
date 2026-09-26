---
title: BC trainer-standalone + events-100% + skill-15.4.1 program COMPLETE 2026-06-16
type: note
permalink: main/checkpoints/bc-trainer-standalone-events-100-skill-15.4.1-program-complete-2026-06-16
tags:
- battlecats
- 15.4.1
- trainer
- self-verify
- bundle
- events
- compendium
- complete
---

# BC program COMPLETE (A→C→B) — 2026-06-16

Three fronts done + verified across 3 repos (NOT pushed). Continues [[bc-15.4.1-event-unlock-live-orb-chest-fix-tower-reset-bug-2026-06-11]].

## Front A — trainer standalone (WU-1..8, all committed, device-verified)
The trainer "refused to work" on 15.4.1 because the bc-offsets resilience gate refused writes (offsets carried as `verified:static`, the `bc_confirm._probe_live_value` confirm seam was never built). Fixed + made standalone:
- **Root unblock:** on-device `libnative-lib.so` sha256 byte-matches `en-15.4.1.json` pin → all static offsets correct for the running binary. Flipped 15.4.1 `static→bindiff`; widened `bc_offsets._CONFIRMED` to `{frida,bindiff}` (identity-confirmed counts as confirmed). The schema already had `bindiff` as a verified state.
- **WU-1 `bc_self_verify.py`** (pure identity probe): hash the .so backing the **attached PID's** `/proc/<pid>/maps` vs the manifest pin → `IdentityVerdict` {MATCH,MISMATCH,NO_DEVICE,NOT_ROOTED,NO_MANIFEST,UNVERIFIABLE}. Placeholder pin (15.3.0 `placeholder:true`) → UNVERIFIABLE. Reject `0x`-prefixed/short digests. 100% cov.
- **WU-2 `bc_gated_resolver.py`** `IdentityGatedResolver(manifest, verdict).off()` admits a write ONLY on MATCH; strictly-additive over the loader (only static promoted on MATCH; manual/null refused; non-MATCH refuses even bindiff/frida).
- **WU-3 Tk** + **WU-5 PySide6** wired: attach → self_verify → MATCH gates the inject/controllers. Tk live-verified `[self-verify] MATCH` reads coherent. PySide6 fail-closed gating (writes_enabled_from = MATCH-only), 98-gate green.
- **shared `bc_identity_seam.py`** `make_read_identity(run_su)`: pure parse of `/proc/maps`+`sha256sum`+`stat -c %s`(works on toybox); seam injected per front-end (Tk bc_adb_device, PySide6 run_adb).
- **WU-4 cross-branch:** `git checkout ralph-hardening -- tools/offsets` ports the package to `consolidate-unified`; `PORT_SOURCE.json` + `test_port_integrity.py` (newline-normalized per-file sha) guard against vendored-copy drift. ANY tools/offsets edit on ralph requires re-port+regen.
- **WU-7 bundle (device-smoke-VERIFIED):** self-contained 148MB onefile `dist/BattleCatsTrainer.exe` bundles frida 17.9.1 + `_frida.pyd` + `frida-server-17.9.1-x86_64` + adb.exe + manifests + vendored bc_speed_force. **KEYSTONE frozen-subprocess fix:** `sys.executable` in a frozen app is the .exe (not python) → spawning a script re-launches the GUI. Solved by an `app.py` `--run-speed-force` sub-command dispatched ABOVE the GUI imports → `bc_speed_force.main`; `speed.py._build_speed_cmd` is frozen-aware (`[exe, --run-speed-force]` when `sys.frozen`). Device smoke: `.exe --run-speed-force --speed 2` → `[attached pid=NNNN] forcing gs+SPEED_OFF=2` over frida-server.
- **WU-8** retired the dead `_probe_live_value` seam (probe now required).
- Persona = pre-rooted modder; PySide6 = consumer product, Tk = dev tool.

## Front C — events docs at verified 100% (commit e22bce7 in battlecats-toolkit/docs/game-knowledge/)
5 docs: `BC-EVENT-ARCHITECTURE.md` (activation model), `BC-STAGE-COMPENDIUM.md` (8-dim living, 87KB), `BC-EVENT-GLOSSARY.md` (every event family + 647-row companion `BC-EVENT-ROSTER.generated.tsv`), `BC-DATA-FORMATS.md` (every file format). Built by 2 Workflows (atlas wf_4b5dde1b + 100%-pass wf_a83923c2). KEY: towers ARE data-only activatable (corrects playbook "PROVEN DEAD"); Golden-Tower reset = repeatable-window-instance re-admit (sub_4DF750/8B0/A10), Behemoth Culling lone reset-safe; THREE namespaces; 6 schedule-only artifact bands; reward-id≠unit (1103≠Crazed-91); name-fill 58=52 EN-present+6 import; 7 JP-only imports {2270,11046-48,27026,34031,36023}.

## Front B — skill→15.4.1 (canonical agent-skills-toolchain a908275 + project battlecats-toolkit 95fef22)
`battlecats-event-unlock` SKILL.md+PLAYBOOK updated to 15.4.1 offsets (sub_819E20 0x823B00, sub_817020 0x820D00, sub_8A3350 0x8AD600, sub_8A3520 0x8AD7D0, sub_5F8DF0 0x600D70, getGlobal 0x65D900, SPEED_OFF 0x31D7A0), towers-corrected, 5 docs cross-linked, **15.3 preserved as a changelog** (user: "not scraped"). I fixed 1 delegated error: changelog getGlobal 15.3.0 was back-computed 0x658560/+0x53A0 → real **0x653C80/+0x9C80** (getGlobal does NOT follow the +0x53A0 wallet cluster).

## Reusable lessons
- **Verify every delegated change** — the WU-5/WU-7/Front-B subagents each had a real residual (F401s, E402, a back-computed offset) caught only by re-checking against the authoritative source.
- **bindiff/identity-confirm** is a legitimate `verified` state distinct from frida (live-read) — a whole-binary sha match proves offsets correct without touching the process.
- **Frozen subprocess pattern**: a sub-command entry dispatched before heavy imports is the way to run a bundled python helper from a PyInstaller onefile.
- Drift is NOT uniform — getGlobal +0x9C80 vs wallet cluster +0x53A0; never back-compute an old offset from a single drift constant.

## Relations
- relates_to [[battlecats-event-summoner]]
- relates_to [[reference_frida_hotpath_interceptor_crash]]
