---
name: systematic-review-screening
description: Use when screening studies for a review, thesis, or evidence map with explicit inclusion and exclusion criteria and borderline-case handling.
---

# systematic-review-screening

This skill applies study-eligibility rules consistently. It is built for title/abstract screening, full-text screening, and documenting why studies stayed in or fell out.

## When to use

- The user is running a systematic review, scoping review, evidence map, or thesis literature screen.
- Inclusion and exclusion rules exist or need to be made explicit.
- Borderline studies need disciplined adjudication rather than gut feeling.

## Workflow

1. Rewrite the inclusion and exclusion rules into operational checks.
2. Screen in two passes: title/abstract first, then full text for survivors.
3. Assign one decision per record: include, exclude, maybe, or unresolved.
4. For every exclusion, record the single best reason rather than a pile of vague reasons.
5. Summarize counts, disagreement clusters, and rule failure points.

## Configuration and access

- If using citation managers, spreadsheets, or screening platforms, reference only their project or export labels.
- Preserve record IDs, DOI, and screening stage.

## Output standard

- Return a screening table or ledger, not just prose.
- Keep reasons short, rule-based, and comparable across records.

## Guardrails

- Do not silently tighten or loosen criteria midstream.
- Do not hide borderline cases; surface them for explicit adjudication.
