---
name: design-studio
description: ONE entry to the whole design pipeline over a running app (Reframe, momentstudio, WebCoder, bilbo) — the mode-routed successor to design-review-loop. Runs the full TCR design-review loop (8 gates, G0 PRIME to G7 VERIFY, revert-gate) plus a thin mode router to jump to one stage — direct (scope, define good, pick a direction, palette/font), audit (a11y/contrast/dead-button UI audit, visual review), mirror (code-to-canvas transpose to Figma), critique (design-critique persona panel), iterate (Figma branch, design tokens), implement (Figma-to-code), verify (re-audit delta), loop (the whole pass), drive (drive/point/interact the live app, to ui-drive), session (interactive restyle of a live element, to design-studio-session). Absorbs the folded design skills' triggers — design review, design system audit, frontend design direction, visual review, mirror to Figma, implement design, drive the app, interactive tweak. NOT for a design DOCUMENT (metaswarm review-design) nor rubric math (ui-audit, critique-panel).
metadata:
  origin: user
---

<!-- origin: user (design-SOTA research, 2026-06-30); RENAMED from design-review-loop -> design-studio + thin mode router (gem-hunt 2026-07-12, item C1, evidence MASTER C.1 / UIUX C.1). Implements DESIGN-WORKFLOW.md §0/§2/§3 (the 8 gates + per-gate method + the transpose->discuss->revert micro-loop), DESIGN-SKILLS-AND-EVAL.md §1.2 (the orchestrator row) + §3 (engagement discipline, revert is first-class), FIGMA-SETUP.md (G2/G5/G6 Figma surface). -->


# design-studio Skill

The **design pipeline entry point** — the ONE named surface for the whole design workflow,
and the **TCR Loop orchestrator** underneath it. `design-studio` is the renamed, mode-routed
successor to `design-review-loop`: it drives a design-review pass as **8 sequenced gates**
AND exposes a **thin mode router** so you can jump straight to a single stage instead of the
whole loop. **TCR = Transpose · Critique · Reconcile** — the three verbs that ARE the
*transpose → discuss → revert* motion (gates G2 → G3 → G6).

**Skill location:** `~/.claude/skills/design-studio/`

> Implements `DESIGN-WORKFLOW.md §0` (the 8-gate headline + table), `§2` (each gate's
> canonical named method + standard questions), `§3` (the transpose→discuss→revert
> micro-loop); `DESIGN-SKILLS-AND-EVAL.md §1.2` (the orchestrator row — *keep it thin; it
> orchestrates, the gates live in the leaf skills*) + `§3` (engagement discipline). Figma
> surface (G2/G5/G6): `FIGMA-SETUP.md`. Consolidation rationale: UIUX-CONSOLIDATION §1.1.

---

## The unified entry — the mode router (the ONE surface)

### The router table — mode → gate → leaf → absorbed trigger vocab
### Two modes route OUT of this skill (not gates)
### How an in-loop mode maps to the harness
### Overview — keep the orchestrator THIN
### When to use
### The headline — the 8 named gates
### The single load-bearing truth: the round-trip is LOSSY
### Driving the loop (the harness)
### G0 — start a pass (records scope + source-of-truth + altitude; opens at G0 PRIME)
### -> prints the G0 question bank; SUCCESS:design-review-<id>-G0
### Show the CURRENT gate's method + leaf skill + standard questions (the next thing to run)
### or a specific gate:  node $DR gate --gate G3 --out $OUT
