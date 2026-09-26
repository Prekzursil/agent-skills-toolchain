---
title: Scrollshot markdown wiring and backend gate update 2026-08-19
type: note
permalink: main/projects/reframe/scrollshot-markdown-wiring-and-backend-gate-update-2026-08-19
tags:
- reframe
- scrollshot
- ocr
- coverage
---

# Scrollshot markdown wiring and backend gate update 2026-08-19

- Reframe now has `scrollshot.exportMarkdown` wired through the sidecar composition root and renderer workspace tab.
- Backend scrollshot core repaired to use signed overlap placement, seam-based composition, and direct system Tesseract TSV OCR instead of the missing `pytesseract` package.
- Focused backend gate passed at 100% line + branch coverage for `media_studio.features.scrollshot` and `media_studio.features.scrollshot_markdown`.
- Focused renderer tests for the new `ScrollshotMarkdown` panel and `Workspace` tab passed.
- Real-media E2E is still red on alignment quality for the downscroll duplicate/skip fixture; current known issue is false cycle mismatch / pose inconsistency on long-range edges. Canonical result schema fields were added during the same repair pass.
- Related repo doc: `docs/wiring/WIRING-scroll-markdown.md`.
