---
permalink: main/claude-memory/downloads-swfoc-memory/feedback-flag-flipping-vs-engine-state
---

---
name: Byte flipping ≠ engine state management in SWFOC
description: Writing state bytes directly bypasses the engine's real state machines. Route through engine functions (Make_Invulnerable, Switch_Sides, BehaviorAttach) instead. Learned twice: FactionSwitch v1 (galactic split-brain) and Unit Control per-unit helpers (2026-04-23).
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
---
**Rule**: Never solve an SWFOC gameplay problem by writing a state byte directly. Route through the engine's state-management function instead.

**Why**: The SWFOC engine maintains redundant state for gameplay-relevant flags — a display byte that the UI reads, separate behavior objects attached via `BehaviorAttach`, subsystem caches that need explicit refresh events. Writing only the display byte produces no gameplay effect.

**How to apply**:

1. Before implementing any "set X = Y" helper in `lua_bridge.cpp`, search `verified_facts.json` for a ledger entry documenting the engine's proper path (e.g. `fact_make_invulnerable_hardpoint_propagation` for invulnerability, `rva_player_list_switch_sides` for human-player slot).
2. If the engine path is a Lua-registered function, either call it via `SWFOC_DoString` with a constructed Lua userdata wrapper, or reimplement its C++ primitive chain inline (QueryInterface → iteration → per-child BehaviorAttach, or similar).
3. Before declaring a helper "working", verify with a round-trip: call it, then read the relevant state via `InspectUnit` / `GetHardpoints` / similar to confirm the effect landed. A helper that returns "OK" means the bridge executed — not that the engine acted on the write.
4. The v1 FactionSwitch / Unit Control byte-flip pattern is an instant red flag in code review.

**Session-verified examples**:
- 2026-04-11 FactionSwitch v1: wrote `+0x30` slot + `+0x62` LocalPlayer byte directly, bypassing `Switch_Sides`'s subsystem refresh event 55 dispatch. Result: split-brain galactic state. Fix: v2 calls the engine's `GameMode_RefreshLocalPlayerSubsystems` after the sweep.
- 2026-04-23 Unit Control: wrote `+0x3A7` invuln_flag, `+0x3A1` prevent_death bit, `hull` float. `InspectUnit` confirms bytes flipped (0x00→0x01, 0x00→0x80, 5198→6000). But combat damage still kills the unit because real invulnerability is per-hardpoint `BehaviorAttach("INVULNERABLE")` and real damage applies through a non-SetHP path. Open tasks: #99 (hardpoint behavior path) and #100 (find real damage hook site).

**Related IDA finding — implicit deref**: IDA Hex-Rays `qword_XXX` is an implicit-dereference symbol. `*(qword_XXX + offset)` is **TWO** memory accesses: (1) read the qword at XXX, (2) dereference that value + offset. Agent B's 2026-04-11 selection chain got this wrong (wrote as one deref), produced garbage mgrRoot `0xa00000002`. Fixed 2026-04-23 with two-deref + `SWFOC_DiagSelection` helper that dumps both interpretations for empirical proof.