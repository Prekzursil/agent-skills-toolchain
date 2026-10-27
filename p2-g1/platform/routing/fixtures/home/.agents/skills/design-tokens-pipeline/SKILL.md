---
name: design-tokens-pipeline
description: Use for the W3C DTCG design-token round-trip that the TCR design-review loop relies on at G5/G6 — extract tokens out of code (CSS custom properties + Tailwind theme dumps) into a DTCG JSON tree, validate against the DTCG v1.0 rules that actually break the Tokens-Studio to Style-Dictionary round-trip (missing-type, bad-alias, alias-cycle, raw-hex-in-code, reserved-misuse), and diff two token trees to emit BOTH the forward change set AND the inverse revert patch (tokens are the one thing that round-trips losslessly, so the inverse patch is the revert surface). Transforms via Style Dictionary + sd-transforms. Do NOT use for visual capture (use transpose-to-figma) or for the critique rubric math (use critique-panel). Pairs with design-review-loop, figma, and design-system.
metadata:
  origin: user
---

<!-- origin: user (design-SOTA research, 2026-06-30); implements DESIGN-WORKFLOW.md §1 (DTCG tokens + Code-Connected components are the ONLY things that round-trip cleanly) + §G6 (every apply-back is a reversible commit), DESIGN-SKILLS-AND-EVAL.md §1.2 (the token spine for G5/G6), FIGMA-SETUP.md §3 (establish the Variables token set BEFORE capture). DTCG = W3C Design Tokens Community Group format spec v1.0 (Oct 28 2025). -->


# design-tokens-pipeline Skill

The **token spine** of the TCR design-review loop (G5 ITERATE / G6 RECONCILE) — the
W3C-DTCG round-trip surface. Tokens are **the only thing that round-trips losslessly**
between code and Figma (`DESIGN-WORKFLOW.md §1`), so this skill is where the durable,
revertible design state lives.

**Skill location:** `~/.claude/skills/design-tokens-pipeline/`

> Three pure Node CLIs (built-ins only for extract/validate/diff; Style Dictionary +
> sd-transforms only for the optional transform). Each emits a terminal-state marker.

---

## When to use

- **G0/G5**: lift CSS custom properties + a Tailwind theme into a DTCG token tree so
  Tokens Studio / Style Dictionary can round-trip them ("establish the Variables token set
  BEFORE capture" — `FIGMA-SETUP.md §3`).
- **G1 token gate**: prove every value is bound (no raw hex that duplicates a token alias).
- **G6 revert edge**: diff before/after token trees and emit the **inverse patch** — the
  lossless revert artifact the loop's revert-gate relies on.

**When NOT to use:**
- Visual capture of the running UI → `transpose-to-figma` (G2).

### The three CLIs
### 1. `extract_tokens.mjs` — code → DTCG
### reads `--name: value;` custom properties (any selector; :root recommended) + a Tailwind
### theme dump; infers DTCG $type; converts `var(--x)` refs to `{group.token}` aliases.
### -> SUCCESS:design-tokens-extract <n> / FAILED:...
### 2. `validate_tokens.mjs` — gate the DTCG file
### --strict treats raw-hex-in-code warnings as failures too.
### -> SUCCESS:design-tokens-validate <n ok> / FAILED:... <n errors>
### 3. `token_diff.mjs` — the revert surface
### --revert writes a DTCG tree that, applied over `after`, restores `before` exactly.
### -> SUCCESS:design-tokens-diff <added>+<removed>+<changed> / FAILED:...
### Transform (optional) — `style-dictionary.config.mjs`
