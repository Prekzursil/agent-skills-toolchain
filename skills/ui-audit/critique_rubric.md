---
title: critique_rubric
type: note
permalink: dqverify-repo-20261013/skills/ui-audit/critique-rubric
---

# Track-B Design-Critique Rubric — DESIGN-EVAL v1

The deterministic rubric Claude applies when turning Track-A's numbers + the screenshot
into a structured design verdict. Grounded in **Refactoring UI** (Wathan & Schoger),
**Material Design 3**, **Apple HIG**, and **Nielsen's 10 usability heuristics**, and
formalized to the **DESIGN-EVAL v1** scoring contract (per-dimension ordinal score +
critical-error override + weighted composite + reliability protocol — the convergent
SOTA pattern from UIClip/UICrit/Nielsen severity/WCAG 3.0).

**How to use it.** For each dimension below: read the *pre-computed evidence* Track-A
routed to it (in `evidenceByDimension`), LOOK at the screenshot, then emit
`{ dimension, score (0-4), rating (pass/warn/fail), confidence, findings[] }`. Each
finding is `{ severity, evidence, recommendation }` and cites numbers by their Track-A
`ref`. Where a dimension has no deterministic signal, judge perceptually from the
screenshot and lower the confidence — **do not invent measurements** (that is Track-A's
job).

## The 0-4 score scale (§2.1 — every scoring dimension)

| Score | Band | Meaning |
|-------|------|---------|
| **4** | Excellent | ship as a reference |
| **3** | Good | only low/info nits |
| **2** | Needs-work | real medium/high defects, recoverable |
| **1** | Poor | pervasive defects |
| **0** | **Critical/fail** | a critical-error condition tripped (forced) |

**Ship gate** (WCAG-3.0-style Bronze): mean ≥ 3.0 **AND** no dimension < 2 **AND** zero
critical errors. **Reference gate:** mean ≥ 3.5 and no dimension < 3.

## Critical-error override (§2.3 — load-bearing)

A critical-error condition (listed per dimension below) **forces that dimension's
`score` to 0** and adds a `critical` finding. It also caps the verdict regardless of the
other scores: **1 critical → overall capped at needs-work (≤60); ≥2 critical → poor
(≤39).** The override is enforced by the validator — a critical finding with a non-zero
score is rejected.

## Weighted composite (§2.4 — the headline, computed not free-handed)

```
overall_0_100 = 100 * ( Σ wᵢ·scoreᵢ ) / ( 4·Σ wᵢ )    # then apply the §2.3 cap
```
Weights (color-contrast highest at 2.0 — least subjective, most load-bearing):

| Dimension | Weight |   | Dimension | Weight |
|-----------|--------|---|-----------|--------|
| color-contrast | **2.0** | | type-scale | 1.0 |
| visual-hierarchy | 1.5 | | consistency | 1.0 |
| empty-error-states | 1.5 | | alignment | 0.75 |
| affordance | 1.5 | | motion | 0.75 |
| spacing-rhythm | 1.0 | | | |

**Do not free-hand `verdict.score`** — fill it with `node critique.mjs compute --input
<file>` (or match `computeVerdict()`). **Freeze weights, viewport, theme/state, and the
anchor set across any before/after pair** — changing them mid-comparison invalidates the
delta.

## Reliability protocol (§2.5 — what makes it repeatable)

- **One dimension per reasoning pass** (kill the halo effect) — use
  `critique.mjs assemble --dimension <name>` for a single-dimension brief, then merge.
- **Anchor with the few-shot exemplars** under each dimension (the 0/2/4 lines).
- **N≥2 passes on perceptual dimensions** (alignment, visual-hierarchy, motion-feel);
  keep the lower score when they disagree; expect honestly-low agreement on pure
  aesthetics (UIClip α=0.37, UICrit κ≈0.30 are the baselines).
- **Lean on the deterministic Track-A numbers as the spine** — they are the evidence a
  skeptic can't argue with; perceptual scores ride on top with confidence labels.

## Severity ladder (how to grade a finding — Nielsen 0-4)

