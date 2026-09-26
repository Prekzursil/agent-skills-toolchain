---
name: Resolver-Injection-At-Composition-Root Pattern
description: When a tab VM needs to consume a shared service (UnitIconResolver, V2BridgeAdapter,
  V2UnitMutationDispatcher), follow the 3-step composition root injection pattern
  — optional ctor param + SetIconResolver hot-swap method + MainViewModelV2 wire-up
  + OnSettingsPropertyChanged hot-swap chain. Validated stable at 8 instances (iter-308/309/312/317/318/319/321/344)
  — highest evidence base of any codified rule.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-resolver-injection-at-composition-root
---

**Rule:** When a tab ViewModel needs to consume a shared service (e.g. `UnitIconResolver` for icon resolution, but applies generally to any per-tab-injectable service), follow the 3-step composition root injection pattern:

1. **Tab VM ctor extension** (per iter-311 codified `feedback_optional_default_null_constructor_extension`):
   ```csharp
   public TabXxxViewModel(
       V2BridgeAdapter bridge,
       /* ... required deps ... */,
       UnitIconResolver? iconResolver = null)  // optional, defaults to null
   {
       _iconResolver = iconResolver;  // capture for use in commands
       // ...
   }
   ```

2. **SetIconResolver hot-swap method** on the tab VM (mirror iter-312 + iter-321 pattern):
   ```csharp
   public void SetIconResolver(UnitIconResolver? iconResolver)
   {
       _iconResolver = iconResolver;
       // Optional: re-resolve any in-flight rows (per iter-321 AssetBrowser pattern)
       // OR leave dormant until next operator-driven Refresh (per iter-344 Combat pattern)
   }
   ```

3. **MainViewModelV2 wire-up + hot-swap chain** in 2 places:
   - **Ctor**: pass shared `iconResolver` instance to tab VM ctor:
     ```csharp
     TabXxx = new TabXxxViewModel(bridge, /* deps */, iconResolver);
     ```
   - **OnSettingsPropertyChanged(IconsRoot)**: add to existing hot-swap chain:
     ```csharp
     var newResolver = new UnitIconResolver(newRoot);
     // ... existing tabs ...
     TabXxx.SetIconResolver(newResolver);  // append to chain
     ```

**Why:**

8 instances across iter-308 → iter-344 (~36-iter window) prove the pattern stable across distinct tab shapes:

| Iter | Tab | Service injected | Hot-swap behavior |
|---|---|---|---|
| iter-308 | Spawning | UnitIconResolver | Re-resolves rows on hot-swap |
| iter-309 | MainViewModelV2 (composition root) | UnitIconResolver | Creates resolver from Settings.IconsRoot |
| iter-312 | All consumers | UnitIconResolver | Live VM rebuild on Settings.IconsRoot change |
| iter-317 | Galactic | UnitIconResolver | Re-resolves rows on hot-swap |
| iter-318 | HeroLab | UnitIconResolver | Re-resolves rows on hot-swap |
| iter-319 | PlayerState | UnitIconResolver | Re-resolves rows on hot-swap |
| iter-321 | AssetBrowser | UnitIconResolver + iconsRoot | Re-resolves rows on hot-swap |
| iter-344 | Combat | UnitIconResolver | Dormant until next Refresh (operator-driven) |

**8 instances is the HIGHEST EVIDENCE BASE of any codified rule in the project.** iter-302 codified at 6 instances; iter-334 codified at 6 instances; iter-337 codified at 3 instances (meta-level pattern). iter-345 codifies at 8 — well over the iter-302 6-instance precedent.

Without this rule, future tab additions consuming shared services would re-derive the 3-step pattern (~15-30 min cycle waste per instance) AND introduce drift risk (tabs forgetting hot-swap → operator changes Settings + sees stale state).

**How to apply:**

When adding a new tab VM that needs UnitIconResolver (or analogous shared service):

