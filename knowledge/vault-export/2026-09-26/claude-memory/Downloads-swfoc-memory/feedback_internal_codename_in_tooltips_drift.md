---
name: Internal-Codename-In-Tooltips-Drift Pattern
description: WPF Button.ToolTip text with `iter <N> LIVE — ` prefix surfaces internal
  iter codenames to operators. Per-button capability badges already convey LIVE/PHASE2
  status; the prefix is internal traceability noise. Validated at 88 instances across
  5 V2 tabs (UnitControl/PlayerState/Inspector/Galactic/Combat) iter-382/383/384/385/386/387.
  Tier 1/2 production-pattern codification — sibling to iter-380 stale-header rule.
  Same root cause (internal codename leakage), different element (ToolTip vs GroupBox.Header).
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-internal-codename-in-tooltips-drift
---

**Rule:** When a WPF Button or other operator-facing control has a `ToolTip` attribute that begins with `iter <N> LIVE — ` (or variant capitalization/format), the prefix MUST be removed. Capability badges (LIVE / PHASE 2 PENDING / LIVE-ONLY indicators on the per-button `<TextBlock Text="{Binding *.Badge}">`) ALREADY surface the wire's status. The `iter N` prefix is internal traceability noise — operators don't recognize iter codenames; they need the description of WHAT the button does, not WHEN it was added.

**Default tooltip conventions to AVOID:**

```xaml
<!-- BAD: tooltips with iter-N prefix; capability badge already shows LIVE -->
<Button ToolTip="iter 110 LIVE — calls (unit):Make_Invulnerable(true) via DoString. Propagates to all hardpoints." />
<Button ToolTip="iter 154 LIVE — (unit):Heal() no-arg. Restores the unit to full hull." />
<Button ToolTip="Iter 96/100 LIVE — Take_Damage_Outer detour scales damageParams[0]" />
<Button ToolTip="iter 169 LIVE — calls (player):Get_Credits(). Returns current credit balance." />
<Button ToolTip="iter 175 LIVE — (taskforce):Move_To(target). Distinct from iter-157 SWFOC_MoveToLua." />
```

**Default tooltip conventions to PREFER:**

```xaml
<!-- GOOD: drop the iter-N prefix; keep operator-relevant description -->
<Button ToolTip="Calls (unit):Make_Invulnerable(true) via DoString. Propagates to all hardpoints." />
<Button ToolTip="Calls (unit):Heal() no-arg. Restores the unit to full hull." />
<Button ToolTip="Take_Damage_Outer detour scales damageParams[0]" />
<Button ToolTip="Calls (player):Get_Credits(). Returns current credit balance." />
<Button ToolTip="Calls (taskforce):Move_To(target). Distinct from unit-receiver SWFOC_MoveToLua." />
```

**Cross-references in tooltips also need cleanup** (per iter-377 Pattern 6 inventory):

```xaml
<!-- BAD: cross-references to iter-N -->
ToolTip="...Read-after-write pair with iter-155 PlayerGiveMoney."
ToolTip="...Reuses iter-199 OtherPlayerLuaExpr."
ToolTip="...Pairs with iter-212 Bribe."

<!-- GOOD: demote to operator-relevant button names -->
ToolTip="...Read-after-write pair with PlayerGiveMoney."
ToolTip="...Reuses Is_Enemy/Is_Ally OtherPlayerLuaExpr."
ToolTip="...Pairs with Bribe."
```

**Why:**

88 instances across iter-382 → iter-387 (~6-iter window) prove the pattern is widespread:

| Iter | Tab | Sub-batches | Tooltips fixed | Cross-refs demoted |
|---|---|---|---|---|
| iter-382 | UnitControl row 7 part 1 | iter 110/111/112 + iter 167/171/172 | 15 | 0 |
| iter-383 | UnitControl row 7 part 2 | iter 118/153/156/157/162/163/180/218 | 24 | 3 |
| iter-384 | PlayerState row 4 | iter 160/161/164/169/170/179/182 | 16 | 11 |
| iter-385 | Inspector row 1 | iter 168/169/171/172/173/174 | 14 | 8 |
| iter-386 | Galactic TaskForce mega-batch | iter 175/176/218 | 10 | 6 |
| iter-387 | Combat tab | iter 96/100/154/162/225/227/281 | 9 | 5 |
| **TOTAL** | **5 V2 tabs** | **~25 sub-batches** | **88** | **33** |

**88 instances MASSIVELY exceeds 6-instance Tier 1/2 codification threshold** per iter-302/334/345/380 production-pattern precedent. **Strongest empirical foundation of any codified rule in the project** (prior record: iter-345 resolver-injection rule at 8 instances; this rule at 88 = 11× higher).

