---
name: CE Lua & AA Pitfalls
description: Hard-won CE 7.6 compatibility rules discovered through crashes and silent
  failures during trainer development
type: feedback
permalink: main/claude-memory/downloads-swfoc-memory/feedback-ce-lua-pitfalls
---

## CE 7.6 Lua API

- `createTabSheet()` does NOT exist — use `pageControl.addTab()` instead
- `writeToPipe` / `readFromPipe` / `closePipe` do NOT exist — only `connectToPipe()` exists (and returns nil)
- Must add `if syntaxcheck then return end` at top of any {$lua} AA script — CE runs scripts twice
- Lua 5.3 has a 200-local-variable limit per function — wrap GUI tab sections in `do...end` blocks

**Why:** These caused silent failures (no GUI appearing) or load errors that took significant debugging to find.
**How to apply:** Before writing any CE Lua code, check these constraints. Before generating AA scripts, verify instruction choices.

## CE Auto Assembler

- Numbers are **hex by default** in ALL contexts (`dd 62` = 0x62, `[r8+62]` = r8+0x62). Use `#` prefix for decimal
- Do NOT use `label(name)` + `name:` for hook points — CE 7.6 errors "defined more than once". Use direct `StarWarsG.exe+OFFSET:` addressing
- Use `ucomiss` instead of `comiss` — comiss raises #IA exception on NaN values (destroyed objects have NaN HP), crashing the game
- Every branch path in a code cave MUST have identical stack depth when reaching the original prologue. Missing pops on null-pointer `jz` paths cause stack corruption → crash on `ret`
- CE may use `FF 25` (indirect jump) instead of `E9` (direct jump) when the cave allocation is too far from the hook point — both are valid

**Why:** comiss crash took hours to diagnose. Stack imbalance crash only triggers on rare null-owner units. label() error was CE-version-specific.
**How to apply:** Every AA cave script must be audited for: ucomiss usage, stack balance on ALL paths, no label()/registersymbol() for hook points.

## RVA Safety

- NEVER hook an unverified/estimated RVA — the lua_close hook at 0x7B8A70 crashed the game on startup because it wasn't the right function
- Always verify RVAs via Ghidra decompilation before creating MinHook hooks
- Make hook failures non-fatal where possible, but even MH_CreateHook succeeding on a wrong address can crash when MH_EnableHook patches the wrong bytes

**Why:** Game crashed on startup from hooking an estimated address. Cost a full game restart cycle.
**How to apply:** Any new RVA added to rvas.h must be tagged CONFIRMED or ESTIMATED. Only CONFIRMED RVAs get hooked.