1. **Step 1 — Tab VM ctor extension** (~3 LoC):
   ```csharp
   private UnitIconResolver? _iconResolver;
   public TabXxxViewModel(V2BridgeAdapter bridge, /* ... */, UnitIconResolver? iconResolver = null)
   {
       _iconResolver = iconResolver;
       // ...
   }
   ```

2. **Step 2 — SetIconResolver hot-swap method** (~3-15 LoC depending on re-resolution behavior):
   ```csharp
   public void SetIconResolver(UnitIconResolver? iconResolver)
   {
       _iconResolver = iconResolver;
       // Optional re-resolution behavior (see "Hot-swap behavior choice" below)
   }
   ```

3. **Step 3 — MainViewModelV2 wire-up** (~2 LoC):
   - Ctor line: `TabXxx = new TabXxxViewModel(bridge, /* deps */, iconResolver);`
   - Hot-swap line: `TabXxx.SetIconResolver(newResolver);` (append to existing chain in OnSettingsPropertyChanged)

4. **Step 4 — Pin tests** (optional ~2-4 facts):
   - Tab VM ctor accepts null iconResolver (graceful default)
   - Tab VM ctor accepts non-null iconResolver (happy path)
   - SetIconResolver hot-swap updates internal state
   - (For tabs with re-resolution) hot-swap re-resolves in-flight rows

**Hot-swap behavior choice (2 patterns):**

- **Pattern A — Eager re-resolution** (iter-308/317/318/319/321 — most common): SetIconResolver iterates the tab's in-flight rows and re-resolves IconPath for each. Operator sees icons change immediately when Settings.IconsRoot changes.
- **Pattern B — Dormant** (iter-344): SetIconResolver only updates the field; rows don't re-resolve until the operator clicks Refresh. Useful when re-resolution is expensive or row population is manual (operator types obj_addr).

**Decision tree**: choose Pattern A when rows are auto-populated from a stable source (e.g. SWFOC_GetPlanets refresh in Galactic tab); choose Pattern B when rows depend on operator input (e.g. Combat tab Hardpoint Inspector requires obj_addr).

**Honest break-out clause** — when this rule does NOT apply:

- **Singleton lifecycle services**: services that are per-application not per-VM (e.g. `Settings`, `BridgeConnectionMonitor`) are injected via constructor as required dependencies, not via the optional-default-null + hot-swap pattern
- **Service has 1 consumer ever**: when a service is consumed by exactly 1 tab VM and unlikely to be added to others, skip the SetIconResolver hot-swap method (operator gets a fresh service per session start)
- **Service requires async initialization**: services that need async setup (`await InitializeAsync()`) don't fit the synchronous SetXxx hot-swap pattern; use a different injection mechanism (e.g. async factory)
- **Service is stateless / immutable**: stateless services don't need hot-swap because there's no state to swap; pass via DI / static reference

**Edge cases worth flagging:**

- **Hot-swap timing**: when MainViewModelV2 hot-swap chain runs, ensure the new service instance is fully constructed BEFORE calling SetIconResolver on each tab. If construction can fail, catch + log + leave existing resolver in place
- **Threading**: SetIconResolver should be safe to call from the UI thread (most cases); if the tab VM does background work, ensure thread safety via lock or Interlocked.Exchange
- **Test isolation**: tests should construct tab VMs without resolver (pass null) to validate graceful default behavior; integration tests can construct with real resolver
- **Iter-321 prefix-overlap finding**: when extending the resolver itself with new prefixes (per iter-313 LocateByConvention plugin set), test for prefix-overlap at the consumer layer — the producer-layer resolver is fine but the consumer-layer file walker may over-match
- **Composition root growth**: as the chain grows (iter-344 = 6 consumers), the OnSettingsPropertyChanged hot-swap method becomes longer. Refactor into a dedicated method when it crosses ~20 lines

**Cost-benefit ratio:**

