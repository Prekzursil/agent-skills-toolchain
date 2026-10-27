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

### How It Works
### Mode 1: Generate Design System
### Mode 2: Visual Audit — DESIGN-EVAL v1 (canonical)
### Mode 3: AI Slop Detection (advisory critique pack)
### The `.design/` artifact contract
### <a name="token-spine"></a>Token spine (DTCG)
### Examples
### → .design/DESIGN.md + .design/design-tokens.json (DTCG)
### → .design/audit.json (Track-A) + .design/critique-output.json (Track-B, 9-dim verdict)
### → info/low findings folded into the DESIGN-EVAL v1 critique
