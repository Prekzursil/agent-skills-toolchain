---
name: data-extraction-matrix
description: Use when extracting structured evidence from papers into a matrix for synthesis, comparison, or review writing.
---

# data-extraction-matrix

This skill converts messy papers into comparable evidence rows. It is designed for extraction tables that can survive later audit and synthesis.

## When to use

- The user needs a study matrix, extraction sheet, or comparison table.
- Multiple papers must be aligned across participants, methods, interventions, outcomes, and limitations.

## Workflow

1. Define the extraction schema from the review question.
2. Pull only fields that matter to later synthesis.
3. Separate reported values from analyst comments.
4. Normalize units, terminology, and missing-value notation.
5. Return the matrix plus a list of fields that were difficult or ambiguous to extract.

## Configuration and access

- Use stable identifiers for each study row.
- If a spreadsheet or database target exists, reference the target label only.

## Output standard

- Produce structured rows first, prose interpretation second.
- Keep comments in a separate analyst field.

## Guardrails

- Do not fill blanks with assumptions.
- Do not merge distinct outcomes into one convenience column.
