---
name: AllActions Count-Pin Drift Catches Late
description: Per-tab AllActions test pins (HaveCount + BeSameAs) drift silently when
  surfacing iters extend the list — full suite catches it; filtered runs do not
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-allactions-count-pin-drift
---

Tabs with `CapabilityAwareAction AllActions => new[] { ... }` lists have matching tests under `tests/SwfocTrainer.Tests/App/V2/ViewModels/<Tab>TabViewModelCapabilityTests.cs::AllActions_EnumeratesEveryActionInDeclaredOrder` that pin both the count and the order via `BeSameAs`. When a surfacing iter extends the AllActions list, the test must be updated alongside — but it's easy to miss because:

1. **Filtered test runs scoped to the iter being closed will pass** — if iter-208 only filters `Iter208|Iter207|WorldStateTabViewModel|CapabilitySurfaceReport`, the Camera/Combat tests aren't in the filter and the drift is invisible.
2. **The full suite catches it but goes silent if you stop running full suites** — when iter-192 added 4 actions to Camera and iter-193 added 4 to Combat, both AllActions tests started failing. Iter-194 through iter-207 closed iters with filtered runs only, never noticing.
3. **The drift accumulated across 14 iters before iter-208's full suite caught it** (iter-192 → iter-208 = 16 iter gap for Camera; iter-193 → iter-208 = 15 iter gap for Combat).

**Why:** Closing iters with filtered runs is genuinely faster (iter-208 filtered = 231ms vs full = 4 minutes). The trade-off is silent drift in unrelated capability tests. By the time the full suite runs, the failure is N iters old and the test author has long forgotten which iter introduced the new actions.

**How to apply:**
- When a surfacing iter touches a tab's AllActions list (`AllActions => new[] { ..., NewAction1, NewAction2 }`), ALWAYS update the matching `<Tab>TabViewModelCapabilityTests.AllActions_EnumeratesEveryActionInDeclaredOrder` in the same iter, not later. Bump `HaveCount(N)` and add the `BeSameAs(vm.NewAction)` index lines.
- Write the iter-208-style "stale-count drift catch" into the close-out doc when it happens (now.md + ralph_loop_state.md), so the next full-suite run isn't surprised.
- Periodic full-suite runs (every 5-10 surfacing iters) catch drift before it accumulates beyond ~2 iters of debt. iter-208 caught 14-iter-old drift — too late.
- The Camera/Combat AllActions tests have a recurring pattern of stale-count drift across surfacing arcs. Other suspects: Spawning (iter-203/206), WorldState (iter-201/202/204/208), Inspector (iter-191/197/198), PlayerState (iter-189/199), UnitControl (iter-188/194), Diagnostics (iter-190/205/207), Galactic (iter-200). When in doubt, run a full suite at the close of each major arc (every 5 iters) instead of pure filtered runs.
- This is the second occurrence: iter-195 (Spawning capability tests stale-count from iter-119, caught at iter-203 / 8-iter delay) + iter-208 (Camera + Combat stale-count from iter-192/193, caught at iter-208 / 15-16-iter delay). Pattern is recurring — institutionalize it via filtered + monthly-full mix, or add a CI gate that fails when AllActions count drifts vs the matching test.