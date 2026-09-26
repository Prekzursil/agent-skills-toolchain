---
name: Stale-GroupBox-Header-Drift Pattern
description: GroupBox headers that include a specific iter range or "iter N" reference
  become stale when the section continues to receive new sub-batches without header
  updates. Header text drifts behind actual section content, misleading operators
  about scope. Validated at 7 instances across 6 distinct V2 tabs (UnitControl/Combat/PlayerState/WorldState/Inspector/Spawning
  ×2) iter-377/378/379. Tier 1/2 production-pattern codification.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-stale-groupbox-header-drift
---

**Rule:** When a GroupBox header in WPF XAML includes a specific iter range or "iter N LIVE" reference, the header text MUST be updated whenever a new sub-batch is added to the section. If updates are skipped, the header drifts and becomes a misleading historic artifact — it tells operators the section was last touched in iter-N, but it actually contains wires from iter-N + iter-M + iter-K + ...

**Default header conventions to AVOID:**

```xaml
<!-- BAD: tied to a specific iter range that will drift as section grows -->
<GroupBox Header="Selected Unit Lua Actions (iter 117-118 LIVE)">
<GroupBox Header="Per-unit combat actions (iter 193 — iter 154 LIVE wires)">
<GroupBox Header="Selected Player Read-side (iter 169 + iter 199)">
<GroupBox Header="Story & Audio (engine Lua, LIVE — iter 159)">
<GroupBox Header="Selected Unit Lua Read-side (iter 191)">
<GroupBox Header="Spawn unit via Lua (iter 119 LIVE)">
<GroupBox Header="Discovery helpers (engine Lua, LIVE — iter 177 + 186)">
```

**Default header conventions to PREFER:**

```xaml
<!-- GOOD: scope-described in operator-relevant terms -->
<GroupBox Header="Selected Unit Lua Actions (~24 LIVE wires; see per-button badges)">
<GroupBox Header="Per-unit combat actions (5 LIVE wires)">
<GroupBox Header="Selected Player Actions (~13 LIVE wires; mixed read/write)">
<GroupBox Header="Cinematic & Audio Controls (12 LIVE wires)">
<GroupBox Header="Selected Unit Lua Read-side (~18 read-side wires)">
<GroupBox Header="Spawn unit via Lua (4 LIVE wires)">
<GroupBox Header="Discovery helpers (5 LIVE wires)">
```

**Why:**

7 instances across iter-377 → iter-379 (~3-iter window) prove the pattern is widespread:

| Iter | Tab | Header before | Header after | Sub-batches accumulated |
|---|---|---|---|---|
| iter-377 | UnitControl | `Selected Unit Lua Actions (iter 117-118 LIVE)` | `Selected Unit Lua Actions (~24 LIVE wires; see per-button badges)` | 8 (iter 110/112/118/167/171/172/194/211/212/213/218) |
| iter-378 | Combat | `Per-unit combat actions (iter 193 — iter 154 LIVE wires)` | `Per-unit combat actions (5 LIVE wires)` | 2 (iter 154 + iter 162) |
| iter-378 | Player State | `Selected Player Read-side (iter 169 + iter 199)` | `Selected Player Actions (~13 LIVE wires; mixed read/write)` | 5 (iter 169/199/209/210/217) |
| iter-379 | World State | `Story & Audio (engine Lua, LIVE — iter 159)` | `Cinematic & Audio Controls (12 LIVE wires)` | 4 (iter 201/202/204/208) |
| iter-379 | Inspector | `Selected Unit Lua Read-side (iter 191)` | `Selected Unit Lua Read-side (~18 read-side wires)` | 4 (iter 191/197/198/214) |
| iter-379 | Spawning | `Spawn unit via Lua (iter 119 LIVE)` | `Spawn unit via Lua (4 LIVE wires)` | 2 (iter 119 + iter 195) |
| iter-379 | Spawning Discovery | `Discovery helpers (engine Lua, LIVE — iter 177 + 186)` | `Discovery helpers (5 LIVE wires)` | 2 (iter 203 + iter 206) |

