---
title: OCR digital store sanity 2026-06-12
type: report
permalink: main/projects/mobile-devices-ocr/ocr-digital-store-sanity-2026-06-12
tags:
- ocr
- digital
- sanity
- store
---

# OCR digital store sanity 2026-06-12

Read-only sanity on C:/Users/Prekzursil/Downloads/Mobile Devices (branch ocr-pipeline).

## Observations
- [tests] `python -m pytest tests/digital -q` => 67 passed, 1 deselected (pytest 9.0.2, Python 3.14.3). #pass
- [store] work2/store holds p001..p287 = 287 page JSONs; 6 skipped (pages 2,3,4,5,6,287), 281 content pages. Total 155046 words.
- [status-totals] agreed 148034 (95.48%), arbitrated 2642 (1.70%), abby_only 2535 (1.63%), junk_excluded 1713 (1.10%), voted 91 (0.06%), unresolved 31 (0.02%).
- [G2 gate] Status.UNRESOLVED words on content pages = 31, budget config.MAX_USER_FLAGS = 50 => 31 <= 50 PASS. This is the load-bearing "final content unresolved vs 50". #gate
- [discrepancy] Per-page `stats.unresolved` field SUMS to 350 across 158 pages, but actual Status.UNRESOLVED words = 31. The accept.py G2 gate counts word.status (31), NOT stats.unresolved (350). The stats.unresolved per-page counter appears stale/different metric — worth noting but does not affect the gate. #investigate
- [diacritics] Corpus-wide content text: legacy-cedilla (şţŞŢ U+015F/0163/etc) = 0 (G3 PASS); comma-below (șțȘȚ U+0219/021B) = 23794.
- [samples] p050/p120/p200 sampled: fluent coherent Romanian prose, comma-below diacritics correct, 0 legacy cedilla each.

## Relations
- part_of [[Mobile Devices OCR pipeline]]
