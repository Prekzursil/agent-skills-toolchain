---
name: SWFOC Simulator wire-format gotchas
description: Cross-iteration catalog of every wire-format mismatch the simulator caught
  between handler assumptions and real-dispatcher emissions (iters 22-34). Reference
  for adding new handlers without re-discovering these.
type: reference
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/reference-simulator-wire-gotchas
---

# SWFOC Simulator wire-format gotchas

**Compiled across iters 22-34 (2026-04-27).**

The simulator at `tests/SwfocTrainer.Tests/Simulator/` catches wire-format mismatches between handler assumptions and the actual dispatcher emissions in the editor's production code. This is the canonical list — every entry was a real bug that *would* have shipped.

## The 9 wire-format mismatches caught

| # | Function | Assumption that was wrong | What the dispatcher actually emits |
|---|---|---|---|
| 1 | `SWFOC_SpawnUnit` | 3-arg `(type, slot, qty)` from early Phase A tests | 6-arg `('type', slot, x, y, z, count)` — `BridgeSpawningDispatcher.cs:33` |
| 2 | Spawn type-id quoting | Double-quoted strings only | **Single-quoted** in `BridgeSpawningDispatcher` (`'TypeName'`) |
| 3 | `SWFOC_SetDamageMultiplier` | per-unit `(unitId, scalar)` | per-slot `(slot, mult)` — `BridgeCombatDispatcher.cs:42` |
| 4 | `SWFOC_SetFireRate` | per-unit | per-slot — same dispatcher |
| 5 | `SWFOC_SetIncomeMultiplier` | faction-string-keyed | per-slot int — `BridgeEconomyDispatcher.cs:53` |
| 6 | `SWFOC_ListHeroes` reply | pipe-separated rows, 5 fields | **newline**-separated rows, 6 fields (`addr;type;owner;alive;respawn_ms;respawn_enabled`) — `BridgeHeroLabDispatcher.cs:38` |
| 7 | `SWFOC_InspectUnit` reply | semicolon-separated fields | **space**-delimited `key=value` tokens (keys: `hull`, `owner`, `invuln_flag`, `prevent_death`) — `BridgeInspectorDispatcher.cs:56` |
| 8 | `SWFOC_DrainEnemyCredits` | `(myslot)` arg | **no-arg** form; engine resolves local human — `BridgeEconomyDispatcher.cs:46` |
| 9 | `SetDiplomacy` / `FireStoryEvent` | `SWFOC_*` wrappers | Engine-NATIVE Lua: `Find_Player + :Make_Ally/:Make_Enemy` and `Story_Event(...)` — `DiplomacyService.cs:165`, `StoryEventService.cs:134` |

## Patterns to remember when adding new handlers

### 1. Always read the dispatcher first

Before writing a simulator handler, find the dispatcher class (`Bridge<Tab>Dispatcher.cs` or the service in `SwfocTrainer.Core/Services/`) and grep for `string.Format(Inv, "return SWFOC_..."`. The exact emission template is the contract.

### 2. Quote-style is mixed

Some dispatchers use `'single'`, others `"double"`. The simulator regex now matches both via:
```csharp
private static readonly Regex s_strRx = new("(?:\"([^\"]*)\"|'([^']*)')", RegexOptions.Compiled);
```
For matching, check `m.Groups[1].Success` vs `m.Groups[2].Success`.

### 3. Function names contain digits

`SWFOC_SetHumanPlayer_v3` parses `3` from `_v3` if you scan ints from the whole command. Always slice inside `(...)` first via `ArgSlice`.

### 4. Engine-native Lua bypasses SWFOC_ prefix

Some services emit raw engine calls (`Find_Player`, `Story_Event`, `:Make_Ally`) instead of `SWFOC_*` wrappers. Register prefix matchers for those literal patterns too.

### 5. ERR-prefix replies → `Succeeded=false`

`NamedPipeLuaBridgeClient.cs:168` classifies any `ERR:`-prefixed bridge response as transport failure. Tests asserting error paths must use `round.Succeeded.Should().BeFalse()` and read `round.ErrorMessage`, not `round.Response`.

### 6. 0-byte responses are transport failures

`NamedPipeLuaBridgeClient.cs:162` flags `totalRead==0` as `Bridge closed connection without responding`. Don't write empty replies from handlers — return at least a single status byte.

### 7. Multiple arities are normal

The same `SWFOC_*` symbol often has 2-3 different call shapes across editor versions / dispatchers. The simulator typically supports all of them by counting args first:

```csharp
if (ints.Count == 1) { /* legacy single-arg */ }
else if (ints.Count >= 2) { /* current 2-arg */ }
```

### 8. Per-slot semantics are common

Combat scalars / income / unit cap / target filter / tech all use per-slot scaling, not per-unit or global. Track via `Dictionary<int, T>` keyed by slot.

### 9. Address parsing is hex-only

`UnitControlTabViewModel.TryParseObjAddr` always parses `ObjAddrInput` as hex (game obj addrs are 64-bit pointers). Tests must format `unit.Id.ToString("X")` not just `ToString()`.

## Where to find each artifact

| Artifact | Location |
|---|---|
| Simulator core | `tests/SwfocTrainer.Tests/Simulator/SwfocSimulator.cs` |
| State model | `tests/SwfocTrainer.Tests/Simulator/FakeGameState.cs` + `Fake{Player,Unit,Planet}.cs` |
| Pipe transport | `tests/SwfocTrainer.Tests/Simulator/FakeBridgePipeServer.cs` |
| Builder helpers | `tests/SwfocTrainer.Tests/Simulator/FakeGameStateBuilder.cs` |
| Direct E2E tests | `tests/SwfocTrainer.Tests/Simulator/E2E/SwfocSimulatorEndToEndTests.cs` (Phase A) |
| Per-domain E2E | `Simulator/E2E/PhaseB*.cs`, `PhaseC*.cs` |
| VM-driven scenarios | `Simulator/E2E/<Tab>ViewModelScenarioTests.cs` (8 tabs covered) |
| Stress tests | `Simulator/E2E/SimulatorStressTests.cs` |
| Operator scenarios | `Simulator/E2E/OperatorScenarioTests.cs` |
| Overlay-feature tests | `Simulator/E2E/PlanetFlipModeTests.cs` |
| README + Phase D candidates | `tests/SwfocTrainer.Tests/Simulator/README.md` |

## Stats as of 2026-04-27 (iter 34)

- **142 simulator tests across 16 files**
- **50+ SWFOC_* functions** covered
- **9 of 11 bridge-using V2 tabs** with full VM-driven coverage (real services + simulator)
- **Editor suite: 7166 / 0 / 0 + 5 skipped**, zero regressions across 14 iterations of new feature work

## What this saves

Every entry in the table above is a regression that would have shipped. Operator clicks button → button does nothing → no error message → only catchable in a live SWFOC session. With the simulator harness those bugs surface at unit-test speed, with a clear stack trace pointing at the handler that needs to match the dispatcher.

The compounding value scales with surface area: each new dispatcher I wire through real services catches new mismatches the simpler direct-handler tests can't see.