---
name: SWFOC Verification Approach
description: How to actually verify SWFOC RE findings — multi-tool cross-validation,
  autonomous testing, no live-game-only probing
type: feedback
permalink: main/claude-memory/downloads-swfoc-memory/feedback-swfoc-verification-approach
---

# SWFOC RE Verification Approach (User Correction)

## The Rule

For SWFOC RE work, claims about engine internals (struct offsets, RVAs, Lua API behavior, hardpoint propagation, etc.) MUST be backed by **multi-tool cross-validation against real binary data**, not by Lua-only probes against a live running game.

## Why

**Why:** The user explicitly called out that:
- Lua-only testing is restrictive (the Lua API is a thin surface — it can confirm a method exists but cannot prove what its C++ implementation actually mutates)
- Live-game probing requires the user to be in the game manually, in active gameplay, unpaused, with the right scope (galactic vs tactical) — that's "very time consuming and sometimes requires scope adjustments that are impractical"
- Spawn results were never properly verified — calls returned `ok=true` but the spawned objects never appeared in subsequent inventory queries; the test reported PASS without checking the side effect
- I (Claude) abandoned the IDA Pro / Ghidra / Binary Ninja / Frida / Cheat Engine MCP tooling that was already wired up and started writing PowerShell scripts that effectively re-implement what those tools already do, but worse
- The tooling was the whole point of having those MCP servers — sidestepping them defeats the purpose

## How to apply

**Multi-tool cross-validation for any RE claim:**

| Layer | Tool | What it proves |
|---|---|---|
| Static decompile | IDA Pro MCP (`mcp__ida-pro-mcp`) | Function signature, control flow, called sub-functions, struct field reads/writes |
| Static cross-check | Ghidra MCP (`mcp__ghidra-mcp`) | Independent decompile (catches IDA hallucination); xrefs to/from address |
| IL analysis | Binary Ninja MCP (`mcp__binary-ninja-mcp`) | LLIL/MLIL/HLIL chains; better xref completeness; type recovery |
| Runtime hook | Frida MCP (`mcp__frida-mcp`) | Args/returns at call site, proves function actually fires, captures real memory writes |
| Memory snapshot | Cheat Engine MCP (`mcp__cheatengine`) | Struct offset values BEFORE and AFTER an operation, proves what changed |
| Lua bridge | `\\.\pipe\swfoc_bridge` | Last layer — confirms the Lua API contract end-to-end against live game |

**A finding is only "verified" when 2+ tools agree.** A Lua probe alone is "live observation" — useful as a final sanity check, NOT proof.

**Autonomous testing requirement:** Tests must run without the user being at the keyboard. The user said "I don't do anything manual remember that". This means:
- No "tell me which planet to attack" prompts
- No "wait for user to be in tactical battle" gates
- No tests that require the user to position units or pause/unpause
- Tests run against a captured game-state snapshot OR a mock environment OR a frozen game state, not live interactive gameplay

**Probe results properly:** When a test calls `Spawn_Unit(...)` and gets `ok=true`, the test MUST then verify the side effect (the spawned unit appears in `Find_All_Objects_Of_Type` enumeration with the expected count delta). PASS != "the call returned without an error" — PASS = "the observable game state changed in the expected way".

## Anti-patterns to avoid

1. Writing PowerShell scripts that probe the Lua bridge instead of using the IDA/Ghidra MCP tools that were already loaded
2. Reporting `Take_Damage` as "tested" when the call returned `ok=true` but hull was unchanged (the test was inconclusive, not passing)
3. Assuming "the function exists in the metatable" means "the function does what its name suggests"
4. Treating live-game intermittent timeouts as "the bridge state is fluctuating" — they may indicate the test premise is wrong
5. Producing `bridge_response: OK` for `Story_Event` and calling that PASS without verifying the event actually fired in the game's event log
6. Skipping the binary RE tools because the Lua bridge is "easier"