---
title: HTML to PDF screen-faithful reproduction (Playwright colorScheme trap)
type: guide
permalink: main/reference/html-to-pdf-screen-faithful-reproduction-playwright-color-scheme-trap
tags:
- pdf
- playwright
- rendering
- html-to-pdf
- gotcha
- chrome
---

To convert an HTML page to a PDF that reproduces what the browser SHOWS ON SCREEN (dark theme, nav bar, backgrounds, filled form values) — not a print artifact.

## The problem
- [gotcha] Chrome `--print-to-pdf` renders the PRINT media stylesheet: white background, nav/header hidden, content paginated into Letter pages. It is NOT the on-screen view. #print-media
- [gotcha] Playwright `page.pdf()` renders SCREEN media (good) BUT defaults `colorScheme:'light'`. A page whose dark theme is gated on `@media (prefers-color-scheme: dark)` will still render LIGHT unless you explicitly emulate dark. This was the load-bearing miss — it cost a full failed attempt where screen-media was correct but the theme was still light. #colorScheme

## The working recipe
- [pattern] Use Playwright `page.pdf()` with `await page.emulateMedia({ media: 'screen', colorScheme: 'dark' })` before `page.pdf(...)`. The `colorScheme:'dark'` is mandatory for dark-themed pages. #recipe
- [pattern] Pass `printBackground: true` so CSS backgrounds/graphics are included. #recipe
- [pattern] Single continuous page (full scroll, no page breaks): measure `scrollHeight`, then `page.pdf({ width:'1440px', height: (scrollHeight+16)+'px', printBackground:true, pageRanges:'1' })`. Width 1440px = desktop view. #single-page
- [pattern] Load playwright-core from an existing skill's node_modules; fall back to `executablePath` = installed Chrome if the bundled browser is missing. #windows

## Verification (do NOT skip)
- [gotcha] Verify by rendering the PDF pages (PyMuPDF/`fitz` `get_pixmap`) and diffing AGAINST a screenshot of the source HTML (Chrome `--screenshot`) — NEVER compare the PDF to itself. Comparing an artifact to itself and calling it "faithful" is an overclaim; the user caught exactly this ("as you can see they are not identical"). #verify-against-source
- [check] Cheap objective signal for dark-theme success: sample the top-left background pixel of the rendered PDF — RGB (0,0,0) confirms dark rendered, white confirms the print/light trap fired. #signal

## Minimal script shape
```js
const { chromium } = require('.../playwright-core');
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
await page.goto('file:///.../page.html', { waitUntil: 'load' });
await page.emulateMedia({ media: 'screen', colorScheme: 'dark' }); // THE FIX
await page.waitForTimeout(2500);
const h = await page.evaluate(() => Math.ceil(Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)));
await page.pdf({ path: out, width: '1440px', height: (h+16)+'px', printBackground: true, pageRanges: '1' });
```

## Relations
- relates_to [[Capture-don't-infer (pipeline failures)]]
- relates_to [[Windows-Shell Footguns]]

Source: OpenAI Pilot HTML→PDF conversion, session 2026-07-13. Full-width colon (：, U+FF1A) note: valid in Windows filenames; copy the source to an ASCII path before building to avoid file:// URL escaping issues.
