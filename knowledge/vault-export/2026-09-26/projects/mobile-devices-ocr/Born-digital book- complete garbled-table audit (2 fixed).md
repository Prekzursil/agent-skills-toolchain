---
title: 'Born-digital book: complete garbled-table audit (2 fixed)'
type: report
permalink: main/projects/mobile-devices-ocr/born-digital-book-complete-garbled-table-audit-2-fixed
tags:
- ocr-pipeline
- born-digital
- tables
- figures
- audit
---

# Born-digital book: complete garbled-table audit

Project: `C:\Users\Prekzursil\Downloads\Mobile Devices`, branch `ocr-pipeline`.
Goal: 287-page Romanian psychology textbook → flawless born-digital DOCX+PDF, 100% integrity.

## The problem
Uncaptioned **side-by-side grid tables** (cells in parallel columns) get flattened into
reading-order word-salad when reflowed to text — they carry no `Tabel` caption, no numeric
data cells, and have too few rows (<6) for `uncaptioned_table_regions` (UNCAP_MIN_ROWS=6),
so they slip past every detector. Example garble on pdf80: "Emisfera Emisfera Emisfere
cerebrale Modalitate cerebrală stângă cerebrală dreaptă integrate Vizual cu Vizual cu...".

## The complete audit (the durable result)
A **deterministic multi-column-band scan** over all 281 content pages (lines sharing a
y-band across >80pt x-gaps, NOT covered by an existing figure region) found 46 candidate
bands → 36 merged per-page crops. A 36-crop **vision classification** (workflows
`classify-tables` 1/2/3, tool-restricted Read-only agents on source crops) found **EXACTLY
TWO genuine garbled side-by-side grid tables** in the whole book:

- **book66** — emisfere cerebrale 4×4 grid ("Modalitatea dominantă… | Emisfera cerebrală
  stângă | dreaptă | Emisfere integrate" × Vizual/Auditiv/Tactilo-kinestezic).
- **book122** — behaviour-tracking FORM ("Ziua | Momentul | Comportamentul | Consecințele"
  × Luni/Marți, dash cells).

All other 34 multi-column bands are prose / stacked single-column lists (which linearize
fine, e.g. the multiple-intelligences "Tip de inteligență…/Caracteristici…/Consecințe…"
list) / captioned figures. book15 (dev-stages) and book93 (communication-styles) were
ALREADY imaged via cross-page continuation (their tables start on book14/book92).

## The fix
`_EXPLICIT_GRID_TABLES` dict in `digital/figures.py` (vision-verified tight bboxes), wired
into `detect_regions` via `_explicit_grid_regions` → emitted as `kind="figure"` (imaged,
never run through extract_table). Tight bboxes: book66 (108,122,526,298), book122
(166,469,459,515). Rebuild: figures 30→32, completeness PASS (0 prose lost), region
UNDER-ext 0, 226 tests pass (+4 new). Both fixes visually confirmed on rendered pdf80/pdf155.

## Key lesson
[[Vision sweeps are unreliable for flattened tables]] — the prior full-book vision audit
(wf weztxbmt5) reported 363/365 clean but MISSED the book66 emisfere garble: agents read
the scrambled cells as plausible prose. The reliable detector for this defect class is the
DETERMINISTIC multi-column-band scan, with vision used only to classify the candidate crops.

## Page-numbering note
`Store.load(N)` == document.json `book_page N` == `config.CROP_PDF` (== ABBYY PDF) page N
(all aligned). But the rendered output PDF (365 pp) ≠ that space (281 content pages reflow
+ front matter); map output pages by searching distinctive text (e.g. "Luni" → pdf155).
