---
name: Native UX surfaces for LIVE bridge wires
description: When a SWFOC_* wire flips LIVE in the catalog, follow up with native
  per-tab buttons — Lua Playground presets are not enough; operators don't discover
  or trust wires that only live in a preset menu
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-native-ux-for-live-wires
---

When a `SWFOC_*` bridge wire flips LIVE in `CapabilityStatusCatalog`, the
session is NOT done until the wire has a native button on the relevant
operator-facing tab.

**Why**: iter 100-113 shipped 17 LIVE wires (Speed, Damage, Camera, Owner,
Spawn, Invuln, Hide, PreventAi, Selectable, Despawn, Stop, Retreat,
universal `CallObjMethodLua`). Iter 116 surfaced them as a Lua Playground
preset menu — operator must navigate to Lua Playground, scroll a 20-entry
ComboBox, paste, then Run. That works for power users but operators
don't discover or trust wires they only see as preset strings. Iter
117-119 closed this by adding native buttons on UnitControl + Spawning
tabs. The cost was tiny (3 iters, ~120 LoC + 19 wire-format pin tests)
because the bridge + catalog + simulator + red-green pairs were already
in place from iter 100-113.

**How to apply** (when shipping a new LIVE wire):

1. Add the bridge wire + harness test (`swfoc_lua_bridge/lua_bridge.cpp`).
2. Flip the catalog entry to `Live` (`CapabilityStatusCatalog.cs`).
3. Add a simulator handler + red-green pair
   (`tests/SwfocTrainer.Tests/Simulator/SwfocSimulator.cs` +
   `tests/SwfocTrainer.Tests/Regression/Iter<NNN>*Tests.cs`).
4. **Add a native button** on the relevant tab — NOT just a Lua
   Playground preset. Bind to a TextBox the operator already sees on
   that tab (e.g. UnitControl's `SelectedUnitLuaExpr`), or add a
   minimal new TextBox if the wire needs distinct input.
5. Add the per-button `CapabilityAwareAction` so the badge shows LIVE.
6. Update the tab's PHASE 2 PENDING banner if applicable to point at
   the new LIVE button as the operator escape hatch.
7. Add a wire-format pin test (`Build*LuaCommand` returns expected
   string) so a future bridge-side rename or quote-style change fails
   at the dispatcher boundary, not at runtime.

**Specific lessons from iter 117-119**:

- The forward-grep `\bSWFOC_X\(` regex in
  `CapabilityCatalogReverseOrphanTests` matches textual occurrences in
  ANY editor source file — including XAML preset strings. So adding
  Lua Playground presets (iter 116) accidentally counted as "wired"
  for the reverse-orphan check. The actual operator-facing UX status
  is independent and must be tracked separately.
- The `CapabilitySurfaceReportIntegrationTests.GenerateReport_AcrossEvery21Tabs`
  regen path had an idempotency bug: it wrote the report from the OLD
  history, then appended a NEW entry to history. Next non-regen run
  loaded the new history and got a different trend line → mismatch.
  Fix: record history first, then reload, then regenerate. Now
  byte-stable across same-day regens.
- Two-Lua-expr signatures (iter 118 ChangeUnitOwner) and
  three-Lua-expr signatures (iter 119 SpawnUnitLua) follow the same
  outer-single-quote-wrap pattern as the iter 117 single-expr helpers.
  The dispatcher escapes single quotes per-arg independently. No
  shared escape state.