---
name: evidence-ledger-synthesis
description: Use when the user needs a claim-by-claim evidence ledger before writing a review, memo, paper section, or recommendation.
---

# evidence-ledger-synthesis

This skill forces synthesis through an evidence ledger. It is the right lane when the user needs confidence-calibrated synthesis instead of an elegant but unsupported narrative.

## When to use

- The output will make recommendations or strong claims.
- Multiple sources disagree or vary in quality.
- The user needs the reasoning trail, not only the final prose.

## Workflow

1. List the material claims or questions the output must answer.
2. Attach source support to each claim with confidence labels such as VERIFIED, INFERRED, UNVERIFIED, or CONFLICTING.
3. Note the best opposing evidence and the likely reason for disagreement.
4. Only after the ledger is stable, write the narrative synthesis.
5. End with what would most improve confidence if checked next.

## Configuration and access

- Preserve source IDs and citation anchors in the ledger.
- If source-management tools exist, request only the project label or export path.

## Output standard

- Lead with the synthesis, but keep the ledger attached or referenced.
- Confidence language must reflect evidence quality, not stylistic certainty.

## Guardrails

- Do not hide weak evidence behind polished prose.
- Do not convert a single source into a settled consensus.
