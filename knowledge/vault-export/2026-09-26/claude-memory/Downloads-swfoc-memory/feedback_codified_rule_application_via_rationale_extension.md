---
name: Codified-Rule Application via Rationale Extension
description: When a codified rule applies to existing P2HP catalog entries, EXTEND
  each entry's rationale with rule reference + architectural identification + cost
  statement + (optional) LIVE alternative. ~5-6 LoC per entry; ~10 min batch cycle
  for 3-4 entries.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-codified-rule-application-via-rationale-extension
---

# Codified-Rule Application via Rationale Extension

**Rule**: When a codified rule (especially iter-426 event-driven defer, iter-302 engine-already-does-this, iter-407 static-data-extraction) APPLIES to existing Phase2HookPending catalog entries, EXTEND each entry's rationale string in `CapabilityStatusCatalog.cs` with a 4-component template:
1. **Cite the codified rule** explicitly (`per iter-NNN feedback_<rule_name>.md rule`)
2. **Identify the architectural shape** (e.g. `*BehaviorClass / *MonitorClass / DynamicVector<*::AwaitingTestType>` for event-driven; `EnumConversionClass<T>` for static-data; etc.)
3. **State the cost** (`multi-iter A1.x offset RE required` for event-driven; `metadata-only break-out` for clause-#6 static-data; etc.)
4. **(Optional) Cite LIVE alternative** if one exists (`alternative: iter-NNN SWFOC_<X>Lua LIVE wire ...`)

**Why**: Catalog rationale strings are reachable from MainViewModel/CapabilityStatusReport surfaces. They're the operator's PRIMARY surface for understanding what each PHASE 2 PENDING button means. Without explicit codified-rule references, operators must infer "why is this still pending?" from context. With the 4-component template, every P2HP entry self-documents its defer reason in operator-trust-grade detail.

This rule formalizes a workflow that emerged organically across iter-433 (4 entries) + iter-436 (3 entries) = 7 instances within 4 iters of pure NON-A1.x codified-rule application work.

**How to apply**:

1. **Identify candidate entries**: cross-reference codified rule's pre-classification table (e.g. iter-426 has 119 *BehaviorClass candidates; iter-302 has Lua-API candidates; iter-407 has static-data candidates) with current Phase2HookPending entries in `src/SwfocTrainer.Core/Diagnostics/CapabilityStatusCatalog.cs`.

2. **Pick 3-4 entries per iter** with CLEAREST architectural match (avoid ambiguous candidates that need RE to confirm).

3. **Extend each entry's rationale** using the 4-component template above. Preserve original rationale; APPEND with " " + new content.

4. **Verify republish** (cheap-insurance pattern; mirrors iter-434/iter-436):
   - dotnet publish (NON-incremental due to source change; binary timestamp advances)
   - filtered tests: CapabilityCatalogTests + Iter167/Iter223/Iter403 (~26 tests; ~250-350ms)
   - Confirm 0 CS warnings (catalog rationale strings are pure content; should never break build)

5. **Document close-out**: iter-N close-out doc citing codification rule's forward-application track + N-instance count + which entries extended.

**Examples** (7 instances at codification trigger):

| Iter | Catalog entry | Codified rule applied | Architectural shape | LIVE alternative cited |
|---|---|---|---|---|
| 433 | SWFOC_SpawnAsStoryArrival | iter-426 | StoryEvent system (event-driven) | (overlay Feature 2 already cited) |
| 433 | SWFOC_EventControl | iter-426 | Engine event queue (Observer pattern) | — |
| 433 | SWFOC_FreezeAI | iter-426 | UnitAIBehaviorClass per-tick | iter-162 SWFOC_SuspendAILua LIVE |
| 433 | SWFOC_SetPermadeath | iter-426 | DeathBehaviorClass tick + emit | — |
| 436 | SWFOC_SetAreaDamage | iter-426 | BarrageAreaBehaviorClass + AsteroidFieldDamageBehaviorClass per-tick | iter-96 SWFOC_SetDamageMultiplierGlobal LIVE |
| 436 | SWFOC_SetTargetFilter | iter-426 | UnitAIBehaviorClass per-tick target-selection | — |
| 436 | SWFOC_ToggleOHKAttackPower | iter-426 | CombatantBehaviorClass + DamageTrackingBehaviorClass per-tick | iter-96 SWFOC_SetDamageMultiplierGlobal LIVE |

All 7 instances applied iter-426 specifically. Future applications could apply iter-302 / iter-407 / other codified rules using the same template.

**Cost-benefit**:

- **Per-entry marginal cost**: ~5-6 LoC of rationale text (varies by complexity of architectural identification + LIVE-alternative citation).
- **Per-batch cycle time**: ~10 min for 3-4 entries (3-4 surgical Edits + cheap-insurance verify republish + close-out doc).
- **Operator trust gain**: each extended entry self-documents its defer reason + architectural shape + cost + alternative; operator no longer needs context to interpret PHASE 2 PENDING badges.
- **Audit-trail durability**: extensions preserve original rationale (additive only); future audits (iter-368 P2HP rule) can still verify entries unchanged from baseline.

**Relationship to iter-329 5-iter docs cleanup batch**:

iter-329 was the FIRST instance of "batch catalog rationale extensions" (5 entries from iter-324-328 drift-resolution arc). However, iter-329's rationales were **ad-hoc** (each entry got a custom note about the drift fix) rather than following a **codified-rule-templated** structure.

iter-433 + iter-436 are the FIRST batches following the formal 4-component template. The pattern crystallized when iter-426 codified the event-driven defer rule — applying iter-426 forward NATURALLY produced the 4-component template (rule citation + architectural shape + cost + alternative).

**Codification trigger**: 7/7 instances within 4 iters (iter-433 batch 4 + iter-436 batch 3). Matches iter-380's 7-instance Tier-1 codification precedent (`feedback_stale_groupbox_header_drift.md`). Per iter-388's 88-instance Tier-1 precedent, 7 is the LOWER bound for Tier-1; the rule is well above threshold.

**Tier**: 1 (production; describes concrete code-modification workflow that future operators will repeat ~5-10× per codified rule)

**Honest break-out cases**:

1. **Codified rule doesn't apply to ANY existing P2HP entries** — e.g. iter-302 (engine-already-does-this) doesn't apply to P2HP entries because P2HP-status implies the engine DOES NOT have a Lua API (otherwise the entry would be LIVE). Skip rationale-extension; the rule applies elsewhere (e.g. preflight stack, codification trigger).

2. **Entry's rationale already cites the LIVE alternative explicitly** (e.g. iter-251 SWFOC_FreezeCredits, iter-266 SWFOC_SpawnUnit, iter-130 SWFOC_SetHeroRespawn) — extending rationale with another iter-426 reference would be redundant and noisy. Skip.

3. **Entry is vestigial / deprecated mirror** (e.g. iter-137 SWFOC_ChangePlanetOwnerWithMode) — rationale explains WHY entry exists at all; no need to add rule reference unless the rule is the deprecation reason.

4. **NEW entries added vs EXTEND-existing** — when adding new catalog entries (vs extending existing), the 4-component template applies from creation. iter-435 close-out flagged option 2 ("apply iter-426 to NEW catalog entries") as a future pivot; that would be a SEPARATE workflow shape (additive vs extending).

5. **Rule's architectural shape is ambiguous for the entry** — e.g. iter-426 + SWFOC_SetIncomeMultiplier: economy subsystem could be event-driven (per-tick income calculation) OR command-class (Player:Add_Credits direct). Without RE, can't confirm. Skip and pursue RE-validation in separate iter.

**Cross-reference to other codified rules**:

- **iter-329 5-iter docs cleanup batch** is the precedent ad-hoc workflow (catalog rationale extensions for drift-resolution). iter-437 codifies the FORMAL template that emerged from iter-426 application.
- **iter-380 + iter-388 Tier-1 codification precedents** (stale-GroupBox-header + internal-codename-tooltips) — both targeted XAML strings in MainWindowV2.xaml. iter-437 targets C# string literals in CapabilityStatusCatalog.cs. SAME workflow shape (batch rationale-string updates) on a DIFFERENT surface.
- **iter-373 codified-rule-self-validates rule** — iter-437 IS the iter-373 rule's "Prospective uses" empirical feedback loop firing: iter-426 codification triggered iter-433 forward-application which triggered iter-436 forward-application which triggered iter-437 codification. Self-sustaining track.

**22nd codified rule** in the project's master-loop codification track. **8th Tier-1 production rule** (after iter-302/334/345/380/388/407 + iter-437 = 7 Tier-1; iter-302/334 are Tier-1 by content, listed). Continues iter-380/iter-388 batch-rationale-string-update workflow family.

**Future application**:

For each NEW codified rule that has pre-classified candidate inventory (e.g. iter-426's 120 RTTI candidates, iter-407's 41 EnumConversionClass<T> instances surveyed), expect ~5-10 rationale extensions following the iter-437 template. Track instance counts per codified rule:
- iter-426 forward-applied: 7 catalog rationale extensions (iter-433 + iter-436) — at iter-437 codification.
- iter-407 forward-applied: 0 catalog rationale extensions yet (P2HP entries don't directly map to static-data extractions; iter-407 applies via ledger pins instead).
- iter-302 forward-applied: rationale extensions would only fire IF an existing P2HP entry transitions to LIVE via Lua API discovery. Not yet observed.

The rule's PROSPECTIVE USES section will be filled by future codified rules' application tracks.