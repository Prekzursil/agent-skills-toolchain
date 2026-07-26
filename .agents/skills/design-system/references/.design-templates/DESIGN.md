# DESIGN.md — Design Canon (template)

> The single human canon for this repo's design system. There is **no** competing
> `design-system/MASTER.md`. Machine-readable tokens live beside this file in the
> **W3C-DTCG** `design-tokens.json`. Scored on **DESIGN-EVAL v1** (see
> `~/.claude/skills/ui-audit/critique_rubric.md`).

## 1. Principles

- _One primary action per screen; size + weight + colour (not size alone) carry hierarchy._
- _Start with too much whitespace; snap everything to the 4-8px spacing scale._
- _One primary + one accent; greys consolidated to tokens; body text clears WCAG AA (4.5:1)._
- _≤ ~6 type styles; motion in the 200-500ms band and honours `prefers-reduced-motion`._

## 2. Tokens (source of truth)

Authored in `design-tokens.json` (DTCG). Do not restate raw hex/px here — reference the
token names so the canon and the emitted CSS/Tailwind/Figma variables never diverge.

| Role | Token |
|------|-------|
| Page background | `color.semantic.bg` |
| Body text | `color.semantic.fg` |
| Primary accent | `color.semantic.primary` |
| Base spacing unit | `dimension.space.2` (8px) |
| Body type | `typography.font-size.body` @ `typography.line-height.body` |

## 3. Per-page overrides

Each route that deviates from the global system gets its own section. Gates read these
sections; keep them terse and token-referenced.

### `/` (home)
- _No override — inherits the global system._

### `/pricing`
- _Example: emphasise the recommended tier via `color.semantic.primary`; all other cards muted._

## 4. Definition of done (DESIGN-EVAL v1 ship gate)

A screen ships when its `critique-output.json` shows **mean ≥ 3.0**, **no dimension < 2**,
and **zero critical errors**. The verdict is computed, not asserted.
