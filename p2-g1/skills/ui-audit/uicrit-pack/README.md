# UICrit few-shot exemplar pack

Additive resource for the `ui-audit` skill's Track-B design critique. It supplies
**expert-authored few-shot anchors** (score `0` / `2` / `4`) for each of the nine
DESIGN-EVAL v1 scoring dimensions, so the critic can calibrate its per-dimension
score against real critique language before grading a new screen.

- **What:** `exemplars.json` — nine dimensions × three anchor bands (27 anchors), each
  with `band`, `critique`, `evidence`, and `recommendation` text plus a stable `id`.
- **Why:** the UICrit few-shot pattern (Duan et al., *UICrit: Enhancing Automated Design
  Evaluation with a UI Critique Dataset*, UIST 2024, arXiv:2407.08850) — anchoring an
  evaluator with a labelled critique corpus raised critique quality **~55%** over
  zero-shot. Evidence: gem-hunt MASTER C-Tier2 (`UICrit few-shot pack`), UIUX S.1,
  BUILD-CHARTER Wave 1 ("adopt UICrit pack").
- **Where it plugs in:** the DESIGN-EVAL rubric (`../critique_rubric.md` §2.5) and the
  `critique.mjs` instructions already tell the critic to *"use the few-shot anchors to
  calibrate"* and *"anchor with the few-shot exemplars under each dimension"*. This pack
  is the machine-readable, expanded form of those anchors.

## Scope & safety

- **Purely additive.** This subdir was created fresh; it modifies **no** existing
  `ui-audit` file. `capture.mjs`, `run_audit.mjs`, `critique.mjs`, `critique_schema.mjs`
  and the rubric are untouched.
- **Advisory / shadow only.** The pack changes no scoring math and adds no gate.
  `critique.mjs` computes the identical §2.4 weighted composite and §2.3 critical cap
  with or without it — it only sharpens the critic's *per-dimension judgement*. There is
  nothing here that can block or nag.
- **Synthetic-but-representative.** Anchor prose is written to the DESIGN-EVAL v1 rubric
  (grounded in Refactoring UI, Material 3, Apple HIG, Nielsen, WCAG 2.2 AA) in the UICrit
  style. These are **not** verbatim rows from the UICrit dataset (that corpus targets
  mobile screens and carries its own licence).

## How to consume it

During a Track-B critique, one dimension per reasoning pass (§2.5 reliability protocol):

1. Assemble the critique input as usual:
   `node critique.mjs assemble --audit ./out/audit.json --dimension color-contrast --out ./out`
2. **Before scoring** dimension `D`, read `exemplars.json → dimensions[D].anchors`.
3. Match the observed screen to the closest anchor band (`0` / `2` / `4`) and interpolate
   (`1` = between 0 and 2, `3` = between 2 and 4).
4. Cite the matched anchor `id` (e.g. `cc-0`) in the finding `evidence` for traceability.
5. Fill and validate the verdict as normal: `node critique.mjs validate --input <file>`
   then `node critique.mjs compute --input <file>`.

The `critical: true` flag on a band mirrors §2.3: an anchor whose score is `0` because a
critical-error condition tripped (e.g. body text < 4.5:1, render crash, dead primary
action, motion with no reduced-motion escape) — matching it forces that dimension's score
to `0` and caps the verdict.

### Optional: fold anchors into the assembled brief

If you want the anchors embedded in the assembled markdown brief without editing
`critique.mjs`, concatenate this pack's per-dimension anchors into a copy of the rubric
and pass it via the existing `--rubric` flag:

```bash
# reversible: builds a throwaway rubric+anchors doc, leaves the live rubric untouched
node uicrit-pack/build_anchored_rubric.mjs > ./out/rubric-anchored.md   # (helper is optional / not shipped)
node critique.mjs assemble --audit ./out/audit.json --rubric ./out/rubric-anchored.md --out ./out
```

No such wiring is committed here on purpose — keeping the pack a pure data resource
honours "does not modify existing ui-audit files". A future opt-in `--exemplars` flag on
`critique.mjs assemble` is the clean way to wire it in when desired.

## Files

| File | Purpose |
|------|---------|
| `exemplars.json` | The 9-dimension × 3-band anchor corpus (the pack). |
| `README.md` | This file. |
| `_test_pack.mjs` | Alignment test — proves the pack's dimension keys, weights, and anchor bands match `critique_schema.mjs`. Run `node uicrit-pack/_test_pack.mjs`. |

## `exemplars.json` shape

```jsonc
{
  "id": "uicrit-fewshot-pack",
  "rubric": "DESIGN-EVAL v1",
  "dimensions": {
    "<dimension>": {
      "weight": 2.0,                 // must equal DIMENSION_WEIGHTS[dimension]
      "question": "…",
      "anchors": [
        { "id": "cc-0", "score": 0, "critical": true,
          "band": "critical-error: …",
          "critique": "expert critique prose …",
          "evidence": "which Track-A signal / visual cue …",
          "recommendation": "actionable fix …" },
        { "id": "cc-2", "score": 2, "band": "…", "critique": "…", "evidence": "…", "recommendation": "…" },
        { "id": "cc-4", "score": 4, "band": "…", "critique": "…", "evidence": "…", "recommendation": "…" }
      ]
    }
    // … all nine SCORING_DIMENSIONS
  }
}
```

The nine dimensions are exactly `critique_schema.mjs`'s `SCORING_DIMENSIONS`:
`visual-hierarchy`, `spacing-rhythm`, `alignment`, `type-scale`, `color-contrast`,
`consistency`, `empty-error-states`, `affordance`, `motion`. The `_test_pack.mjs` gate
enforces that this stays true (keys, weights, and the 0/2/4 anchor bands).
