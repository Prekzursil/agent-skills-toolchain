---
name: critique-panel
description: Use to run the G3 CRITIQUE gate of the TCR design-review loop - a four
  named-persona panel (user-advocate / systems-consistency / a11y / brand-aesthetic)
  that each REASON over ui-audit's Track-A numbers plus the screenshot, run the NN/g
  "I Like / I Wish / What If" ritual, score the nine DESIGN-EVAL v1 dimensions 0-4,
  then synthesize a severity-ranked findings list. A TRIAGE accelerator.
metadata:
  origin: user
permalink: dqverify-repo-20261013/skills/critique-panel/skill
---

<!-- origin: user (design-SOTA research, 2026-06-30); implements DESIGN-WORKFLOW.md G3 (NN/g Design Critique ritual + I Like/I Wish/What If + named multi-agent panel as TRIAGE), DESIGN-SKILLS-AND-EVAL.md §1.1 (one-persona-per-call reliability protocol), §1.2 (the four personas + quota), §2.1-§2.4 (0-4 scale, 9 dimensions/weights/critical triggers, weighted composite + cap), §3 (defer DIRECTION to the human; enumerate don't pick). -->


# critique-panel Skill

The **G3 CRITIQUE** gate of the TCR design-review loop — the *discuss edge*. Four named
heuristic personas each reason over the **same** pre-computed Track-A numbers
(`ui-audit` `audit.json`) + the screenshot, run the NN/g design-critique ritual, score
the nine **DESIGN-EVAL v1** dimensions 0–4, and emit a typed verdict. `synthesize` then
dedupes + ranks them into one findings list with a weighted composite.

**Skill location:** `~/.claude/skills/critique-panel/`

> The harness (`critique_panel.mjs`) is **pure plumbing** — it never calls a model and
> never measures pixels. It routes evidence onto each persona's owned dimensions, builds
> the per-persona brief, validates typed verdicts (incl. the quota gate), and aggregates.

---

## When to use

- The **G3 CRITIQUE** gate after `ui-audit` (G1) has produced `audit.json` + screenshots.
- You want a **multi-perspective**, severity-rated, typed critique (not "looks good to me").
- You want the panel to **enumerate + rank** defects and propose directions for the human.

**When NOT to use:**
- Driving the app / measuring pixels → that is `ui-audit` Track-A (this consumes its output).
- Picking the winning redesign direction → the **human decides at G4** (`frontend-design-direction`).
- The whole 8-gate loop end-to-end → `design-studio` (this is one leaf gate).

---

## The honesty note (cite it)

The panel is a **TRIAGE accelerator, NOT an oracle.** Multi-agent VLM critique has ~21%
expert overlap, ~24% false-positives, and is near-random at *picking* the better design
(WiserUI-Bench). So the personas **enumerate, score, and rank** — the **human is the
decider at G4** (`DESIGN-SKILLS-AND-EVAL.md §3.2`).

---

## The four named personas

Each persona stays in character and judges **only** its owned dimensions (one persona per
call kills the halo effect — `DESIGN-SKILLS-AND-EVAL.md §1.1`). Dimensions are
double-covered on the high-weight / critical-prone axes so the panel cross-checks.

| Persona | Method | Owned dimensions |
|---|---|---|
| **user-advocate** | Nielsen's 10 usability heuristics | visual-hierarchy, empty-error-states, affordance, consistency |
| **systems-consistency** | Refactoring UI + Material 3 / HIG + Nielsen #4 | spacing-rhythm, type-scale, alignment, consistency |
| **a11y** | WCAG 2.2 AA + WCAG 3.0 draft | color-contrast, affordance, motion |
| **brand-aesthetic** | Refactoring UI colour/personality + Nielsen #8 | visual-hierarchy, color-contrast, type-scale, motion |

The full per-persona method + the 0–4 band, severity ladder, nine dimensions/weights, and
critical-error triggers live in **`panel_rubric.md`** (the deterministic lens, schema-aligned).

---

## Driving the panel (the harness)

```powershell
$CP = "$HOME/.claude/skills/critique-panel/critique_panel.mjs"

# 1) ASSEMBLE — read audit.json + screenshot(s) + rubric, route numbers onto each
#    persona's owned dimensions, write FOUR persona briefs (.json + .md) to fill.
node $CP assemble --audit ./out/audit.json --screenshot a.png,b.png --scope /,/settings --out ./out

# 2) (Claude, as each persona) fill panel-<persona>.out.json — score 0-4 + I Like/I Wish/What If.

# 3) VALIDATE — type-check a persona verdict incl. the quota gate (>=2 iLike + 1 iWish/screen)
node $CP validate --input ./out/panel-user-advocate.out.json
#   -> SUCCESS:critique-panel-user-advocate-<id> / FAILED:...

# 4) SYNTHESIZE — merge verdicts -> ranked findings + weighted composite + protected wins
node $CP synthesize --inputs ./out/panel-*.out.json --audit ./out/audit.json --out ./out
#   -> SUCCESS:critique-panel-<id>

# Dump the persona + synthesis JSON Schemas (keep them in sync)
node $CP schema --out ./
```

**The contract:** the harness routes evidence and validates; **Claude reasons** as each
persona over the numbers; `synthesize` computes the verdict. The personas reason over
numbers Track-A already measured — they never pixel-ground.

---

## Scoring (from `panel_rubric.md`)

- **0–4 per owned dimension** + a `confidence`; `critical: true` only when that dimension's
  critical-error trigger fired (forces its score to **0**).
- **I Like** (wins to protect) / **I Wish** (severity-rated defects + recommendation) /
  **What If** (alternative directions to enumerate — *not* pick).
- **Quota (anti-tunnel-vision, even solo):** ≥2 `iLike` + 1 `iWish` per in-scope screen
  (the validator enforces it).
- **Composite:** `overall = 100 · Σ wᵢ·scoreᵢ / (4·Σ wᵢ)` with the critical cap (1 critical →
  ≤60; ≥2 → poor). **Ship gate:** mean ≥3.0 AND no dimension <2 AND zero critical errors.

color-contrast carries the highest weight (**2.0**); any body text below 4.5:1 is a
critical that forces color-contrast to 0.

---

## Where this sits — the loop neighbors

```
G1 AUDIT ─ ui-audit (Track-A numbers + screenshots)   ──audit.json──▶  THIS (G3 CRITIQUE)
G3 CRITIQUE ─ critique-panel  ◀ discuss edge          ──verdict──▶     G4 DIRECT (human decides)
```

**REQUIRED NEIGHBORS:** `ui-audit` (supplies `audit.json` + screenshots, shares the
DESIGN-EVAL v1 rubric) · `design-studio` (the orchestrator that invokes this at G3) ·
`frontend-design-direction` (G4, where the human picks among the enumerated directions).

---

## Terminal-state outputs

Every subcommand prints a marker on its last line (`AGENTS.md §4` anti-degeneration):
- `SUCCESS:critique-panel-<persona>-<id>` / `FAILED:critique-panel-<persona>-<id> <reason>` (validate)
- `SUCCESS:critique-panel-<id>` (synthesize)

---

## TDD

```powershell
cd ~/.claude/skills/critique-panel
npm test   # node --test tests/panel_schema.test.mjs tests/cli.test.mjs
```

Covers: persona vocabulary + owned-dimension routing · the typed persona + synthesis
schemas · the quota gate · the weighted composite + critical-error override/cap · and the
CLI assemble/validate/synthesize round-trip with terminal-state markers.