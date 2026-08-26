---
name: methods-results-discussion-calibrator
description: Use when a draft paper has drift between methods, results, and discussion and needs section-to-section calibration.
---

# methods-results-discussion-calibrator

This skill realigns the central paper sections so the methods justify the results, the results justify the discussion, and the discussion does not outrun the evidence.

## When to use

- A paper draft reads as if the sections were written in isolation.
- Claims in the discussion exceed what the results can bear.

## Workflow

1. Extract each explicit claim from results and discussion.
2. Trace each claim back to the method and evidence that support it.
3. Flag section drift: unsupported claims, missing methods, or orphan results.
4. Rewrite section transitions and limits so the argument stays internally coherent.

## Configuration and access

- Preserve manuscript version, section notes, and evidence map only.

## Output standard

- Report the biggest alignment failures first.
- Provide concise rewrite directions by section.

## Guardrails

- Do not inflate discussion claims to make the paper sound stronger.
- Do not leave unsupported results in place without a warning.
