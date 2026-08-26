---
name: long-pdf-evidence-synthesizer
description: Use when the user needs a professional synthesis of a long PDF, report, thesis, or policy document with section-accurate evidence tracking and clear separation between author claims and your synthesis.
---

# long-pdf-evidence-synthesizer

This skill turns long PDFs into audit-friendly syntheses. The job is not just to shorten the file; it is to preserve structure, evidence, limitations, and decision relevance.

## When to use

- A PDF is too long to read linearly and the user needs a defensible summary.
- The result will feed a paper, report, policy memo, study plan, or executive brief.
- The user needs section-level extraction rather than a generic paragraph summary.

## Workflow

1. Classify the document: empirical paper, review, thesis, policy report, guidance, or textbook material.
2. Build a section map with page ranges and a one-line role for each section.
3. Extract the governing question, methods or reasoning basis, key findings, limitations, and practical implications.
4. Keep an evidence ledger that maps each major claim back to the section or page span where it appears.
5. Deliver a layered output: executive summary, structured notes, risks, and follow-up questions.

## Configuration and access

- If OCR, PDF APIs, or document tools are available, reference only the tool or config slot by name.
- Preserve file path, title, publication year, and source URL or repository identifier when known.

## Output standard

- Use the sequence `question -> structure -> evidence -> findings -> limitations -> action items`.
- Mark what the document explicitly says versus what you infer.
- When useful, include a compact table of sections and evidence anchors.

## Guardrails

- Do not fabricate page numbers or quotes.
- Do not collapse limitations into conclusions.
- Preserve uncertainty when the underlying document is weak, outdated, or methodologically thin.