| severity | meaning |
|----------|---------|
| critical | blocks use or fails a hard standard: WCAG contrast fail, render crash (pageError), dead primary action, blank screen, motion with no reduced-motion escape |
| high | clearly wrong and noticeable: unwired secondary control, no visual hierarchy, colliding/overflowing elements |
| medium | off but tolerable: off-grid spacing, inconsistent gutters, slightly too many type styles, out-of-band animation |
| low | minor polish: sub-pixel spacing, a single near-duplicate grey |
| info | observation / nice-to-have, no action strictly required |

## Verdict mapping (computed, for reference)

- **good** (~75-100): composite healthy, no dimension < 2, zero criticals.
- **needs-work** (~40-74): real defects but a recoverable base.
- **poor** (~0-39): a capped catastrophe (≥2 criticals, or a 1-critical board that
  already scored low).

---

## 1. visual-hierarchy · weight 1.5
*Does the eye land on the right thing first?* (Refactoring UI: "hierarchy is everything"; HIG: clarity/deference.)
- **Good:** one clear primary action; size, weight and colour — not size alone — separate primary / secondary / tertiary; supporting text de-emphasised; a clear focal point.
- **Track-A signals:** axe `landmark`/`heading-order`/`region` (missing document structure flattens hierarchy).
- **Critical-error trigger (→0):** no focal point AND the primary CTA is visually indistinguishable from secondary controls.
- **Anchors:** **0** no focal point, primary CTA lost in a wall of equal-weight controls · **2** a focal point exists but secondary actions compete · **4** unmistakable primary action, calm de-emphasised supporting content.

## 2. spacing-rhythm · weight 1.0
*Consistent spacing scale and breathing room.* (Refactoring UI: start with too much whitespace, use a spacing scale; Material 8dp / 4dp grid.)
- **Good:** margins/padding/gaps on a 4-8px scale; related items grouped by proximity; generous, even whitespace; no cramped or colliding blocks.
- **Track-A signals:** `off-scale-spacing` **high-confidence** (authored off-grid integers like 13px / 30px) = real warnings; **low-confidence** sub-pixel = noise (`info` at most).
- **Critical-error trigger (→0):** colliding/overlapping content blocks.
- **Anchors:** **0** content blocks overlap/collide · **2** several high-confidence off-grid values, uneven rhythm · **4** everything on one scale, deliberate whitespace.

## 3. alignment · weight 0.75
*Shared edges and baselines; tidy gutters.* (Refactoring UI: align to a grid; Material columns/gutters.) **Screenshot-judged — no deterministic Track-A signal.**
- **Good:** elements share left/right edges and baselines; consistent gutters; labels and values line up.
- **How to judge:** look at the screenshot — do card titles, body copy and controls share edges? Ragged left edges? Judge perceptually; confidence `medium`/`low`; run twice.
- **Critical-error trigger:** — (rarely critical).
- **Anchors:** **0** content visibly random, nothing shares an edge · **2** mostly aligned, one or two items drift off the grid · **4** crisp shared edges and even gutters throughout.

## 4. type-scale · weight 1.0
*A limited, deliberate type ramp.* (Refactoring UI: define a modular scale, limit weights; Material type scale; HIG Dynamic Type.)
- **Good:** ≤ ~6 distinct (size/weight/line-height) styles; obvious heading vs body vs caption; line-height ~1.4-1.6 for body.
- **Track-A signals:** `type-scale-sprawl` (> 6 distinct triples) → undisciplined ramp.
- **Critical-error trigger (→0):** body text illegibly small or over-set.
- **Anchors:** **0** body text illegibly small / no heading-body distinction · **2** ramp sprawls (9+ triples) but is readable · **4** tight modular ramp, clear heading/body/caption.

## 5. color-contrast · weight 2.0 (highest)
*Palette harmony and legibility.* (Refactoring UI: one primary + accent, greys with a hint of saturation; WCAG AA; Material tonal palette.)
- **Good:** text meets WCAG AA (≥ 4.5:1 body, ≥ 3:1 large); a small, consistent palette; greys consolidated to tokens; accent used sparingly.
- **Track-A signals:** `wcag-contrast` (sub-4.5:1 text); axe `color-contrast`; `color-inventory-sprawl` (near-duplicate greys).
- **Critical-error trigger (→0):** **any body text < 4.5:1.**
- **Anchors:** **0** body text fails AA (any sub-4.5:1) · **2** large text passes but the grey palette is fragmented · **4** all text clears AA, small consistent token palette.

