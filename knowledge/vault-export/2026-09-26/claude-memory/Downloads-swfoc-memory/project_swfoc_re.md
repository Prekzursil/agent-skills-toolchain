---
name: SWFOC RE Project Status
description: Current state of SWFOC reverse engineering — Phases 1-5 complete, 20
  deliverables produced, trainer v3 (10 tabs), workspace reorganized
type: project
permalink: main/claude-memory/downloads-swfoc-memory/project-swfoc-re
---

## Phase Summary (as of 2026-04-05)

- **Phase 1**: RTTI recovery (2919 classes), initial struct layouts
- **Phase 2**: Live CE runtime verification, PlayerObject corrections, AOB signatures
- **Phase 3**: Exhaustive engine decompilation — 10 subsystems fully mapped via Ghidra
- **Phase 4**: Bridge v3 (state caching), Trainer v3 (10 tabs, 2252 lines), test suite
- **Phase 5**: Knowledge base consolidated (695KB across 20 deliverables), workspace reorganized

## Current State

### Workspace Structure (reorganized 2026-04-05)
```
swfoc_memory/
  knowledge-base/    — alamo_engine_kb_v3.json, reference.md, VERIFIED_RVAS_v3.md, etc.
  re-findings/       — 10 Phase 3 JSON files (playerobj, gameobj, combat, ai, etc.)
  trainer/           — SWFOC_GUI_Trainer_v3.CT + .lua
  bridge/            — bridge_test.py, pipe_test_quick.py, bridge_v3_changes.md
  swfoc_lua_bridge/  — DLL source (lua_bridge.cpp, rvas.h, build.bat)
  community/         — community_comparison.md
  archive/           — All superseded files (v1, v2, phase intermediates)
```

### Trainer v3 (10 tabs) — LOADED SUCCESSFULLY, NEEDS FULL TEST
- Tab 1: Economy (credits, tech, drain, max — all read/write CONFIRMED working)
- Tab 2: Combat (God Mode, OHK — hook installs, game survives, needs damage test)
- Tab 3: Speed (hero respawn — read/write CONFIRMED working)
- Tab 4: Inspector (manual address, VTable check — reads work, no crash)
- Tabs 5-10: Spawning, Galactic, Hero Lab, Battle, Story, Debug — BUILT, UNTESTED

### DLL Bridge v3 — COMPILED CLEAN, DEPLOYED, RUNNING
- Game state caching added (probe for Find_Object_Type in Hook_lua_open)
- lua_close hook DISABLED (RVA 0x7B8A70 is ESTIMATED, crashed game)
- SWFOC_StateInfo() function added
- Bridge log confirms: all 12 self-tests pass, PlayerArray found, local player identified
- Pipe server running but CE's connectToPipe() returns nil (API issue to investigate)

## Critical Learnings (from this session)

1. CE 7.6 does NOT have `createTabSheet()` — use `pageControl.addTab()`
2. Must add `if syntaxcheck then return end` at top of {$lua} scripts
3. Use `ucomiss` not `comiss` in AA caves — comiss crashes on NaN HP
4. CE 7.6 AA: don't use `label(name)` + `name:` — "defined more than once" error. Use `StarWarsG.exe+OFFSET:` directly
5. Lua 200-local limit: wrap tab construction in `do...end` blocks
6. CE AA numbers are hex by default: `dd 62` = 0x62, NOT decimal 62
7. NEVER hook unverified RVAs — lua_close at 0x7B8A70 crashed on startup
8. PlayerObject.Playable (+0x37) is NOT 0/2 — values seen: 217, 222, 66, 123, 0

## Known Issues

1. **lua_close RVA unverified** — 0x7B8A70 is estimated, hook disabled. Needs Ghidra confirmation
2. **CE pipe API mismatch** — connectToPipe() exists but writeToPipe/readFromPipe do NOT in CE 7.6. Bridge pipe server runs but CE can't connect
3. **Drain enemy logic broken** — checks Playable==2, but field has values like 217. Should check credits>0 && !isLocal instead
4. **God mode untested in combat** — hook installs (FF 25 indirect jmp), game survives, but no unit was attacked to verify protection
5. **Phase 3 findings are Ghidra static only** — 185 field offsets across PlayerObject+GameObject need runtime confirmation

## Key Files to Read
1. `README.md` — Full project index
2. `knowledge-base/alamo_engine_kb_v3.json` — All structs and RVAs
3. `knowledge-base/VERIFIED_RVAS_v3.md` — 280+ RVAs with verification status
4. `swfoc_lua_bridge/rvas.h` — C++ constants

**Why:** Building a complete trainer/modding toolkit for SWFOC Thrawn's Revenge 3.5
**How to apply:** Next session should focus on: (1) fix CE pipe connection, (2) runtime-verify Phase 3 offsets, (3) test god mode in actual combat, (4) fix drain enemy logic