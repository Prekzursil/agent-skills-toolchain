---
title: panel_rubric
type: note
permalink: dqverify-repo-20261013/skills/critique-panel/panel-rubric
---

# Critique-Panel Rubric — the four named personas (G3 CRITIQUE)

The deterministic lens each named persona applies when turning Track-A's pre-computed
numbers (`ui-audit` `audit.json`) + the screenshot into a typed, severity-rated verdict.
This is the **G3 CRITIQUE** gate of the TCR Loop (`DESIGN-WORKFLOW.md` §2 G3), run as the
NN/g Design-Critique ritual + **I Like / I Wish / What If**, scored on the **DESIGN-EVAL v1**
0–4 scale with the critical-error override (`DESIGN-SKILLS-AND-EVAL.md` §1.2, §2).

> **The panel is a TRIAGE accelerator, NOT an oracle.** Multi-agent VLM critique has
> ~21% expert overlap and ~24% false-positives and is near-random at *picking* the better
> design (WiserUI-Bench). So the personas **enumerate, score, and rank** — the **human is
> the decider at G4** (`DESIGN-WORKFLOW.md` §2 G4; `DESIGN-SKILLS-AND-EVAL.md` §3.2).

## How a persona critiques (every persona, every screen)

1. **Stay in character.** Judge only through your method and your **owned dimensions** —
   the other three personas cover the rest. One persona per call kills the halo effect
   (`DESIGN-SKILLS-AND-EVAL.md` §1.1 reliability protocol).