**Operator impact** (the WHY the rule matters):
- Per-button capability badges (`<TextBlock Text="{Binding *.Badge}">` controls) ALREADY surface LIVE / PHASE 2 PENDING / LIVE-ONLY status in the UI. The `iter N` prefix in tooltips is REDUNDANT.
- Internal `iter N` codenames are MEANINGLESS to operators. They scan tooltips for "what does this button do?", not "what month did Claude ship this?".
- Cross-references to internal iter-N (`Reuses iter-199 OtherPlayerLuaExpr`) require operators to remember iter-N → button name mapping. Demoted form (`Reuses Is_Enemy/Is_Ally OtherPlayerLuaExpr`) operator-recognizable directly.
- Tooltip length matters for hover UX. Removing 14-22 chars of prefix per tooltip × 88 instances = ~1.5 KB binary text reduction (empirically observed: iter-384 published binary shrank 0.01 MB after PlayerState batch).

**How to apply:**

When adding a new SWFOC_* wire to a tab's GroupBox:

1. **Skip the `iter <N> LIVE — ` prefix from the start.** Use either:
   - `Calls (unit):X(args). <description>` for unit-method wires
   - `Calls (taskforce):X(args). <description>` for TaskForce wires
   - `Calls (player):X(args). <description>` for player-method wires
   - `Calls X(args). <description>` for global-method wires
   - `<bare description>` for non-Lua wires (e.g., GLOBAL multipliers, internal toggles)
2. **Skip cross-references using `iter <N>`.** Reference the operator-visible button name instead:
   - Bad: `iter-155 PlayerGiveMoney`. Good: `PlayerGiveMoney`.
   - Bad: `iter-199 OtherPlayerLuaExpr`. Good: `Is_Enemy/Is_Ally OtherPlayerLuaExpr`.
   - Bad: `iter-212 Bribe`. Good: `Bribe`.
3. **Capitalization convention**: prepend "Calls" with capital C; preserve method name case as engine returns it (e.g., `(unit):Make_Invulnerable(true)`).
4. **Keep ALL operator-relevant context**: receiver type clarification (`Receiver: PLAYER (type Find_Player(...) into UnitLuaExpr)`), warnings (`WARNING: state RESETS on Galactic↔Tactical mode change`), cross-button hints (`Pair with Has attack target? predicate`).

When AUDITING an existing tab for tooltip drift, run:

