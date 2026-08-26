---
name: scopus-wos-coverage-auditor
description: Use when comparing Scopus, Web of Science, Dimensions, or related indexing outputs and the user needs a disciplined explanation of differences.
---

# scopus-wos-coverage-auditor

This skill audits database-coverage disagreements. It is for explaining why one index finds a paper, citation count, or journal signal that another one does not.

## When to use

- Citation counts, h-index signals, journal coverage, or affiliation metrics differ across platforms.
- The user needs a defensible explanation before reporting metrics.

## Workflow

1. Identify the entity being compared: paper, author, journal, institution, or subject slice.
2. Normalize identifiers first: DOI, ORCID, ISSN, affiliation variant, or journal title.
3. Compare coverage assumptions, document types, update lag, and data-cleaning differences.
4. Summarize what is a real disagreement versus a platform-scope difference.
5. Recommend the least misleading metric to report.

## Configuration and access

- Save only identifiers, report paths, and platform labels.
- Keep account access user-controlled.

## Output standard

- Explain differences mechanistically, not as mysterious platform failure.
- State the reporting caveat that should travel with the metric.

## Guardrails

- Do not average incompatible metrics into one number.
- Do not report comparative counts without naming the source platform and date.