## 6. consistency · weight 1.0
*The same components, spacing and type across screens.* (Nielsen #4 consistency & standards; Material components; HIG consistency.)
- **Good:** repeated patterns look identical across screens; shared spacing/type/colour tokens; no per-screen drift.
- **Track-A signals:** `visual-regression` (>5% baseline drift), plus per-screen rule-count and type-triple-set diffs.
- **Critical-error trigger (→0):** the same component renders differently across core screens.
- **Anchors:** **0** a shared component looks different per screen · **2** minor drift in spacing/type between screens · **4** pixel-stable repeated patterns.

## 7. empty-error-states · weight 1.5
*Quality of empty / loading / error / blank-render states.* (Nielsen #9 recover from errors, #1 visibility of system status; Material empty states.)
- **Good:** empty states explain what's missing and offer a next action; errors are human and recoverable; no raw blank screens.
- **Track-A signals:** `pageError` (uncaught exception → render crash); **a near-blank screenshot with content expected is itself an empty/error-state failure.**
- **Critical-error trigger (→0):** render crash / blank where content is expected.
- **Anchors:** **0** screen rendered blank or a page error fired · **2** functional but bare empty/error states (no guidance) · **4** informative, recoverable, on-brand empty/error states.

## 8. affordance · weight 1.5 *(DESIGN-EVAL v1 — new)*
*Do controls signal that they act, and give feedback?* (Norman signifiers; HIG ≥44px / Material 48dp targets; WCAG focus-visible.)
- **Good:** interactive elements look interactive (cursor, hover, affordant styling); tap targets ≥ 44px/48dp; keyboard focus has a visible signifier; every primary action gives feedback.
- **Track-A signals:** `tap-target` (sub-44px); `dead-control` (effect:none → unwired button); `click-error` (non-actionable); `missing-focus-visible` (controls suppress the outline and no `:focus-visible` rule); axe `focus`/`target-size`.
- **Critical-error trigger (→0):** a primary action gives no signifier OR no feedback (dead primary control).
- **Anchors:** **0** the primary action is dead (no feedback on click) · **2** secondary controls are sub-target or lack focus signifiers · **4** every control is affordant, ≥44px, with a visible focus ring and feedback.

## 9. motion · weight 0.75 *(DESIGN-EVAL v1 — new)*
*Is motion purposeful, smooth, and respectful?* (M3 motion / "expressive ≠ decorative"; 200–500ms band; `prefers-reduced-motion`.)
- **Good:** transitions in the ~200–500ms band; smooth (no visible jank/dropped frames); motion clarifies cause/effect; honors `prefers-reduced-motion`.
- **Track-A signals:** `motion-duration` (transition/animation outside the 200–500ms band); `reduced-motion` (page animates but ships no `prefers-reduced-motion` rule).
- **Critical-error trigger (→0):** janky/blocking animation, OR motion with no reduced-motion escape hatch.
- **Anchors:** **0** blocking/janky motion or no reduced-motion escape · **2** durations out of band or motion that doesn't aid comprehension · **4** snappy in-band motion that clarifies state and respects reduced-motion.

## overall (the holistic line — not weighted, not scored 0-4)
*Holistic "does it look good?"* Summarize the nine dimensions with the screenshot. Lead with the single most important fix.
- **Track-A signals:** `summary-totals` (the roll-up) + the optional **UIClip** numeric prior (weak prior, never ground truth — it can't see wiring/contrast/affordance/motion).
- Produce: `verdict.looksGood`, `verdict.score` (the §2.4 composite, **computed**), a one-line `headline`, a short `summary`, and a `prioritizedFindings` list (highest severity first) a developer can act on in order.

## Grading a before/after (§2.6 — the point)

Per-dimension delta Δᵢ on 0-4 · composite improvement `after/before − 1` (e.g. 47→81 ⇒
+72%) · **critical-error burndown** (the most defensible single claim — binary,
non-subjective) · report contrast pass-rate / %-on-scale spacing / tap-target compliance
/ type-triple count / regression % / motion-duration compliance **before vs after**.
**The delta IS the evidence the change improved, not moved laterally** — a redesign that
moves no rubric dimension is suspect.