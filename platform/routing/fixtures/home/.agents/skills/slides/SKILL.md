---
name: slides
description: Create and edit presentation slide decks (`.pptx`) with PptxGenJS, bundled layout helpers, and render/validation utilities. Use when tasks involve building a new PowerPoint deck, recreating slides from screenshots/PDFs/reference decks, modifying slide content while preserving editable output, adding charts/diagrams/visuals, or diagnosing layout issues such as overflow, overlaps, and font substitution.
---

# Slides

## Overview

Use PptxGenJS for slide authoring. Do not use `python-pptx` for deck generation unless the task is inspection-only; keep editable output in JavaScript and deliver both the `.pptx` and the source `.js`.

Keep work in a task-local directory. Only copy final artifacts to the requested destination after rendering and validation pass.

## Bundled Resources

- `assets/pptxgenjs_helpers/`: Copy this folder into the deck workspace and import it locally instead of reimplementing helper logic.
- `scripts/render_slides.py`: Rasterize a `.pptx` or `.pdf` to per-slide PNGs.
- `scripts/slides_test.py`: Detect content that overflows the slide canvas.
- `scripts/create_montage.py`: Build a contact-sheet style montage of rendered slides.
- `scripts/detect_font.py`: Report missing or substituted fonts as LibreOffice resolves them.
- `scripts/ensure_raster_image.py`: Convert SVG/EMF/HEIC/PDF-like assets into PNGs for quick inspection.
- `references/pptxgenjs-helpers.md`: Load only when you need API details or dependency notes.

## Workflow

1. Inspect the request and determine whether you are creating a new deck, recreating an existing deck, or editing one.
2. Set the slide size up front. Default to 16:9 (`LAYOUT_WIDE`) unless the source material clearly uses another aspect ratio.
3. Copy `assets/pptxgenjs_helpers/` into the working directory and import the helpers from there.
4. Build the deck in JavaScript with an explicit theme font, stable spacing, and editable PowerPoint-native elements when practical.

### Authoring Rules
### Recreate Or Edit Existing Slides
### Validation Commands
### Render slides to PNGs for review
### Build a montage for quick scanning
### Check for overflow beyond the original slide canvas
### Detect missing or substituted fonts
