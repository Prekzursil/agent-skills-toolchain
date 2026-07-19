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
- The critique rubric math → `critique-panel` / `ui-audit` Track-B.

---

## The three CLIs

### 1. `extract_tokens.mjs` — code → DTCG
Pull design tokens **out of code** into a DTCG JSON tree (the code is the source of truth
for a code-first repo).
```powershell
$DT = "$HOME/.claude/skills/design-tokens-pipeline"
node $DT/extract_tokens.mjs --css src/theme.css,src/tokens.css --tailwind theme.json --prefix tw --out tokens.json
#   reads `--name: value;` custom properties (any selector; :root recommended) + a Tailwind
#   theme dump; infers DTCG $type; converts `var(--x)` refs to `{group.token}` aliases.
#   -> SUCCESS:design-tokens-extract <n> / FAILED:...
```

### 2. `validate_tokens.mjs` — gate the DTCG file
Check the DTCG v1.0 rules that **actually break the Tokens-Studio ⇄ Style-Dictionary
round-trip**:
| rule id | meaning |
|---|---|
| `missing-type` | leaf token has no resolvable `$type` (own or inherited) |
| `bad-alias` | a `{group.token}` alias points at a non-existent token |
| `alias-cycle` | aliases form a cycle (a → b → a) — Style Dictionary would loop |
| `raw-hex-in-code` | a `$type:color` raw hex AND a sibling alias of the same value exists (the §G1 "no raw hex" token gate) |
| `reserved-misuse` | a `$`-prefixed key outside the DTCG reserved set |
```powershell
node $DT/validate_tokens.mjs --file tokens.json --strict
#   --strict treats raw-hex-in-code warnings as failures too.
#   -> SUCCESS:design-tokens-validate <n ok> / FAILED:... <n errors>
```

### 3. `token_diff.mjs` — the revert surface
Diff two DTCG trees and emit **BOTH** the forward change set **AND** the inverse patch.
The inverse patch IS the lossless revert artifact the TCR loop relies on
(`DESIGN-WORKFLOW.md §G6`: "every apply-back is a reversible commit; revert anything that
regresses a tracked axis"):
```powershell
node $DT/token_diff.mjs --before old.json --after new.json --out diff.json --revert revert.json
#   --revert writes a DTCG tree that, applied over `after`, restores `before` exactly.
#   -> SUCCESS:design-tokens-diff <added>+<removed>+<changed> / FAILED:...
```

### Transform (optional) — `style-dictionary.config.mjs`
Transform the DTCG tree to platform outputs (CSS vars, JS, etc.) via **Style Dictionary 4
+ @tokens-studio/sd-transforms** (`npm i` the devDependencies first).

---

## DTCG essentials (the format this skill speaks)

- A **token** is an object with a `$value` (and usually a `$type`); a **group** is a plain
  object of tokens/groups and may carry a `$type` that descendants inherit.
- **Aliases** reference another token with `{group.token}` syntax.
- **Reserved keys** start with `$`: `$value`, `$type`, `$description`, `$extensions`,
  `$deprecated`. Anything else `$`-prefixed is `reserved-misuse`.

---

## Where this sits — the loop neighbors

```
G0/G5 ─ extract_tokens (code -> DTCG) ──▶ validate_tokens (gate) ──▶ Style Dictionary transform
G6   ─ token_diff (forward + inverse patch)  ◀ the lossless revert surface
```

**REQUIRED NEIGHBORS:** `design-review-loop` (invokes this token spine at G5/G6) ·
`figma` (`use_figma`) + Tokens Studio (the Figma side of the round-trip) · `design-system`
(consumes the validated token set) · `figma-implement-design` (G6 code-side apply-back).

---

## TDD

```powershell
cd ~/.claude/skills/design-tokens-pipeline
npm test   # node --test tests/tokens.test.mjs
```

Covers: CSS custom-property + Tailwind extraction and `$type` inference · `var()` →
`{alias}` conversion · all five validation rules (missing-type, bad-alias, alias-cycle,
raw-hex-in-code, reserved-misuse) · and the forward diff + inverse-patch round-trip
(applying `revert.json` over `after` restores `before` exactly).
