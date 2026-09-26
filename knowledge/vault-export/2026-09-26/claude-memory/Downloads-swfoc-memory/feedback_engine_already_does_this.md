---
name: Engine-Already-Does-This Primitive Shortcut
description: When adding a new bridge wire, default to leveraging the cheapest existing
  mechanism (engine Lua API via DoString OR filesystem probe via Win32) instead of
  pinning a new RVA. 6× to 10× cheaper than RVA work for equivalent operator-visible
  capability.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-engine-already-does-this
---

**Rule:** When adding any new SWFOC_* bridge wire, the FIRST thing to check is whether the engine already exposes the capability via a primitive that's cheaper to leverage than RVA-pinning. The two cheap primitives are:

1. **DoString into engine Lua API** (~30-50 LoC per wire)
2. **Filesystem probe via Win32 FindFirst/Next** (~80-110 LoC per wire)

vs. RVA-pin path (~200-500 LoC + multi-hour reverse-engineering).

**Why:**

6 instances across the iter 100-300 window prove this is load-bearing across multiple sessions, multiple parallel threads, and multiple operator-mandate expansions:

| Iter | Wire | Mechanism | Cost |
|---|---|---|---|
| iter-100 | `SetUnitSpeed` / `SetPerFactionSpeedMultiplier` | DoString → engine `Set_Speed` Lua method | ~50 LoC |
| iter-107 | `SetCameraPos` | DoString → `Scroll_Camera_To` Lua | ~30 LoC |
| iter-179 | TaskForce write-side batch | DoString → TaskForce Lua methods | ~30 LoC for 4 wires |
| iter-296 | `GetPlanets` | DoString → `Find_All_Objects_Of_Type('Planet')` | ~50 LoC |
| iter-299 | `GetFactionRoster` | DoString → `Find_All_Objects_Of_Type` + faction filter | ~80 LoC |
| iter-300 | `ListMods` | Filesystem walk of `./Mods/*/Modinfo.xml` | ~110 LoC |

Without the rule, each wire would have cost ~200-500 LoC of RVA pin + decompile + callgraph cross-validation work. The cumulative savings across 6 instances is measured in **days of operator/agent time**.

**How to apply:**

1. **30-second grep**: search `docs/lua-api.md` for the operation you need (engine Lua API surface).
2. **If found in engine Lua API**: use DoString approach. Wrap engine Lua call inside a static `kEnumerateScript` C-string, pcall-guard each dereference (so one bad object doesn't break the whole call), invoke via `DoString(L, kScript, "=SWFOC_<name>")`, capture return-stack via `fn_tostring(L, -1)`, push back to Lua. Return CSV the C# dispatcher consumes. Reference templates: iter-296 `Lua_GetPlanets` (no-arg), iter-299 `Lua_GetFactionRoster` (1-arg).
3. **If NOT found in engine Lua API**: check if it's a *filesystem* question (mod folders, save files, log paths). If yes: use Win32 `FindFirstFileA` / `FindNextFileA` walk pattern. Reference templates: iter-299 `Lua_GetCurrentMod` (most-recently-accessed), iter-300 `Lua_ListMods` (all candidates).
4. **Only if NEITHER applies** (e.g., engine-internal state with no Lua exposure AND no filesystem footprint): RVA pin is justified. Audit ledger first via `python -m verifier lint` from `tools/`; pin via callgraph CLI re-audit pattern if related symbols already exist (iter-128 SetUnitShield correction template).

**Honest break-out clause** — when filesystem wins over DoString:

iter-299 GetCurrentMod and iter-300 ListMods both use filesystem probes, NOT DoString, because the engine has NO Lua API for "what mod did I launch with?" or "what mods are installed?" — the Lua VM doesn't know about its own host process's command-line. Acknowledge this honestly in the catalog rationale so future readers don't waste time looking for an engine Lua API that doesn't exist.

**Edge cases worth flagging:**

- **Don't double-codify with `feedback_flag_flipping_vs_engine_state`**: that earlier rule is the INVERSE direction — when something looks easy via direct memory write but should go through the engine. This rule (engine-already-does-this) is about preferring the cheap mechanism. Both can be true: prefer engine API, but route through it (don't bypass it via direct memory write).
- **Composability**: DoString-based wires can compose. iter-299 GetFactionRoster reuses iter-296's `Find_All_Objects_Of_Type` pattern + adds a per-element filter. Subsequent wires get even cheaper as the operator's mental model of available engine APIs grows.
- **Mod-compat is FREE with DoString**: the engine's Lua API works on whatever mod is loaded. iter-296 GetPlanets returns the active mod's planet roster without knowing whether vanilla, AOTR, ROTM, or something else is installed. RVA pins, by contrast, may need per-mod calibration.
- **Wire-format alignment is mandatory**: the cheap mechanism still has to emit the CSV shape the C# dispatcher consumes. iter-296b mid-iter fix (pipe-separated → newline-separated) burned ~15 minutes because the bridge return shape didn't match what `BridgeGalacticDispatcher.GetPlanetsAsync` parses. Always grep the consumer-side dispatcher's parser FIRST and match its expected format.

**Cost-benefit ratio:**

- DoString path: ~30-50 LoC, 1 iter from design to LIVE (iter-296 = 1 iter; iter-299 = 1 iter for both wires).
- Filesystem path: ~80-110 LoC, 1 iter (iter-299 GetCurrentMod = 1 iter; iter-300 ListMods = 1 iter).
- RVA-pin path: ~200-500 LoC, 5-iter arc (iter-225 fire-rate-global = 5-iter arc; iter-237 SetCameraPos per-coord = 5-iter arc).
- **6× to 10× cheaper for equivalent operator-visible capability.**

**Memory-write triggers** (don't skip codifying when these fire):

- 6 instances across ~200 iters is enough recurrence to abstract. The pattern survived multiple sessions, multiple parallel threads (Thread A + Thread B + Thread C), and multiple operator-mandate expansions (iter-294 enumeration mandate). Codification at this point is *defensible*, not premature.
- Future incidents (instance #7+) should EXTEND this rule rather than create new ones. Add a row to the table above.
- If a future iter discovers a THIRD cheap mechanism (e.g., shared-memory probe, named-pipe IPC against a sidecar), add it as a new section here.

**Prospective uses (iter-302+):**

- Asset/icon extraction (iter-303+ stretch) — check for engine Lua API to load DDS / .meg first; if missing, fall back to filesystem .meg parser + DDS decoder.
- Faction-roster-by-build-tab (Audit B remaining wire) — likely DoString via `Get_Buildable_Type_List()` if it exists.
- Hero-roster (Audit B remaining wire) — likely DoString via `Find_All_Objects_Of_Type('Hero')` extension of iter-299.

**Pattern reinforcement:** the *5-second-grep* discipline (codified iter-283 `feedback_infra_claim_drift_bidirectional`) and this rule are siblings — both are cheap-verification-before-design rules. Combined: at the top of any new-wire iter, spend 30 seconds checking (a) does the engine Lua API expose this? (b) does this pre-exist as code? Both checks together cost ~35 seconds and prevent ~hours of misdirected work.