**7 instances exceeds 6-instance Tier 1/2 codification threshold** per iter-302/334/345 production-pattern precedent.

**Operator impact** (the WHY the rule matters):
- Internal `iter N` codenames are MEANINGLESS to operators. They scan headers for "what does this section do?", not "what month did Claude ship this?".
- Stale headers UNDERCOUNT scope: a section with 24 LIVE wires labeled "iter 117-118 LIVE" makes operators think there are only 2 wires. They miss the other 22.
- Stale labels can become INCORRECT: PlayerState header said "Read-side" but section had grown to include write-side wires (Lock_Tech, Make_Ally, Disable_Orbital_Bombardment, GLOBAL diplomacy). Operators reading "Read-side" expected query-only buttons; reality was 8 mutate-engine buttons mixed in.
- Scrolling cost: when section names lie about scope, operators scroll past relevant features to find what they need elsewhere.

**How to apply:**

When adding a new sub-batch to an existing GroupBox in MainWindowV2.xaml:

1. **Read the current GroupBox header.** Note any `iter N` reference.
2. **Decide between two header strategies:**
   - **Count-only header** (preferred default): `(N LIVE wires)` or `(~N LIVE wires; see per-button badges)`. Simple, scope-honest, never goes stale unless wire count changes.
   - **Scope-described header** (when scope shifted, not just grew): `Cinematic & Audio Controls (12 LIVE wires)` — captures operator workflow intent + wire count.
3. **Replace the iter-N reference** in the header text. Move historic context into a `<!-- 2026-MM-DD (iter N): ... -->` provenance comment ABOVE the GroupBox declaration.
4. **Cross-check with the section's actual content.** Walk the WrapPanel/StackPanel and count buttons; verify the count matches the header.

When ADDING a new GroupBox to MainWindowV2.xaml, choose a header that doesn't tie to the current iter — use scope-description + (count) format from the start.

**NOT applicable when:**

- **Header is a tab name** (e.g., `<TabItem Header="Combat" />`): tab names don't have iter ranges; this rule is for GroupBox headers within tabs.
- **Section was added in a single iter and will never grow** (truly atomic feature, low expected scope-creep): can keep `(iter N LIVE)` shorthand. Rare in practice — `Camera & Debug` tab's "Scroll camera to target (iter 107 LIVE)" header is one of the few legitimately-stable instances.
- **Header references a milestone iter** (e.g., `Iter 100-300 LIVE wires`): these are explicitly intended to drift; the operator reads them as "wires shipped through iter N", and the section is refreshed periodically. Lua Playground preset menu is the canonical example.
- **Section is INTRINSICALLY tied to one iter** (e.g., a regression-test guard + provenance pair): keep the iter-N reference because removing it would lose the audit trail.

**Edge-case sub-rules:**

- **Section name no longer fits scope**: when the section has grown WIDE enough that even the LABEL is wrong (e.g., "Read-side" but section now has write-side wires too), RENAME the section AND update the count. Don't just update the count — operators still get misled by the wrong label.
- **Mixed read/write sections**: append `(~N LIVE wires; mixed read/write)` to disambiguate. Predicate: if section has BOTH `Read_*`/`Get_*` AND `Set_*`/`Make_*` wires, it's mixed.
- **Section spans many iters with consistent purpose**: `(~N LIVE wires; see per-button badges)` works well — defers detail to per-button tooltips/badges.
- **Section count is uncertain or will continue growing**: use `~N` (approximate) instead of exact `N` to avoid future drift. Anchors the order-of-magnitude without false precision.
- **Section has multiple sub-types** (operator must read row labels to find right button): consider splitting into sub-GroupBoxes. Don't try to summarize complex multi-purpose sections in a one-line header.

