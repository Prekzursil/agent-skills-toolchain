---
name: pdf-reader
description: Read a PDF and ground every extracted claim in a real source span (cited_text plus a page or char location) rather than a model-invented citation. Two paths, use together, the native Anthropic Citations API (attach the PDF as a document content block with citations enabled, so cited claims carry cited_text plus page_location) and the pdf-reader MCP server (read_pdf, search_pdf, pdf_evidence) for literal page and region evidence. Use when a question over a PDF needs defensible, quotable answers, when summarizing or extracting facts from a report or paper or contract, or when a claim about a PDF must point at the exact page and text it came from. Do NOT use for bulk OCR of scans (use ocr-suite) or for academic metadata and access tagging (use scholarly-literature-review).
---

# PDF Reader (citation-grounded)

Read a PDF and make every claim **provably traceable to a span in the source** —
a verbatim `cited_text` plus a page (or character) location — instead of a
model-generated `[1]` that maps to nothing. Two complementary paths; prefer to
run both so the API's grounding and the MCP's literal evidence corroborate.

> **`pdf-reader` is an MCP server, not a workflow you reimplement.** The
> `mcp__pdf-reader__*` tools do the extraction; this skill is the convention for
> *grounding* what they return. The native Citations API is the anti-hallucination
> guarantee — a cited span provably came from the PDF, not from the model.

## When to Activate

- Any Q&A, summary, or fact-extraction over a PDF where the answer must be defensible.
- "What does this report/paper/contract say about X" and you must quote the exact page.
- Building a cited claim list from a PDF (findings, obligations, figures, dates).
- A downstream consumer (deep-research, a review) needs per-claim `cited_text` + location.

Do **not** use for: bulk OCR of image-only scans (use `ocr-suite`); academic
metadata / access classification / citation graphs (use `scholarly-literature-review`
or `scholarly-access`); pure page-image rendering with no claim to ground.

## Path A — Native Citations API (the grounding guarantee)

Attach the PDF as a `document` content block with **`citations: {enabled: true}`**.
The response splits into `text` blocks; every cited block carries a `citations`
array whose entries are real spans from the PDF.

### Path B — pdf-reader MCP (literal page + region evidence)
### Workflow
### Quality Rules
### Pairs with
