---
name: SWFOC In-Memory Simulator Harness
description: Phase A complete 2026-04-27 — in-memory simulator at tests/SwfocTrainer.Tests/Simulator/
  pairs the real bridge wire protocol with synthetic FakeGameState. Lets editor features
  be tested E2E without a live SWFOC session.
type: project
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/project-swfoc-simulator
---

# SWFOC In-Memory Simulator Harness

**Created:** 2026-04-27 (iter 22 of the Ralph polish loop)

**Location:** `tests/SwfocTrainer.Tests/Simulator/` (in the editor solution at `C:\Users\Prekzursil\Downloads\SWFOC editor`)

## What it is

In-memory mock of SWFOC's runtime that:
1. Speaks the **same named-pipe wire protocol** as the production `powrprof.dll` bridge (0x00 terminator + ASCII reply, longest-prefix dispatch).
2. Maintains a **synthetic game state** (players, units, planets, story flags, mode/AI/fog toggles).
3. Exposes a **per-`SWFOC_*` function handler registry** that parses Lua args, mutates state, and returns the live wire format the editor expects.

The editor's real `V2BridgeAdapter → NamedPipeLuaBridgeClient` stack connects to it as a client — no editor-side mocking. Tests assert that simulated state mutated as the feature claims it should.

## File layout

```
tests/SwfocTrainer.Tests/Simulator/
├── README.md                            ← architecture + Phase B candidates
├── FakeBridgePipeServer.cs              ← transport (named pipe + dispatcher)
├── FakeGameState.cs                     ← world: players + units + planets + flags
├── FakePlayer.cs                        ← slot/faction/credits/IsHuman/IsLocal/HasAiBrain
├── FakeUnit.cs                          ← type/hull/owner/alive/invuln/prevent-death
├── FakePlanet.cs                        ← name/owner/revealed/structures
├── SwfocSimulator.cs                    ← orchestrator: registers handlers on the pipe server
└── E2E/
    ├── SwfocSimulatorEndToEndTests.cs   ← 13 per-function tests
    └── OperatorScenarioTests.cs         ← 4 multi-step journeys
```

## Phase A coverage (iter 22)

16 SWFOC_* functions registered across:
- **Diagnostics** — GetVersion, GetBuildInfo, DiagListRegisteredFunctions, DiagSelfTest
- **Player state** — GetAllPlayers, GetLocalPlayer, SetHumanPlayer_v3, GetCredits, SetCredits
- **Spawning** — BatchTypeExists, ListUnitTypes, SpawnUnit
- **Unit control** — ListTacticalUnits, KillUnit, SetUnitInvuln, SetUnitHull, PreventUnitDeath
- **Galactic** — RevealAll, GetPlanets
- **Story** — FireStoryEvent

Plus a catch-all `"return "` stub that returns `"(sim: unhandled probe — handler not registered)"` so unknown probes fail clearly instead of timing out.

## Phase B candidates (in priority order, see README)

1. Combat scalars — SetDamageMultiplier, SetFireRate, SetUnitShield
2. Hero Lab — ListHeroes, HeroInstantRespawn, HeroStatEdit, SetHeroRespawn
3. AI brain — GetAiBrain, NullAiBrain, AttachAiBrain, FreezeAI
4. Galactic — ChangePlanetOwner, GetTechForSlot, SetTechForSlot, InstantBuild
5. Diplomacy — SetDiplomacy
6. Speed — SetGameSpeed, SetPerFactionSpeedMultiplier, SetUnitSpeed
7. Event stream — EventControl, EventStreamDrain
8. Hardpoints — GetHardpoints, OneHitKill, CombinedGodOHK

## Gotchas captured during construction

- **Lua function names contain digits** (`SWFOC_SetHumanPlayer_v3`). A naive `\d+` regex over the whole command will eat the version suffix as the first arg. Always slice inside `(...)` first via `SwfocSimulator.ArgSlice`.
- **`NamedPipeLuaBridgeClient` (production code) flags `ERR:`-prefixed replies as `Succeeded=false`** (line 168). Test assertions on error paths must use `Succeeded.Should().BeFalse()` and `ErrorMessage.Should().StartWith("ERR:")` — not `Succeeded=true` with `Response="ERR:..."`.
- **0-byte responses are transport failures**. The bridge client treats `totalRead==0` as `Bridge closed connection without responding` (line 162-164). Don't write empty replies from handlers — return at least a single status byte.
- **InternalsVisibleTo is wired** at `src/SwfocTrainer.App/Properties/AssemblyInfo.cs` for `SwfocTrainer.Tests` — internal helper methods on VMs (e.g. `ProbesTabViewModel.PushHistory`, `SwfocSimulator.ArgSlice`) are accessible from test code.

## What this does NOT replace

- **Live RVA verification** — bridge C++ functions still need 2-tool consensus in `verified_facts.json` before they're VERIFIED. The simulator only proves the editor's BRIDGE-CALL path is correct, not that the bridge itself implements the function correctly against the engine.
- **WPF window tests** — pixel-level theme verification (`DarkModeContrastTests`) and FlaUI-driven UI walks (`WpfTabAuditTests`) still need a launched window. Those live in `SwfocTrainer.UiTests/`, separate from the simulator.
- **End-to-end live-game smoke** — the final pre-release pass still uses `knowledge-base/go_live_smoke_checklist_*.md` against an actual SWFOC session. The simulator catches *most* breakage before that point but is not a substitute for that final pass.