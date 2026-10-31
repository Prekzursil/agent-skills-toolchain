---
name: design-system
description: Use this skill to generate or audit design systems, check visual consistency, and review PRs that touch styling. Emits/consumes the single `.design/` artifact contract and scores on the canonical DESIGN-EVAL v1 rubric (9 dims, 0-4) — the legacy 10-dim 0-10 visual-audit scale is RETIRED.
origin: ECC
---

# Design System — Generate & Audit Visual Systems

> **Canon note (2026-07-12 consolidation).** This skill now rides ONE rubric, ONE canon,
> and ONE artifact contract:
> - **One rubric:** the design-quality verdict is **DESIGN-EVAL v1** (9 dimensions, 0-4,
>   critical-error override, weighted composite), whose single source of truth is
>   `~/.claude/skills/ui-audit/critique_rubric.md` + `critique.schema.json`. The former
>   Mode-2 bespoke **10-dimension / 0-10** scale is **RETIRED** (crosswalk below).
> - **One canon:** design decisions live in **`<repo>/.design/DESIGN.md`** (per-page
>   override sections) + a **W3C-DTCG** `<repo>/.design/design-tokens.json`. There is no
>   longer a competing `design-system/MASTER.md` canon.
> - **One artifact contract:** every stage reads/writes a leaf under **`<repo>/.design/`**
>   (see [The `.design/` artifact contract](#the-design-artifact-contract)). Downstream
>   gates parse those leaf artifacts — never an honor-system "audit passed" flag.
>
> This skill is being consolidated under the **`design-studio`** meta-skill (the mode
> router). Until that rename lands, invoke it as `design-system` and treat `ui-audit` as
> the audit/drive engine it delegates to. Nothing here BLOCKS: the artifact-contract
> gates run in shadow/advisory mode when first wired (council C5).

## When to Use

- Starting a new project that needs a design system
- Auditing an existing codebase for visual consistency
- Before a redesign — understand what you have
- When the UI looks "off" but you can't pinpoint why
- Reviewing PRs that touch styling

## How It Works

### Mode 1: Generate Design System

Analyzes your codebase and generates a cohesive design system into the single canon:

```
1. Scan CSS/Tailwind/styled-components for existing patterns
2. Extract: colors, typography, spacing, border-radius, shadows, breakpoints
3. Research 3 competitor sites for inspiration (via browser MCP)
4. Propose a design token set as W3C-DTCG tokens ($value/$type)
5. Generate .design/DESIGN.md with rationale for each decision
6. (Optional) Create an interactive HTML preview page (self-contained, no deps)
```

**Output (canon):**
- `<repo>/.design/DESIGN.md` — the human canon, with per-page override sections.
- `<repo>/.design/design-tokens.json` — **W3C-DTCG** source-of-truth tokens
  (see [`design-tokens-pipeline`](#token-spine) for the Style-Dictionary/Figma emit).
- `<repo>/.design/design-preview.html` — optional, self-contained preview (NOT canon).

> The tokens are authored in the **W3C Design Tokens Community Group** format
> (`$value` / `$type` / `$description`, group nesting, `{alias.reference}` refs). This is
> the lossless half of the code↔Figma round-trip and the input to the token pipeline.

### Mode 2: Visual Audit — DESIGN-EVAL v1 (canonical)

The visual audit no longer defines its own scale. It **delegates to the canonical
DESIGN-EVAL v1 rubric** driven by `ui-audit`:

```
1. Capture the running app  → ui-audit Track-A  → .design/audit.json   (deterministic numbers)
2. Reason over numbers + screenshot on DESIGN-EVAL v1 (9 dims, one dim per pass)
3. Compute the weighted composite → .design/critique-output.json (Track-B verdict)
```

DESIGN-EVAL v1 scores **nine dimensions, each 0-4** (not 0-10), with a **critical-error
override** (forces that dimension to 0 and caps the verdict) and a **weighted composite**
(color-contrast weighted highest at 2.0). The nine dimensions:

| # | Dimension | Weight |
|---|-----------|--------|
| 1 | `visual-hierarchy` | 1.5 |
| 2 | `spacing-rhythm` | 1.0 |
| 3 | `alignment` | 0.75 |
| 4 | `type-scale` | 1.0 |
| 5 | `color-contrast` | **2.0** |
| 6 | `consistency` | 1.0 |
| 7 | `empty-error-states` | 1.5 |
| 8 | `affordance` | 1.5 |
| 9 | `motion` | 0.75 |

**Ship gate** (WCAG-3.0-style Bronze): mean ≥ 3.0 AND no dimension < 2 AND zero critical
errors. The rubric text, per-dimension anchors, critical triggers, and the composite
formula are canonical in `ui-audit/critique_rubric.md` — **do not re-state or fork them
here.**

#### Retired 10-dim → DESIGN-EVAL v1 crosswalk

The legacy Mode-2 10-dimension / 0-10 scale is **retired**. Every legacy dimension maps
onto a DESIGN-EVAL v1 dimension (or an advisory sub-signal) so no coverage is lost:

| Legacy Mode-2 dim (0-10) | → DESIGN-EVAL v1 (0-4) | Note |
|--------------------------|------------------------|------|
| 1. Color consistency | `color-contrast` | palette/token consolidation + WCAG |
| 2. Typography hierarchy | `type-scale` + `visual-hierarchy` | ramp discipline vs. focal order |
| 3. Spacing rhythm | `spacing-rhythm` | 1:1 |
| 4. Component consistency | `consistency` | 1:1 |
| 5. Responsive behavior | `consistency` (advisory sub-signal) | breakpoint/reflow capture, advisory |
| 6. Dark mode | `consistency` (advisory sub-signal) | dual-theme capture, advisory |
| 7. Animation | `motion` | 200-500ms band + reduced-motion |
| 8. Accessibility | `color-contrast` (WCAG) + `affordance` (focus/target) | split by concern |
| 9. Information density | `visual-hierarchy` (anchor) | density reads as hierarchy pressure |
| 10. Polish | `affordance` + `empty-error-states` + `motion` | hover/feedback, empty/loading, transitions |
| — (new in v1) | `alignment` | shared edges/baselines — screenshot-judged |

Each finding still gets a severity (Nielsen 0-4: critical/high/medium/low/info), the
concrete evidence (cited by its Track-A `ref`), and a fix with exact `file:line`.

### Mode 3: AI Slop Detection (advisory critique pack)

Slop detection is now an **advisory heuristics pack** that feeds the DESIGN-EVAL v1
critique as anchors — it is **not** a separate score. Surface these as `info`/`low`
findings on the mapped dimension (shown in brackets):

```
- Gratuitous gradients on everything                              [visual-hierarchy]
- Purple-to-blue defaults                                         [color-contrast]
- "Glass morphism" cards with no purpose                          [consistency]
- Rounded corners on things that shouldn't be rounded            [consistency]
- Excessive animations on scroll                                  [motion]
- Generic hero with centered text over stock gradient            [visual-hierarchy]
- Sans-serif font stack with no personality                      [type-scale]
```

Fold these into `critique.mjs assemble` as slop-pack anchors; they raise scrutiny, never
force a score on their own (only the rubric's critical-error triggers do that).

## The `.design/` artifact contract

Every stage of the design pipeline reads and writes a **leaf artifact** under the repo's
`.design/` directory. This mirrors metaswarm's proven `.beads/` recovery pattern: a fresh
Claude or Codex thread can pick up `.design/` cold and know exactly where each stage's
input/output lives. **Downstream gates parse these leaves — never an honor-system flag.**

| Leaf | Written by | Read by | Purpose |
|------|-----------|---------|---------|
| `DESIGN.md` | Mode 1 (generate) / DIRECT | every stage | the human canon (per-page override sections) |
| `design-tokens.json` | Mode 1 / token pipeline | tokens, mirror | **W3C-DTCG** source-of-truth tokens |
| `audit.json` | `ui-audit` Track-A | critique, gates | deterministic numbers (contrast, spacing, tap-targets, a11y, regression) |
| `critique-output.json` | `ui-audit` Track-B | gates, revert-gate | the DESIGN-EVAL v1 verdict (9 dims + composite) |
| `transpose-record.json` | transpose (code→canvas) | mirror, gates | what was mirrored to Figma + drift class |
| `tokens.json` | token pipeline (emit) | transpose, mirror | resolved/emitted DTCG tokens (Style-Dictionary output) |
| `mirror-manifest.json` | mirror (`use_figma`) | reverse-drift guard | `screen → figmaFileKey+nodeId, commit, content-hash` (skip when unchanged) |
| `loop-state.json` | `loop.mjs advance` | recovery, gates | stage → artifact-path map; the state machine's memory |
| `baselines/` | `ui-audit visual_diff` | regression | per-screen baseline PNGs |

**Evidence-bound gates (the point).** When the pipeline advances a stage, the gate
**parses the leaf** (e.g. reads `critique-output.json.verdict.score` + the critical-error
count, or `audit.json` totals) rather than trusting a caller-supplied "it passed" boolean.
`loop-state.json` records each stage's artifact path so the next stage auto-discovers its
input and a reviewer can reconstruct the whole run from disk. This applies the skill's own
"never self-certify" rule to the skill itself.

Reference templates for every leaf ship alongside this skill under
`references/.design-templates/` (copy them to seed a repo's `.design/`).

## <a name="token-spine"></a>Token spine (DTCG)

The W3C-DTCG `design-tokens.json` is the lossless canon. The
[`design-tokens-pipeline`](#) skill emits platform artifacts (CSS custom properties,
Tailwind, Style-Dictionary output → `tokens.json`) and Figma Variables (via a `use_figma`
Plugin-API script — quota-exempt writes on the Education Full seat). **Code → Figma is
render-mediated and lossy:** tokens + Code-Connected components round-trip; React
state/routing/logic never survive. The mirror marks *staleness*, never pretends a live
two-way sync.

## Examples

**Generate into the canon:**
```
/design-system generate --style minimal --palette earth-tones
# → .design/DESIGN.md + .design/design-tokens.json (DTCG)
```

**Audit an existing UI (DESIGN-EVAL v1):**
```
/design-system audit --url http://localhost:3000 --pages / /pricing /docs
# → .design/audit.json (Track-A) + .design/critique-output.json (Track-B, 9-dim verdict)
```

**Check for AI slop (advisory anchors):**
```
/design-system slop-check
# → info/low findings folded into the DESIGN-EVAL v1 critique
```