```
Grep `ToolTip="iter \d+` in MainWindowV2.xaml within tab's line range.
```

Apply per-line `Edit` calls in parallel (one Edit per tooltip; Claude Code batches them).

**Format-variation handling:**

Tooltips ship in 4+ format variants across 5 audited tabs:
- **Variant A** (UnitControl/Combat read-side): `iter <N> LIVE — calls (X):Y(args)`
- **Variant B** (UnitControl write/PlayerState/Inspector/Galactic): `iter <N> LIVE — (X):Y(args)` (drops "calls" word)
- **Variant C** (Combat scalars): `Iter <N> LIVE — X` (capitalized "Iter")
- **Variant D** (Combat compound): `Iter <N>/<M> LIVE — X` (compound iter range)

All transform to: `Calls (X):Y(args). <desc>` or `<bare desc>` form.

**NOT applicable when:**

- **Tooltip is on a status-display TextBlock** (not a Button). Status displays show current state, not action descriptions.
- **Tooltip is intrinsically tied to one iter** (e.g., regression-guard test stub explicitly testing iter-N's pin behavior). Rare in practice — 0 instances surfaced in iter-382-387 audit.
- **Tooltip references a milestone iter or arc-name** (e.g., `Camera primitive arc — extras`). Operator-recognizable; preserve.
- **Tooltip is in code (string literal)** rather than XAML. Code strings have different audit/edit pattern.

**Edge-case sub-rules:**

- **Cross-reference demotion is opportunistic, not required.** If demoting a cross-ref would lose operator-relevant context (e.g., `complement to iter-155 Unlock_Tech` → `complement to PlayerUnlockTech` is fine; `iter-204 on/off pattern, lineage now 7 iters deep` → `on/off pair pattern` loses informative meta-pattern reference). Make per-line judgment.
- **Compound iter refs** (`Iter 96/100 LIVE — X`) are special: drop both iter numbers; the description is what survives.
- **"iter N namespace-agnostic finding for the iter-Y helper"** type meta-references (architectural notes embedded in tooltips): drop the iter-N references but keep the architectural insight (`namespace-agnostic finding for the helper`).
- **"Iter X LIVE (iter-Y wire)" double iter ref** (iter-218 form): drop both; preserve the bare description.

**Cost-benefit ratio:**

Per-fix cost: ~1 LoC text change per tooltip + 0 LoC provenance (unlike iter-380 headers which had provenance comments above the GroupBox declaration; tooltip changes are inline). Cycle time: ~30 sec per tooltip when batched in parallel via multiple `Edit` calls in single message.

Cumulative cost across 88 fixes shipped iter-382-387: ~88 LoC source + ~33 cross-ref demotions = ~120 LoC delta. Cumulative cycle time: ~75 min (across 6 iters; ~12.5 min per iter when batched 9-24 fixes).

Avoidance benefit: operators see operator-relevant tooltip text, no internal codename pollution, no need to mentally translate `iter-N` → button purpose.

**Codification trigger justification:**

Tier 1/2 production-pattern codification at 88/6 instances per iter-302 (6 instances) / iter-334 (6) / iter-345 (8) / iter-380 (7) precedent. **88 instances across 5 distinct V2 tabs ALL exhibited this drift pattern naturally**; the rule was generated organically by 6 iters of UI/UX polish work (iter-382-387), NOT by abstraction-laddering meta-codification.

**This codification is GROUNDED in concrete production-pattern instances**, the same epistemology as iter-380's stale-header rule. The 88-instance evidence base is **the strongest of any codified rule in the project** — 11× the prior record (iter-345 resolver-injection at 8 instances).

**Sibling rule relationship:**

- **iter-380** `feedback_stale_groupbox_header_drift.md` covers GroupBox HEADER drift (`<GroupBox Header="...iter N..."`)
- **iter-388** `feedback_internal_codename_in_tooltips_drift.md` covers Button TOOLTIP drift (`<Button ToolTip="...iter N..."`)
- Both share root cause: **internal iter codenames leaking into user-facing UI text where operators read it**
- Both share fix template: drop the iter-N prefix, keep operator-relevant description
- Both share audit workflow: single grep against MainWindowV2.xaml + parallel Edit batch
- Different elements (Header attribute vs ToolTip attribute) + different scopes (1 header per GroupBox vs many tooltips per GroupBox) make separate codification cleaner than unified rule

**iter-389+ prospective uses:**

- **iter-389-393 cleanup of remaining 4 tabs**: Connection (6 tooltips), Camera & Debug (8 tooltips), Economy (4 tooltips), Spawning (4 tooltips), plus extras in less-trafficked tabs. ~31 more tooltips queued for cleanup; codified rule guides per-tab batches.
- **Future SWFOC_* wire additions**: every new Button.ToolTip should ship with `Calls (X):Y(args)` format from the start, no `iter N` prefix.
- **Audit cadence**: every ~30 iters (next at iter-417 if iter-388 closes the trigger), grep `ToolTip="iter \d+` against MainWindowV2.xaml to surface new instances of drift; fix in batch.
- **Tier 1/2 self-validation**: future audit-and-fix arcs (e.g., similar pattern for code Comments referencing `// iter N`) can reference this rule's concrete fix template.

**Cross-link to related codified rules:**

- **iter-380** `feedback_stale_groupbox_header_drift.md` — sibling rule (Tier 1; 7-instance trigger; same root cause, different element)
- **iter-302** `feedback_engine_already_does_this.md` — Tier 1/2 6-instance precedent
- **iter-334** `feedback_locate_by_convention_extensible.md` — Tier 1/2 6-instance precedent
- **iter-345** `feedback_resolver_injection_at_composition_root.md` — Tier 1/2 8-instance precedent (prior evidence-base record)

**Pattern lessons surfaced during codification:**

1. **Cross-tab fan-out scales pattern recurrence dramatically.** Single-tab pattern with 7 instances (iter-380 headers) → 7-instance trigger. Cross-tab pattern with 88 instances spread across 5 tabs (iter-388 tooltips) → 88-instance trigger (11× higher). Watch for cross-tab patterns; they accumulate evidence faster.
2. **Sibling-rule pattern emerges naturally when same root cause manifests in different elements.** iter-380 (header) + iter-388 (tooltip) are siblings — both internal-codename-leakage; different element scopes. Don't artificially merge into unified rule when scope difference is meaningful (header has 1 per GroupBox, tooltip has many).
3. **Concrete-work codification is faster + stronger than meta-codification.** iter-377-380 sibling header arc = 4 iters / 7 instances / 1 codification. iter-382-387 sibling tooltip arc = 6 iters / 88 instances / 1 codification (this rule). Both grounded in operator-visible work, not cluster meta-iteration.
4. **Format variations within a pattern accumulate as the codebase grows.** 4 distinct tooltip formats surfaced across 5 audited tabs (`iter / Iter / Iter X/Y / "calls" inclusion`). Codified rule should explicitly enumerate variations rather than assume uniformity. Future audits use the variation enumeration as a checklist.