**Cost-benefit ratio:**

Per-fix cost: ~1 LoC text change + ~6 LoC provenance comment = ~7 LoC. Cycle time: ~1 min (read content + decide header + edit + verify in next publish).

Cumulative cost across the 7 fixes shipped iter-377/378/379: 7 × 7 LoC = ~49 LoC source impact. Cumulative cycle time: ~30 min (across 3 iters; ~10 min per iter when batched).

Avoidance benefit: operators don't scroll past relevant features OR misunderstand section scope OR miss new wires that were added but not surfaced in the header.

**Codification trigger justification:**

Tier 1/2 production-pattern codification at 7/6 instances per iter-302 (6 instances) / iter-334 (6 instances) / iter-345 (8 instances) precedent. 7 distinct V2 tabs / GroupBoxes ALL exhibited this drift pattern naturally; the rule was generated organically by 3 iters of UI/UX polish work (iter-377/378/379), NOT by abstraction-laddering meta-codification.

**This codification is GROUNDED in concrete production-pattern instances**, fundamentally different from the iter-359/363/368/371/373/374 Tier 4 cluster (meta-rules about audit cadence/codification process). The 7-instance evidence base is empirical, not derived.

**iter-381+ prospective uses:**

- **iter-380+ MainWindowV2.xaml additions**: every new GroupBox should ship with a count-format header from the start (no iter-N references).
- **iter-381+ Lua Playground preset menu refresh**: the `Iter 100-300 LIVE wires` header at line 4248 needs periodic refresh per this rule's "milestone iter" carve-out — but the count format should still apply.
- **Future RE arc closeouts** (e.g., when iter-380+ ships a NEW dispatcher helper + 4-wire batch): the GroupBox surfacing the new wires should use `(N LIVE wires)` format, never `(iter <kickoff> LIVE)`.
- **Audit cadence**: every ~30 iters (next at iter-410), grep `Header=".*iter \d+` against MainWindowV2.xaml to surface new instances of drift; fix in batch (iter-378/iter-379 pattern).
- **Tier 1/2 self-validation**: future audit-and-fix arcs (e.g., similar pattern for ToolTip drift, Comment drift) can reference this rule's concrete fix template.

**Cross-link to related codified rules:**

- iter-302 `feedback_engine_already_does_this.md` — Tier 1/2 6-instance precedent
- iter-334 `feedback_locate_by_convention_extensible.md` — Tier 1/2 6-instance precedent
- iter-345 `feedback_resolver_injection_at_composition_root.md` — Tier 1/2 8-instance precedent (HIGHEST evidence base)
- iter-368 `feedback_audits_clean_when_no_new_wires.md` — Tier 4 audit-prediction pattern (DIFFERENT epistemology — meta-rule, not production-rule)

**Pattern lessons surfaced during codification:**

1. **Concrete production work drives the strongest codification triggers.** Iter-377 NEW pattern observation became 7-instance trigger over 3 iters of UX polish — much faster + more grounded than waiting for natural recurrence on a meta-codification cluster.
2. **Single grep audit produces complete inventory in seconds.** `Header=".*iter \d+` against MainWindowV2.xaml returned 12 candidates in <1 sec; categorized as 7 STALE / 5 ACCURATE / 1 needs-refresh in ~5 min eyeballing. This audit-first pattern beats "fix as you find" eyeball scanning.
3. **Verification heuristic is empirically reliable**: 4/4 LIKELY STALE candidates from iter-378 catalog confirmed STALE on section-content verification (100% hit rate). Classification rule: "section content has been extended in iters AFTER the header was written" → almost certainly STALE.
4. **Sometimes a stale-header fix is also a section-rename moment.** WorldState `"Story & Audio (iter 159)"` → `"Cinematic & Audio Controls"` captured shifted operator workflow (now used for filming setups, not just audio). Don't just bump iter range — re-evaluate the section name.