---
name: Static-Data RE Extraction via Callgraph Mining
description: Extract program-lifetime engine constants (enum-to-string maps, RTTI
  tables, etc.) once at RE time + embed in C# const list. Cheaper than RVA pin + bridge
  wire when constants are stable across binary versions.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-static-data-re-extraction
---

# Static-Data RE Extraction via Callgraph Mining

**Rule**: When a SWFOC engine subsystem has a `static EnumConversionClass<T>` initializer (or analogous program-lifetime static-data builder), the embedded strings are program-lifetime constants. Extract them ONCE at RE time via callgraph + IDA decompile body mining; embed as a C# `IReadOnlyList<string>` const. **NO bridge wire needed.**

**Why**: Engine roundtripping (DoString into Lua API) costs ~30-50 LoC bridge + 1-2 ms per call. Static-data extraction costs 0 LoC bridge + 0 ms per call (the C# const list is in-process). For program-lifetime constants (enum mappings, RTTI tables, sprite-name registries), the engine never mutates them after init — so a one-time extraction at RE time is functionally equivalent to live querying.

**How to apply**:
1. Identify candidate cluster: grep `untouched_subsystems.md` for `EnumConversionClass<...>`, `RegistryClass<...>`, or similar single-function-per-cluster RTTI shapes
2. Confirm callgraph metadata: `python tools/callgraph_query.py fn <addr>` — expected shape is **1 caller** (program-init driver) + **10 callees** (operator_new + free + RegisterMapping + AppendEntry helpers)
3. Locate corpus file: read the `source` field from step 2 output (e.g. `full_b48-49.json`)
4. Extract strings: `python tools/extract_enum_conversion_strings.py <addr> <corpus_filename>` — returns IDA `aXxx` symbol-label refs
5. Add ledger entry via `tools/iter<N>_ledger_add.py` template (3-tool consensus via binary-fingerprint identity per iter-258/iter-404 precedent)
6. Verify lint clean: `python -m verifier lint` should report 0 errors / 0 warnings
7. **Optional UX consumer** — if a Lua wire exists for the enum (e.g. iter-156 `SWFOC_ActivateAbilityLua` for UnitAbilityType), ship a C# const list + ComboBox dropdown in the relevant V2 tab. Otherwise DEFER UX consumer with documented reason.

**Examples** (3 confirmed instances at 3/3 trigger):

| Iter | Target | Names | Function size | UX consumer status |
|---|---|---|---|---|
| 402-404 | `EnumConversionClass<UnitAbilityType>` @ 0x1405DEA20 | 69 | 7012 bytes | **SHIPPED** UnitControl Activate_Ability ComboBox (iter-403; 21/21 GREEN) |
| 405 | `EnumConversionClass<ModelAnimType>` @ 0x140279010 | 111 | 9313 bytes | **DEFERRED** — no Play_Animation Lua wire yet |
| 406 | `EnumConversionClass<GUIGadgetComponentType>` @ 0x1401D98B0 | 83 | 7743 bytes | **DEFERRED** — engine-internal UI rendering pipeline |

**Cumulative**: 263 engine-canonical strings extracted across 3 distinct enum types in ~70 min total.

**Honest break-out cases** (when this rule does NOT apply):

1. **Engine mutates the data after init**: extraction stale. Indicators — string-table Add/Remove callees in non-init contexts; mutable global vector pointer; "Reload" or "Refresh" call sites that re-populate the table. In these cases the bridge-wire roundtrip is correct.
2. **Constants change across binary versions**: per iter-256 AOB-drift rule, community-table AOBs are unreliable across versions. Static-data RE is OK as long as **same engine_build_hash** (StarWarsG.exe v1.121.13.7360) is enforced; ledger entry must pin the build hash. Future binary updates require re-extraction.
3. **Enum is small (<10 entries)**: not worth tooling; just hand-list in C# const.
4. **No UX consumer AND no near-term feature on the roadmap**: still extract for ground-truth ledger pin, BUT mark UX consumer as DEFERRED in close-out doc to avoid editor-surface inflation.
5. **Strings are user-facing localized text** (not engine identifiers): localization tables mutate per language; live engine query is required.

6. **EnumConversionClass<T> with NO RegisterMapping calls** (iter-410 empirically discovered; iter-425 generalized to non-template classes): the class instance is constructed with just the type-name string for serialization/diagnostics; enum values are integer-keyed without canonical string labels. Indicators: `strcpy(v2, "TypeName")` is the ONLY string in the asm body; zero `aXxx` symbol-label refs. Examples:
- `EnumConversionClass<DifficultyLevelType>` @ 0x1405DE400 (size 782 bytes; 0 names extracted) — iter-410
- `EnumConversionClass<ForceAlignmentType>` @ 0x1405DDAA0 (size 794 bytes; 0 names extracted) — iter-410
- `EnumConversionClass<MapEnvironmentType>` @ 0x1405E8770 (1409 bytes / zero refs) — iter-414 size-threshold refinement
- **`FactionTypeConverterClass`** @ 0x1403301A0 (size **549 bytes**; 0 names extracted; **NON-TEMPLATE** standalone class) — iter-425 finding

Pattern: skip extraction; the operator-facing strings come from XML config / localization tables / hardcoded labels in editor code (e.g. iter-322 Combat presets hardcode "Easy/Normal/Hard/Hardcore" because the engine doesn't expose them via this conversion class). **Diagnostic test (refined iter-414)**: zero `aXxx` refs in asm = metadata-only conversion class, REGARDLESS of function size. The reliable signal is **regex match count, not function size**. **Generalization (iter-425)**: this clause now covers BOTH template variants (`EnumConversionClass<T>`, `DynamicEnumConversionClass<T>`) AND non-template standalone classes (`FactionTypeConverterClass`) — the pattern is "config-driven type registry with no in-binary canonical names." Future operators: trust the zero-extraction count as the definitive metadata-only signal; defer to other RE workflow (XML config / localization / hardcoded labels).

7. **EnumConversionClass<T> with strings in error-handling paths only** (iter-410 empirically discovered; iter-424 generalized to bitfield variants): some clusters return error-handler strings (e.g. `aErrorCanTCreat` / `aErrorCanTOpenX`) when the regex picks up `aXxx` labels — these are DIAGNOSTIC strings for failure cases, not the canonical enum-value names. Examples:
- `EnumConversionClass<GameObjectCategoryType>` @ 0x14046AD50 (size 1521 bytes; 5 strings extracted but ALL are error-handler diagnostic strings) — original iter-410 finding
- **`DynamicBitfieldConversionClass<GameObjectCategoryType>` @ 0x14046AD50** (size 1521 bytes; **same 5 ERROR strings as enum variant**) — iter-424 finding
- **`DynamicBitfieldConversionClass<GameObjectPropertiesType>` @ 0x14046B350** (size 1521 bytes; **same 5 ERROR strings**) — iter-424 finding
Pattern: validate extracted strings before accepting — they should look like enum-values (Title_Case_Underscores) not error messages (Error_Cant_Create_Foo). **The bitfield template family (`DynamicBitfieldConversionClass<T>`) shares the same parser-error template as the enum family (`EnumConversionClass<T>`) for the GameObjectCategoryType/PropertiesType cases** — actual flag names live in XML data files (matching iter-411 clause #8 architecture for DynamicEnumConversionClass<T>).

8. **`DynamicEnumConversionClass<T>` does NOT generalize to this recipe** (iter-411 empirically validated): the engine has TWO distinct conversion-class families. `EnumConversionClass<T>` = STATIC registration at program-init via RegisterMapping calls (recipe applies). `DynamicEnumConversionClass<T>` = RUNTIME parsing from XML config files (recipe does NOT apply — strings live in `data/xml/<typename>.xml`, not the binary). **Diagnostic test**: all 5 `DynamicEnumConversionClass` template instantiations tested at iter-411 (AIGoalCategoryType / MovementClassType / ObjectWeatherCategoryType / PerceptionTokenType / SurfaceFXTriggerType) returned identical 4 error-handler strings (aErrorCanTCreat / aErrorCanTOpenX / aErrorCouldnTAd / aErrorEnumEntry) and identical 1998-byte function size — proves they're template instantiations of a generic XML-loader, not per-type registration code. **Workflow for Dynamic variant**: walk `<game-data-dir>/data/xml/` looking for the matching `<typename>.xml` config file; parse XML for enum-value-name pairs. Different RE methodology entirely.

**Cost-benefit**:
- **First extraction** (iter-402-404 mini-arc): ~50 min (RE + tooling buildup + implementation + republish + ledger). Most cost is one-time tool development.
- **Second extraction** (iter-405): ~10 min (tooling generalized; just `python extract_enum_conversion_strings.py <addr> <file>` + ledger).
- **Third+ extraction** (iter-406): ~5-10 min (mechanical; ledger script is template-able).
- **Marginal cost trends to ~5 min** as tooling matures.
- **Operator value**: 263 cumulative strings shipped via this pattern; iter-403 UnitControl ComboBox alone removes "memorize SWFOC ability names" friction for every operator session forever.
- **vs RVA pin + bridge wire alternative**: ~50 min RE + ~30-50 LoC bridge wire + ~5 LoC simulator handler + ~20 LoC editor consumer + ~10 LoC pin tests = ~200 LoC + ~2 hours per enum. Static-data extraction is **5-10× cheaper** for program-lifetime constants.

**Cross-reference to other codified rules**:
- **iter-302** `feedback_engine_already_does_this.md`: this rule is a TIER-2 EXTENSION of iter-302. Original iter-302 covers "engine has Lua API → DoString" (live roundtripping). This iter-407 rule covers "engine has STATIC DATA → extract once + embed" (no roundtripping). Decision tree: live data → iter-302; constant data → iter-407.
- **iter-256** `feedback_aob_drift_across_binary_versions.md`: applies to RVA-pin-based wires, NOT static-data extraction. Different pattern, complementary recipe (both use callgraph + IDA decompile body workflow).
- **iter-302** + **iter-407** together cover the full "use what the engine already provides" taxonomy: live API + static data. Future codification candidate is "engine has FILESYSTEM data → walk directory" which would extend the family further (iter-300 SWFOC_ListMods is the 1st instance of that 3rd tier).

**Codification trigger**: 3/3 (iter-402-404 / iter-405 / iter-406). Pattern stable across 3 distinct EnumConversionClass instances with same callee shape (operator_new + free + RegisterMapping × N).

**4th+ candidates** (untouched_subsystems.md still has — extract opportunistically):
- `EnumConversionClass<UnitCategoryType>` (if exists; not yet checked in untouched index)
- `EnumConversionClass<ProjectileType>` (if exists)
- `EnumConversionClass<DamageType>` (if exists)
- Other RTTI clusters with single-function-per-cluster + 1-caller / 10-callee shape

Each future extraction ships at ~5-10 min via the established tooling.