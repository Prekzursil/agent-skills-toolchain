---
name: critique-panel
description: Use to run the G3 CRITIQUE gate of the TCR design-review loop — a four named-persona design-critique panel (user-advocate / systems-consistency / a11y / brand-aesthetic) that each REASON over ui-audit's pre-computed Track-A numbers plus the screenshot, run the NN/g "I Like / I Wish / What If" ritual, score the nine DESIGN-EVAL v1 dimensions 0-4 with critical-error overrides, then synthesize into one deduped, severity-ranked findings list with a weighted composite and enumerated directions (the human decides at G4). The panel is a TRIAGE accelerator, not an oracle. Do NOT use to drive the app or measure pixels (that is ui-audit Track-A) or to pick the winning redesign direction (that is the human at G4). Pairs with ui-audit and design-review-loop.
metadata:
  origin: user
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

### The honesty note (cite it)
### The four named personas
### Driving the panel (the harness)
### 1) ASSEMBLE — read audit.json + screenshot(s) + rubric, route numbers onto each
### persona's owned dimensions, write FOUR persona briefs (.json + .md) to fill.
### -> SUCCESS:critique-panel-user-advocate-<id> / FAILED:...
### 4) SYNTHESIZE — merge verdicts -> ranked findings + weighted composite + protected wins
### -> SUCCESS:critique-panel-<id>
### Dump the persona + synthesis JSON Schemas (keep them in sync)
### Scoring (from `panel_rubric.md`)
### Where this sits — the loop neighbors
### Terminal-state outputs
