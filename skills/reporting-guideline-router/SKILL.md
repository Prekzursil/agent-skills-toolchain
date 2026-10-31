---
name: reporting-guideline-router
description: Use when the manuscript or protocol needs the correct reporting guideline
  lane such as PRISMA, CONSORT, STROBE, ARRIVE, STARD, CARE, or COREQ.
permalink: dqverify-repo-20261013/skills/reporting-guideline-router/skill
---

# reporting-guideline-router

This skill routes a manuscript to the right reporting guideline family and turns the guideline into an actionable completeness pass.

## When to use

- The user is writing methods, results, or a protocol and needs the right checklist.
- The study design is known but the reporting standard is unclear.

## Workflow

1. Identify the actual study design, not just the broad field.
2. Match it to the nearest reporting standard and note close alternatives when relevant.
3. Turn the checklist into concrete missing-information questions.
4. Return a targeted completeness pass rather than a pasted checklist dump.

## Configuration and access

- Preserve the chosen guideline name and version with the manuscript notes.

## Output standard

- State the selected guideline first.
- Then list the most important missing items in writing order.

## Guardrails

- Do not force one guideline onto a clearly different study design.
- Do not claim compliance without actually checking the items.