- **Per-tab marginal cost**: ~5-15 LoC source + ~2-4 pin tests + ~5-10 min cycle from "decide to add resolver consumption" to "filtered tests GREEN"
- **Without the rule**: each tab would re-derive the 3-step pattern (~15-30 min per tab) + risk forgetting hot-swap (operator-facing bug) + risk constructor breaking change (each ctor change ripples through tests)
- **Rule application factor**: **~2-3× faster per tab** AFTER the first 2 instances + zero hot-swap drift across the chain
- **Cumulative savings across 8 instances**: ~2-4 hours of operator/agent time + zero hot-swap drift bugs over ~36-iter window

**Memory-write triggers** (8-instance evidence base):

- **8 instances** across iter 308-344 (~36-iter window) is the HIGHEST evidence base of any codified rule. Pattern survived 8 distinct tab shapes (Spawning ListBox + Galactic DataGrid + HeroLab DataGrid + PlayerState ComboBox + AssetBrowser DataGrid + Combat ListBox + ...) and 2 hot-swap patterns (eager + dormant).
- **iter-344 was the 8th instance + the trigger for codification**. Future incidents (instance #9+) should EXTEND this rule rather than create new ones — most likely add a row to the table above with the new tab's hot-swap behavior pattern (Pattern A or Pattern B).
- **If a 9th tab needs a NEW hot-swap pattern** (e.g. Pattern C — async re-resolution), document it under "Hot-swap behavior choice" rather than creating a new rule.

**Prospective uses (iter-346+):**

When the next tab VM needs to consume UnitIconResolver, follow this rule:

- **Inspector tab**: would benefit from icon resolution if it ever shows a unit-name field that maps to a unit icon (currently shows engine pointer + raw type addresses; Pattern B if added)
- **WorldState tab**: would benefit if story-event entries get faction-affiliation icons (Pattern A if added)
- **Director Mode tab**: would benefit if waypoint targets show unit-type icons (Pattern A if added)
- **Settings tab**: already wires the resolver indirectly via Settings.IconsRoot; doesn't need direct injection

For NEW shared services beyond UnitIconResolver:

- **V2BridgeAdapter** (existing): already injected per this pattern in all consumer tabs (V2BridgeAdapter is the original instance of the 3-step pattern; iter-308 generalized to UnitIconResolver)
- **V2UnitMutationDispatcher** (existing): same pattern; injected in tabs that need engine mutations
- **NEW services**: codification candidate `feedback_resolver_injection_at_composition_root.md` extends to any per-tab-injectable shared service

**Pattern reinforcement:**

This rule is the **service-injection companion** to:
- `feedback_optional_default_null_constructor_extension.md` (iter-311 codified) — ctor extension WITHOUT breaking source-compat
- `feedback_status_badge_as_inline_docs.md` (iter-311 codified) — operator-trust UX for the badge surface
- `feedback_locate_by_convention_extensible.md` (iter-334 codified) — adds a 7th asset class plugin (next abstraction layer)
- `feedback_iter_strategy_preflight_stack.md` (iter-337 codified) — applies preflight to confirm composition-root pattern is well-precedented

Combined: when adding a new tab VM that needs a shared service, the iter-345 rule says HOW (3-step pattern) + iter-311 says WHEN to extend ctor (optional default null) + iter-337 says CHECK existing precedent before deviating.

**Cross-link to related codified rules:**

- `feedback_optional_default_null_constructor_extension.md` (iter-311) — ctor extension mechanism
- `feedback_status_badge_as_inline_docs.md` (iter-311) — UX side of the same composition root extension
- `feedback_extract_on_second_use.md` (iter-316) — when to extract the SetIconResolver pattern itself (was extracted at 2nd use)
- `feedback_locate_by_convention_extensible.md` (iter-334) — producer-side of icon resolution
- `feedback_iter_strategy_preflight_stack.md` (iter-337) — preflight discipline; check this rule first when adding new tab service injection
- `feedback_engine_already_does_this.md` (iter-302) — analogous codification at wire-design layer (6-instance precedent that this rule extends to 8)
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running the filtered test suites this rule recommends