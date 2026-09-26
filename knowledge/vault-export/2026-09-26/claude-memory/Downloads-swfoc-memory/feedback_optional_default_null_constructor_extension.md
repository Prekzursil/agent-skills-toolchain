---
name: Optional-default-null constructor extension
description: Extend an existing constructor with an optional dependency defaulting
  to null + wire at composition root in a separate iter. Total cost ~3 LoC + tests;
  total ripple zero.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-optional-default-null-constructor-extension
---

When a new optional capability needs to flow into an existing class, extend the constructor signature with `Type? newDep = null` instead of breaking source-compat with a required parameter. Wire the real dependency at the composition root in a SEPARATE iter so the introduction iter and the integration iter are independently reviewable.

**Why:** When a multi-deep dependency tree (e.g. WPF MVVM with 20+ services at the root) needs a new dependency for one specific consumer, threading it through every test stub + every prior callsite is expensive. Optional-default-null lets the introduction iter ship without touching unrelated callers; the wiring iter ships the real value at the composition root only.

**How to apply:**
- Extend constructor: add `Type? newDep = null` as the LAST parameter (preserves positional compat)
- Use the optional dep behind a null check at use site (`_newDep?.DoSomething()`)
- Keep the param name self-documenting (e.g. `iconResolver`, not `resolver`)
- Add a comment block above the ctor explaining the iter-N intro + iter-M wiring split
- Pin the no-dep path with a test (`Constructor_WithoutNewDep_DoesNotThrow`)
- In the integration iter at the composition root, instantiate the dep and pass it explicitly
- Pin the with-dep path at the integration iter

**Instances (3 — codification trigger reached at iter-309):**
- iter-301: `SettingsTabViewModel(V2Settings settings, V2BridgeAdapter? bridge = null)` — added bridge for mod-picker without breaking 30+ existing test stubs
- iter-308: `SpawningTabViewModel(V2BridgeAdapter bridge, UnitIconResolver? iconResolver = null)` — added icon resolver for Spawning tab ListBox without breaking ~80 existing Spawning tests
- iter-309: composition-root wiring at `MainViewModelV2.ctor` calls `new SpawningTabViewModel(bridge, new UnitIconResolver(ResolveIconsRoot(settings)))` — completes both prior optional deps in 2 lines

**Edge cases:**
- **Don't use this for required dependencies.** If the class genuinely cannot function without the dep, fail fast (`ArgumentNullException`) instead of accepting null and silently degrading.
- **Don't chain >2 optional deps.** If a constructor has 3+ optional null-defaulting params, the API is signaling that the class has too many responsibilities. Refactor instead.
- **The "no-op when null" path must be operator-graceful.** iter-308 SpawningTab returns null IconPath which WPF binds to a hidden Image — operator sees no icons but no broken-image placeholder either. Test both paths.
- **In integration iters, wire eagerly** — don't lazily construct the dep inside the consumer. The composition root is the right place for object lifetime decisions.

**Cost-benefit:**
- Cost: 1-line signature change + 1-line composition-root edit + 2 pin tests (with-dep + without-dep)
- Benefit: zero ripple to existing callers; introduction iter ships independently of integration iter
- Anti-pattern cost: making the dep required would force updating N test stubs + N constructor callsites + breaking source-compat for downstream consumers

**Cross-link:** This rule is the constructor-side counterpart to iter-302 `feedback_engine_already_does_this` (which is about runtime dependency choices). Together they encode "small, additive changes at well-defined seams."