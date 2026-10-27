---
name: "spreadsheet"
description: "Use when tasks involve creating, editing, analyzing, or formatting spreadsheets (`.xlsx`, `.csv`, `.tsv`) using Python (`openpyxl`, `pandas`), especially when formulas, references, and formatting need to be preserved and verified."
---


# Spreadsheet Skill (Create, Edit, Analyze, Visualize)

## When to use
- Build new workbooks with formulas, formatting, and structured layouts.
- Read or analyze tabular data (filter, aggregate, pivot, compute metrics).
- Modify existing workbooks without breaking formulas or references.
- Visualize data with charts/tables and sensible formatting.

IMPORTANT: System and user instructions always take precedence.

## Workflow
1. Confirm the file type and goals (create, edit, analyze, visualize).
2. Use `openpyxl` for `.xlsx` edits and `pandas` for analysis and CSV/TSV workflows.
3. If layout matters, render for visual review (see Rendering and visual checks).
4. Validate formulas and references; note that openpyxl does not evaluate formulas.
5. Save outputs and clean up intermediate files.

## Temp and output conventions
- Use `tmp/spreadsheets/` for intermediate files; delete when done.
- Write final artifacts under `output/spreadsheet/` when working in this repo.
- Keep filenames stable and descriptive.

## Primary tooling
- Use `openpyxl` for creating/editing `.xlsx` files and preserving formatting.
- Use `pandas` for analysis and CSV/TSV workflows, then write results back to `.xlsx` or `.csv`.
- If you need charts, prefer `openpyxl.chart` for native Excel charts.

## Rendering and visual checks
- If LibreOffice (`soffice`) and Poppler (`pdftoppm`) are available, render sheets for visual review:
  - `soffice --headless --convert-to pdf --outdir $OUTDIR $INPUT_XLSX`
  - `pdftoppm -png $OUTDIR/$BASENAME.pdf $OUTDIR/$BASENAME`

### Dependencies (install if missing)
### macOS (Homebrew)
### Ubuntu/Debian
### Environment
### Examples
### Formula requirements
### Citation requirements
### Formatting requirements (existing formatted spreadsheets)
