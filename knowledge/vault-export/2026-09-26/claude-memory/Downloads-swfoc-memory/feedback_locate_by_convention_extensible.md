---
name: LocateByConvention Plugin Set Extension Pattern
description: When adding a new asset class to UnitIconResolver, mirror the iter-313
  pattern exactly (Resolve<X> → Locate<X>Dds → LocateByConvention(prefix, name)) plus
  11 pin tests covering null/empty/canonical/N-way-discriminator/N-way-symmetry/cached/default-arg/cache-missing/unsupported-size/not-present/N-way-co-existence.
  Validated stable at N=6 plugins.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-locate-by-convention-extensible
---

**Rule:** When adding a new asset class to `UnitIconResolver` (in `SWFOC editor/src/SwfocTrainer.Core/Assets/UnitIconResolver.cs`), mirror the iter-313 plugin pattern exactly:

1. **Add 2 public methods + 1 line to class XML doc**:
   - `public string? Resolve<X>(string assetName, int size = N)` — caches the lookup via `ThumbnailCache.GetCachedPathOrNull(ddsPath, size)` with try/catch ArgumentException → null
   - `public string? Locate<X>Dds(string assetName) => LocateByConvention("<prefix>_", assetName)`
   - 1-line addition to class XML doc: `///   - <X> icons: <c>i_<prefix>_&lt;Name&gt;.dds</c> (iter <N>, default size <N>)`
2. **Add a test file** `tests/SwfocTrainer.Tests/Core/Assets/Iter<N><X>IconResolverTests.cs` with **exactly 11 facts** mirroring the iter-313/314/315/331/332 shape (see "How to apply" below for the full template).
3. **Mark the test class with `[Collection("ThumbnailCacheEnv")]`** for env-var orthogonality with all other thumbnail-cache tests.

**Why:**

6 instances across the iter-308 → iter-332 window (~25-iter span) prove this pattern is stable for arbitrary asset classes:

| Iter | Asset class | Resolver method | Filename prefix | Default size | Marginal LoC (src + test) |
|---|---|---|---|---|---|
| iter-308 | Unit icons | `Resolve(unitTypeName)` | `i_button_` | 32 | ~70 + ~250 (kickoff includes helper) |
| iter-313 | Hero portraits | `ResolvePortrait(heroName)` | `i_portrait_` | 64 | ~50 + ~225 |
| iter-314 | Faction emblems | `ResolveFactionEmblem(factionName)` | `i_faction_` | 48 | ~50 + ~225 |
| iter-315 | Planet icons | `ResolvePlanetIcon(planetName)` | `i_planet_` | 96 | ~50 + ~225 |
| iter-331 | Weapon hardpoints | `ResolveWeaponIcon(weaponName)` | `i_button_hp_` | 32 | ~50 + ~225 |
| iter-332 | Ability icons | `ResolveAbilityIcon(abilityName)` | `i_button_ability_` | 32 | ~50 + ~225 |

Without the rule, each plugin would have independently re-derived the locator-cache-fallback pattern, the 11-test pin shape, and the env-var collection wiring — wasting ~30-60 min per plugin AND introducing drift risk between plugins. The iter-313 LocateByConvention helper itself eliminated the duplicated-walk drift inside the resolver; the test pattern + class-doc pattern eliminate it at the consumer/regression layer.

**How to apply:**

For a new asset class `<X>` with prefix `i_<prefix>_` and default size `<N>`:

1. **Add to UnitIconResolver.cs** (~50 LoC; mirror iter-331 ResolveWeaponIcon block exactly):
   ```csharp
   /// <summary>
   /// 2026-MM-DD (iter NNN): &lt;X&gt;-icon counterpart to <see cref="Resolve"/>.
   /// Returns the cached thumbnail PNG path for ... at <paramref name="size"/>.
   /// </summary>
   public string? Resolve<X>(string assetName, int size = <N>)
   {
       if (_extractedDdsRoot is null || string.IsNullOrWhiteSpace(assetName))
           return null;
       var ddsPath = Locate<X>Dds(assetName);
       if (ddsPath is null) return null;
       try
       {
           return ThumbnailCache.GetCachedPathOrNull(ddsPath, size);
       }
       catch (ArgumentException) { return null; }
   }

   public string? Locate<X>Dds(string assetName)
       => LocateByConvention("<prefix>_", assetName);
   ```

