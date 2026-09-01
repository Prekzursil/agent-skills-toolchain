---
name: apa-citation-discipline
description: Use when writing or repairing APA-style academic prose, references, in-text citations, and attribution discipline without citation laundering.
---

# apa-citation-discipline

This skill enforces citation discipline first and style second. The aim is correct attribution, reference completeness, and clean academic prose that matches the requested APA style constraints.

## When to use

- The user needs APA-compliant citations or references.
- A paper draft has inconsistent author-year formatting, missing metadata, or unsupported claims.
- The user wants grammar and style fixes without weakening evidence fidelity.

## Workflow

1. Identify the requested style boundary: APA 7th references, in-text citations, tables, headings, or all of them.
2. Check whether each citation actually supports the adjacent claim.
3. Normalize author names, year, title, source, DOI, URL, and retrieval notes only where they are required.
4. Repair prose for clarity and grammar after citation accuracy is secured.
5. Return both the corrected text and a concise list of unresolved metadata gaps.

## Configuration and access

- Use DOI and canonical metadata where possible; keep raw URLs only when no DOI exists.
- If bibliographic tools are available, request only the library label or export path.

## Output standard

- Preserve meaning while tightening wording.
- Surface unsupported claims explicitly instead of smoothing them over.
- When reference data is incomplete, mark the exact missing field.

## Guardrails

- Do not invent publication details.
- Do not add citations to claims unless the source has been checked.
- Do not let formatting polish hide evidence defects.
