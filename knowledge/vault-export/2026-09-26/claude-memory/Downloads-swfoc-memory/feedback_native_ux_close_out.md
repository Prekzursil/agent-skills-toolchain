---
name: Native UX Close-Out for Bridge Wires
description: After landing a LIVE bridge wire, follow up with a per-tab native button
  surface (not just a Lua Playground preset) — operators shouldn't have to paste Lua
  to use a typed wire
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-native-ux-close-out
---

After a session where 17 LIVE wires landed with only Lua Playground presets as the operator surface (iter 100-113), the natural close-out (iter 117-119) was adding per-tab native buttons. Three patterns proved out:

**The "single Lua expression + many buttons" pattern (iter 117)**: When a tab has multiple bridge wires that all take the same first arg (a unit handle), surface them as a single TextBox + a WrapPanel of buttons. UnitControl tab's "Selected Unit Lua Actions" GroupBox does this for 7 wires (Make_Invulnerable / Hide / PreventAiUsage / SetSelectable / Despawn / Stop / Retreat). Marginal cost per new wire: ~3 lines of XAML + 1 dispatcher method (using a shared `BuildUnitLuaMethodCall` helper).

**The "two expressions side-by-side" pattern (iter 118)**: When a wire takes two Lua expressions (unit + target player), add a Separator and a second TextBox below the iter 117 GroupBox. Each arg has independent escaping (single quotes inside escape to `\'`).

**The "three expressions = its own GroupBox" pattern (iter 119)**: When a wire takes three+ Lua expressions (player + type + position for SpawnUnitLua), promote it to its own GroupBox with one TextBox per arg. The Spawning tab's existing PHASE 2 PENDING `SWFOC_SpawnUnit` button stays as-is; the iter 119 GroupBox is positioned as the LIVE alternative with banner copy explicitly directing operators ("Use the 'Spawn unit via Lua' section below for the LIVE alternative").

**Why:** Lua Playground presets (iter 116) prove the wire works but don't scale — operators don't want to memorize 21 different preset paths. A native button on the right tab is what makes the wire feel real.

**How to apply:**
- After a LIVE wire ships in the bridge + has its catalog flip + simulator handler + red-green tests, add a per-tab button as the close-out iter.
- For each new wire, write a `Iter<N><WireName>ShapeTests.cs` that pins the expected `return SWFOC_X('a', 'b', ...)` string format. That way a future bridge-side rename trips the dispatcher's red-green pair instead of waiting for the live game to mismatch.
- For each new dispatcher method or test, regen the capability surface report with `SWFOC_REGEN_CAPABILITY_SURFACE=1 dotnet test --filter "FullyQualifiedName~CapabilitySurfaceReportIntegrationTests.GenerateReport_AcrossEvery21Tabs"`. The regen path records history FIRST, re-loads, then writes the markdown — this fix landed iter 118 to make same-day regens byte-stable.
- The reverse-orphan test `CapabilityCatalogReverseOrphanTests` greps source for `\bSWFOC_X\(` patterns. Adding a button or a Lua Playground preset both count as "wired" from the regex's perspective. Drop entries from `KnownUnwiredEntries` when their textual SWFOC_* call site lands.
- Update the per-tab `AllActions` list with the new `CapabilityAwareAction` so the surface report counts the new buttons. Bumps the LIVE/PHASE 2 PENDING totals in the bottom-bar surface indicator.