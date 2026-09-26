---
name: SWFOC Bridge Architecture
description: Two parallel bridge systems (powrprof.dll + SwfocExtender.Host) and how
  the editor reaches them
type: reference
permalink: main/claude-memory/downloads-swfoc-memory/reference-bridge-architecture
---

# SWFOC Bridge Architecture

There are TWO independent bridge systems in this project. They serve different consumers and don't talk to each other natively.

## System A — powrprof.dll (Lua Bridge)

- **Process**: Injected into `StarWarsG.exe` via DLL hijacking (`powrprof.dll` proxy in the corruption directory)
- **Pipe**: `\\.\pipe\swfoc_bridge`
- **Source**: `C:\Users\Prekzursil\Downloads\swfoc_memory\swfoc_lua_bridge\lua_bridge.cpp`
- **Hooks**: `lua_open`, `lua_close`, `luaD_call`, `Take_Damage_Outer`, `DeathHandler`
- **Protocol**: Connect → write Lua command + null terminator → read response
- **Drain mechanism**: Pipe handler queues command, the `luaD_call` hook drains it on a registered Lua state on the main game thread
- **Limitation**: Drain only fires when the game actually invokes Lua. If the game is paused/in menu/in transition, no luaD_call → no drain → 10s timeout with `ERR: timeout (10s) - game may be paused or in menu`
- **Status**: Working — 286KB DLL, 388 lua_open hooks per session, all 13 SWFOC_* helpers register correctly, self-tests pass for every state. Used by the CE trainer historically.

## System B — SwfocExtender.Host (Native Plugin Host)

- **Process**: Standalone `SwfocExtender.Host.exe` (NOT injected into the game; runs as a separate process)
- **Path**: `C:\Users\Prekzursil\Downloads\SWFOC editor\native\build-win-vs\SwfocExtender.Bridge\Release\SwfocExtender.Host.exe`
- **Pipe**: `\\.\pipe\SwfocExtenderBridge`
- **Source**: `C:\Users\Prekzursil\Downloads\SWFOC editor\native\SwfocExtender.Bridge\src\BridgeHostMain.cpp`
- **Plugins**:
  - `EconomyPlugin` — handles `set_credits` via `process_mutation::TryWriteValue` (real memory writes via OpenProcess + WriteProcessMemory)
  - `BuildPatchPlugin` — `toggle_instant_build_patch`
  - `GlobalTogglePlugin` — `freeze_timer`, `toggle_fog_reveal`, `toggle_ai`, `set_unit_cap`
  - `HelperLuaPlugin` — **STUB**. Validates the request, captures `helperScript` in diagnostics, returns success without executing anything. Covers `spawn_unit_helper`, `spawn_*_entity`, `place_planet_building`, `set_context_allegiance`, `set_hero_state_helper`, `toggle_roe_respawn_helper`.
- **Status**: Native features (EconomyPlugin et al.) actually mutate game memory. Helper features return success-without-execution.

## How the .NET Editor Reaches Each System

- **14 native features** (`set_credits`, `freeze_timer`, etc.):
  Editor → `IBackendRouter` → `NamedPipeExtenderBackend` → `SwfocExtenderBridge` pipe → host → plugin → process memory write. **WORKS.**
- **15 v5 services** (`StoryEvent`, `EnhancedSpawn`, `CameraDirector`, etc.):
  Each service has a `BuildLuaCommand` method that produces real Lua source.
  **As of 2026-04-06 evening:** `LuaBridgeExecutor` first tries `NamedPipeLuaBridgeClient` → `\\.\pipe\swfoc_bridge` (System A, direct). When the bridge pipe is unavailable it falls back to the orchestrator/profile-action path, which routes through `HelperLuaPlugin` (the stub) and only records what *would* have executed.

## Why Two Systems

- System A predates the editor and was used by the Cheat Engine v3/v4 trainer.
- System B was built for the .NET editor's native plugins and runs out-of-process so the editor doesn't need to be injected into the game.
- The HelperLuaPlugin in System B was designed assuming a future native Lua execution path; the stub remains because the project shipped EconomyPlugin / BuildPatchPlugin first.

## Live Testing Prerequisites

Before any v5 service can mutate the live game, ALL of the following must hold:

1. `StarWarsG.exe` is running with `powrprof.dll` injected (the dll lives in the game's `corruption` directory).
2. The game is in **active gameplay** (tactical or galactic, **not** main menu, **not** paused). luaD_call must fire on a registered state.
3. `\\.\pipe\swfoc_bridge` is reachable (verify with the test script in `swfoc_memory/test_pipe.ps1`).
4. `SwfocExtender.Host.exe` is running for the editor's native features.