2. **Update the class XML doc table** (1 line): add the new asset class row to the "Filename conventions used" enumeration.

3. **Create the pin test file** `tests/SwfocTrainer.Tests/Core/Assets/Iter<N><X>IconResolverTests.cs` with exactly these **11 facts** (mirror iter-332 for the most-recent template):

   - `Resolve<X>_NullRoot_ReturnsNull` — graceful null contract when no IconsRoot configured
   - `Resolve<X>_Empty<X>Name_ReturnsNull` — empty + whitespace string coverage
   - `Locate<X>Dds_FindsAtCanonicalPath` — happy path
   - `Locate<X>Dds_DoesNotMatchOther<N-1>Conventions` — **strict N-way prefix discriminator** (stage all prior-convention files for the same NAME; only the new prefix should match)
   - `Other<N-1>Convention_Resolvers_DoNotMatch<X>Convention` — **reverse N-way symmetry** (stage the new prefix; verify NONE of the prior resolvers match it)
   - `Resolve<X>_DdsExists_AndCachePopulated_ReturnsCachedPath` — happy path through cache
   - `Resolve<X>_DefaultSize_Is<N>_<distinguishing-text>` — **default-arg pin** (catches consolidation refactors that drift the default; mention which other classes share or don't share the default size)
   - `Resolve<X>_DdsExists_CacheMissing_ReturnsNull` — graceful-null contract mirror
   - `Resolve<X>_UnsupportedSize_ReturnsNull_DoesNotThrow` — exception safety
   - `Locate<X>Dds_NotPresent_ReturnsNull` — happy-null path
   - `All_<N>_AssetClasses_CoExist_AtSameDir_WithoutCollision` — **end-to-end N-way validation** (stage 1 file per category for the same NAME; verify N distinct paths from N resolvers)

4. **Mark with `[Collection("ThumbnailCacheEnv")]`** at class level. Set up tempdir-per-test in constructor; clean in `Dispose`. Save/restore `SWFOC_THUMB_CACHE` env var.

5. **Run filtered test suite**: `dotnet test --filter "FullyQualifiedName~Iter307|...|Iter<N>"` via PowerShell `Start-Process` wrapper (Clink-bypass per `feedback_dotnet_test_hang_diagnosis`). Expect 11 new + cumulative 11×N pass in <2.5s.

**Honest break-out clause** — when this rule does NOT apply:

The rule applies to NEW asset classes that follow the SWFOC `i_<prefix>_<assetname>.dds` filename convention. It does NOT apply when:

- **Non-DDS extensions** (e.g., audio cues `*.wav`, video clips `*.bik`, text manifests `*.xml`): would need a new helper not built on `LocateByConvention(prefix, name)` returning `<prefix><name>.dds`. iter-313 helper signature is DDS-extension-locked.
- **Multi-file asset classes** (e.g., a unit needing both `i_button_X.dds` AND `i_select_X.wav`): would need a new compound resolver method that locates multiple files and returns a record. The 11-test pin pattern would need extension to cover the compound shape.
- **Dynamically-generated assets** (e.g., engine-rendered icons that don't exist as DDS files on disk): no filesystem walk applies; must use a different mechanism (e.g., engine screenshot capture, dynamic texture extraction).
- **When iter-333-style consumer-layer prefix overlap risks exist**: if the new prefix is a SUBSTRING of an existing prefix (e.g., adding `i_button_special_` when `i_button_` already exists), follow the iter-333 prefix-overlap audit pattern at the consumer layer (longest-prefix-first ordering + HashSet claim tracking). The producer-layer LocateByConvention helper itself is unaffected — it uses literal-prefix non-glob filename matching.

**Edge cases worth flagging:**

- **Prefix-overlap at the consumer layer (iter-333 finding)**: the iter-321 AssetBrowserTabViewModel walker uses glob-based `Directory.EnumerateFiles(root, $"{prefix}*.dds", SearchOption.AllDirectories)` which has SUPERSET semantics. When iter-333 added weapons (`i_button_hp_`) and abilities (`i_button_ability_`), the existing unit walker (`i_button_*.dds`) would have over-matched both. Fix: longest-prefix-first ordering of `CategoryPrefixes` array + `HashSet<string>` tracking claimed DDS paths. **The producer-layer LocateByConvention helper is unaffected** because it uses literal non-glob filename matching (`{prefix}{name}.dds`).
- **Default size sharing is OK**: at iter-332 N=6, three asset classes (units + weapons + abilities) share the size-32 default because they render at the same scale in the SWFOC unit-detail UI. Pin the shared default with a test that mentions which other classes share or don't share the size — catches consolidation refactors that drift the default but doesn't enforce uniqueness.
- **N-way discriminator scales**: at N=6, the discriminator + symmetry + co-existence triplet generates ~30 directional assertions worth of coverage at runtime, but only 3 test methods at the source layer. Cost stays linear.
- **Hot-swap correctness**: every consumer of `UnitIconResolver` must call `SetIconResolver(newResolver)` for the new instance to propagate; verify with a `Hot_Swap_RebuildsRows` test (iter-312/iter-321 pattern).
- **Composability with iter-321 Asset Browser**: every new asset class MUST also be added to `AssetBrowserTabViewModel.CategoryPrefixes` array (longest-prefix-first) + the `ResolveIconForCategory` switch + the iter-321 test count assertion. Without this, the Asset Browser tab becomes inconsistent with the resolver's plugin set.

**Cost-benefit ratio:**

- **Per-plugin marginal cost (iter-313/314/315/331/332)**: ~50 LoC source + ~225 LoC tests = ~275 LoC total. ~30 min cycle from "decide to add asset class X" to "filtered tests GREEN + close-out doc shipped".
- **Without the rule**: each plugin would have re-derived the resolver pattern (~30-60 min wasted re-discovering the cache-fallback shape) + the test pattern (~30-60 min wasted re-deriving the 11-fact coverage matrix) + the env-var collection wiring (~5-15 min wasted on parallelization flakes) = ~65-135 min per plugin BEFORE drift catches.
- **Rule application factor: ~2-4× faster** per plugin AFTER the first 2 instances. Cumulative savings across 6 instances ≈ ~6-12 hours of operator/agent time.

**Memory-write triggers** (don't skip codifying when these fire):

- 6 instances across ~25 iters is enough recurrence to abstract — mirrors iter-302 `feedback_engine_already_does_this` 6-instance precedent.
- Future incidents (instance #7+) should EXTEND this rule rather than create new ones. Add a row to the table above. If a 7th asset class surfaces (e.g., build-tab category icons, ranking medal icons, cooldown overlay icons), it should ship at the validated ~50 LoC source + ~225 LoC test marginal cost.
- If a 7th instance surfaces a NEW shape constraint (e.g., compound multi-file assets, non-DDS extensions), document it under "Honest break-out clause" rather than creating a new rule.

**Prospective uses (iter-334+):**

- **Build-tab category icons** (e.g., `i_buildtab_<category>.dds`) — SWFOC has Land / Space / Infantry / Vehicle / Aircraft tab buttons; would extend the plugin set to N=7.
- **Ranking medal icons** (e.g., `i_rank_<level>.dds`) — for hero veterancy displays; N=8.
- **Cooldown overlay icons** (e.g., `i_cooldown_<state>.dds`) — for ability/weapon cooldown UI; N=9.
- **Cursor icons** (e.g., `i_cursor_<state>.dds`) — for context-sensitive mouse cursors; N=10.

Each would slot into the iter-313 LocateByConvention plugin set at the validated ~50 LoC source + ~225 LoC test marginal cost.

**Pattern reinforcement:** this rule is the **producer-layer companion** to the consumer-layer pattern lessons surfaced by iter-333 (`feedback_glob_walker_prefix_overlap_audit` + `feedback_consumer_extensibility_audit`). Producer extensibility is clean (each plugin uses literal-prefix non-glob matching); consumer extensibility needs more audit (glob walkers + default-arg inheritance + hot-swap correctness). Both rules are siblings — when adding a new asset class, follow this rule at the producer layer, then audit consumers per the iter-333 finding before declaring the new plugin shipped end-to-end.

**Cross-link to related codified rules:**

- `feedback_engine_already_does_this.md` (iter-302 codified at 6-instance trigger) — same codification cadence; both prefer cheap-existing-mechanism over re-derivation.
- `feedback_aob_drift_across_binary_versions.md` (iter-256 codified) — different domain (RVA pinning) but same "validate before committing" philosophy at the iter-strategy layer.
- `feedback_infra_claim_drift_bidirectional.md` (iter-283 codified) — 5-second-grep discipline; combined with this rule, both prevent re-derivation waste at iter-design-time.
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172 codified) — toolchain rule for running the filtered test suite this rule recommends.