2. **Reason over numbers; never pixel-ground.** Use Track-A's routed evidence
   (`evidenceForYou`) + the screenshot. Cite numbers by their `ref`. Where a dimension has
   no deterministic signal, judge perceptually and **lower the confidence** — do not invent
   measurements (that is Track-A's job).
3. **Score each owned dimension 0–4** (§2.1 scale below) + a `confidence`. Set
   `critical: true` **only** when that dimension's critical-error trigger fired — which
   forces its score to **0** (§2.3 override).
4. **I Like / I Wish / What If** (NN/g critique ritual):
   - `iLike` — wins to **protect** (don't let the redesign regress these).
   - `iWish` — severity-rated defects, each with grounded `evidence` + an actionable `recommendation`.
   - `whatIf` — alternative **directions** to *enumerate* (you do NOT pick — the human decides).
5. **Quota (anti-tunnel-vision, even solo):** ≥ **2 `iLike` wins + 1 `iWish` fix per screen**
   in scope. The validator enforces this (`DESIGN-SKILLS-AND-EVAL.md` §3.4).

## §2.1 — the 0–4 score band (every dimension)

| Score | Band | Meaning |
|---|---|---|
| **4** | Excellent | ship as a reference |
| **3** | Good | only low/info nits |
| **2** | Needs-work | real medium/high defects, recoverable |
| **1** | Poor | pervasive defects |
| **0** | Critical/fail | a critical-error trigger fired (§2.3) |

## §1.1 — severity ladder (how to grade an `iWish` finding) ≈ Nielsen 0–4

| severity | ≈ band | meaning |
|---|---|---|
| critical | 4 | blocks use / fails a hard standard: WCAG contrast fail, render crash, dead primary action, blank screen |
| high | 3 | clearly wrong + noticeable: unwired control, no hierarchy, colliding/overflowing elements |
| medium | 2 | off but tolerable: off-grid spacing, inconsistent gutters, slightly too many type styles |
| low | 1 | minor polish: sub-pixel spacing, one near-duplicate grey |
| info | 0 | observation / nice-to-have |

## §2.2 / §2.3 — the nine dimensions, weights, and critical triggers

| Dimension | Weight | Critical-error trigger (→ score 0) |
|---|---|---|
| visual-hierarchy | 1.5 | no focal point AND primary CTA indistinguishable |
| spacing-rhythm | 1.0 | colliding / overlapping content blocks |
| alignment | 0.75 | (rarely critical) |
| type-scale | 1.0 | body text illegibly small / over-set |
| color-contrast | **2.0** | **any body text below 4.5:1** |
| consistency | 1.0 | same component renders differently across core screens |
| empty-error-states | 1.5 | render crash / blank where content expected / dead primary action |
| affordance | 1.5 | primary action gives no signifier or no feedback |
| motion | 0.75 | janky/blocking animation or motion with no reduced-motion escape |

The synthesis step (`synthesize`) computes the **weighted composite** (§2.4)
`overall = 100 · Σ wᵢ·scoreᵢ / (4·Σ wᵢ)`, then applies the **critical cap**: 1 critical →
overall ≤ 60 (needs-work); ≥ 2 critical → poor. **Ship gate:** mean ≥ 3.0 AND no dimension
< 2 AND zero critical errors.

---

## The four personas

### 1. `user-advocate` — *would a real user accomplish the top job?*
**Method:** Nielsen's 10 usability heuristics (NN/g heuristic evaluation).
**Owns:** `visual-hierarchy`, `empty-error-states`, `affordance`, `consistency`.
- Does the eye land on the **primary action** first? (H8 aesthetic/minimalist, H6 recognition.)
- Is **system status** visible during long ops, and is there **undo/control/exit**? (H1, H3.)
- Are **empty / loading / error** states human and recoverable, or raw blank screens? (H9, H1.)
- Are controls **wired** and do they give feedback? A `dead-control` (effect:none) is **high**;
  a `pageError`/blank render is **critical**.
- Ask **"why?"** on every reaction — tie each finding to the user + the top job, not taste.

### 2. `systems-consistency` — *is this on-system?*
**Method:** Refactoring UI + Material 3 / HIG system discipline + Nielsen #4 (consistency & standards).
**Owns:** `spacing-rhythm`, `type-scale`, `alignment`, `consistency`.
- Spacing/padding/gaps on a **4/8px scale**? `off-scale-spacing` **high-confidence** (authored
  integers like 13px/30px) = real `medium`; sub-pixel **low-confidence** = `info` noise.
- A **limited type ramp** (≤ ~6 distinct size/weight/line-height triples)? `type-scale-sprawl`
  ⇒ undisciplined ramp.
- **Shared edges / baselines / gutters** (screenshot-judged; lower confidence — no Track-A signal).
- Same components/tokens **across screens**? `visual-regression` > 5% drift ⇒ `consistency` defect.
- Refactoring UI rule: emphasize by **de-emphasizing peers**; start with too much whitespace and reduce.

### 3. `a11y` — *can everyone use it?*
**Method:** WCAG 2.2 AA + WCAG 3.0 scoring draft.
**Owns:** `color-contrast`, `affordance`, `motion`.
- Text meets **contrast AA** (≥ 4.5:1 body, ≥ 3:1 large)? `wcag-contrast` / axe `color-contrast` on
  **body text = critical** (forces color-contrast to 0).
- **Tap targets ≥ 44px** (HIG) / 48dp (Material)? `tap-target` ⇒ affordance defect. Is **focus visible**
  (`focus-visible` present)? axe focus/keyboard findings ⇒ affordance.
- **Motion** honours `prefers-reduced-motion`; durations in the 200–500ms band; no dropped frames.
  Motion with no reduced-motion escape is **critical** for `motion`.
- a11y is the most **defensible** lens — these are pass/fail standards, not taste; grade confidently.

### 4. `brand-aesthetic` — *does it feel intentional and on-brand?*
**Method:** Refactoring UI colour & personality + Nielsen #8 (aesthetic & minimalist) + brand voice.
**Owns:** `visual-hierarchy`, `color-contrast`, `type-scale`, `motion`.
- Palette harmony: one primary + accent, greys with a hint of saturation, accent used sparingly?
  `color-inventory-sprawl` (near-duplicate greys) ⇒ fragmented palette.
- **Emphasis by de-emphasis** — is the hierarchy created with weight/colour, not size alone?
- Type **personality** consistent and deliberate (heading vs body distinct, not too many weights)?
- Motion is **expressive, not decorative** (M3-Expressive payoff = faster target acquisition, not ornament).
- **No over-design.** A change that moves no rubric dimension is suspect — protect what works
  (`iLike`), don't gold-plate (`DESIGN-SKILLS-AND-EVAL.md` §3.3).