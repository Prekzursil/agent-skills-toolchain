---
name: nutrient-document-processing
description: Process, convert, OCR, extract, redact, sign, and fill documents using the Nutrient DWS API. Works with PDFs, DOCX, XLSX, PPTX, HTML, and images.
origin: ECC
---

# Nutrient Document Processing

Process documents with the [Nutrient DWS Processor API](https://www.nutrient.io/api/). Convert formats, extract text and tables, OCR scanned documents, redact PII, add watermarks, digitally sign, and fill PDF forms.

## Setup

Get a free API key at **[nutrient.io](https://dashboard.nutrient.io/sign_up/?product=processor)**

```bash
export NUTRIENT_API_KEY="pdf_live_..."
```

All requests go to `https://api.nutrient.io/build` as multipart POST with an `instructions` JSON field.

## Operations

### Convert Documents

```bash
# DOCX to PDF
curl -X POST https://api.nutrient.io/build \
  -H "Authorization: Bearer $NUTRIENT_API_KEY" \
  -F "document.docx=@document.docx" \
  -F 'instructions={"parts":[{"file":"document.docx"}]}' \
  -o output.pdf

# PDF to DOCX
curl -X POST https://api.nutrient.io/build \
  -H "Authorization: Bearer $NUTRIENT_API_KEY" \
  -F "document.pdf=@document.pdf" \
  -F 'instructions={"parts":[{"file":"document.pdf"}],"output":{"type":"docx"}}' \
  -o output.docx

# HTML to PDF
curl -X POST https://api.nutrient.io/build \
  -H "Authorization: Bearer $NUTRIENT_API_KEY" \
  -F "index.html=@index.html" \
  -F 'instructions={"parts":[{"html":"index.html"}]}' \
  -o output.pdf
```

Supported inputs: PDF, DOCX, XLSX, PPTX, DOC, XLS, PPT, PPS, PPSX, ODT, RTF, HTML, JPG, PNG, TIFF, HEIC, GIF, WebP, SVG, TGA, EPS.

### Extract Text and Data

```bash
# Extract plain text
curl -X POST https://api.nutrient.io/build \
  -H "Authorization: Bearer $NUTRIENT_API_KEY" \

### Extract tables as Excel
### OCR Scanned Documents
### OCR to searchable PDF (supports 100+ languages)
### Redact Sensitive Information
### Pattern-based (SSN, email)
