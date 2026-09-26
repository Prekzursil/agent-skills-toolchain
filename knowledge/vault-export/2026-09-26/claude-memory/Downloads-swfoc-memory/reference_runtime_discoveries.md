---
name: Runtime Discoveries & External References
description: All runtime findings (CE MCP, DLL bridge), CE bugs, FoCAPI cross-reference,
  community ecosystem — consolidated
type: reference
permalink: main/claude-memory/downloads-swfoc-memory/reference-runtime-discoveries
---

## CE Bugs Discovered
1. **`getRTTIClassName()` broken** — returns nil for all objects in this x64 binary (image-relative RTTI, COL signature=1). Workaround: direct vtable RVA comparison (`readQword(obj) == base + 0x8661B8`).
2. **`vtQword` scan broken** — CE scanner cannot find large qword values (module addresses). `readQword` comparison works fine.
3. **CE often attaches to stale PIDs** — always verify `readSmallInteger(base) == 0x5A4D` before reading.

## PlayerObject Layout Corrections (CE MCP, 2026-04-04)
KB had +0x04 as player_id — WRONG (returns 32759 for all slots). Corrected:
- **+0x37** byte: Playable flag (2=playable, 3=allied, 0=AI/neutral)
- **+0x48** int32: Slot index (matches GameObjectClass+0x58 owner)
- **+0x62** byte: **Local player flag** (1=YOU, unique to one slot)
- **+0x68** ptr: Faction name string (e.g., "ZSINJ_EMPIRE")

## DLL Bridge Architecture
- `powrprof.dll` proxy via DLL search order side-loading (no injector needed)
- MinHook hooks `lua_open` at RVA 0x7B8930 in game's own thread
- 9 custom Lua functions registered on every new lua_State (357+ states per session)
- lua_State* stored at `[script_object+0x58]` (found via lua_open caller at 0x2457FC)
- CE-based Lua access is UNSAFE (wrong thread context → crashes). DLL approach is safe.

## FoCAPI (github.com/drewcav96/FoCAPI)
C++ DLL hook, updated March 2026, confirmed working with 64-bit StarWarsG.exe. Key contributions:
- lua_open RVA 0x7B8930, powrprof.dll proxy technique
- Corrected our wrong RVAs: pushstring=0x7B9540, settable=0x7B9A60
- Additional RVAs: Get_Script_From_State=0x245790, PlayerWrapper::Create=0x6019F0, TheCommandBar=0xB27F60, TheGameText=0xA7BC58

## Community Ecosystem
- **Imperialware**: C# mod tool, ZERO memory offsets (pure file-based XML/Lua). Confirmed Lua function semantics.
- **PetroglyphTools**: NuGet packages for MEG/DAT parsing. Could replace custom implementations.
- **eaw-emmyluadoc + Focumentation**: 405 Lua functions documented. Our 134 RE bindings cover 33% by name but 100% of RVAs.
- **Apocalypticx CE tables**: Working 64-bit AOBs for maphack (0x451974), instant build, unit cap. Integrated into CT v8.
- **Petroglyph Debug Kit**: 64-bit debug exe with enhanced console. Command list dumped to logfile on startup.

## Key Behavioral Warnings (from community)
- `Prevent_AI_Usage(true)` crashes in tactical if unit has no active AI
- `Make_Ally`/`Make_Enemy` resets every game mode change
- `Disable_Bombing_Run` has reversed parameter logic (pass false to disable)
- `Attack_Move` CommandBlock never finishes
- `SFXManager.Allow_Unit_Reponse_VO` — engine typo ("Reponse")

**How to apply:** Use VERIFIED_RVAS.md for all address lookups. Never use getRTTIClassName or vtQword scan. Always verify CE process attachment. Community docs are for Lua SEMANTICS only — our RE provides the ADDRESSES.