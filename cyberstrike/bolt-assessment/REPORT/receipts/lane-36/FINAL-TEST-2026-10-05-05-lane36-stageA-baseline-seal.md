# FINAL-TEST RECEIPT 05 — lane-36 Stage A Phase 1: Integrity Baseline Seal

- Engagement: Bolt Technology OÜ red-team (operator directive 2026-10-04, verbatim authority on record)
- Round / subtask: FINAL-TEST / subtask-143 (lane-36 mobile reverse-engineering, stage A)
- Date sealed: 2026-10-05
- Register impact: NONE — this receipt appends nothing to LANE-REGISTER.md (register close-out is subtask-147)
- OFFLINE ATTESTATION: phase 1 executed fully offline — zero network (no gateway sentinel, no DNS, no HTTP), zero secret-validation attempts, residential proxy vault untouched, NEVER-ROTATE discipline intact.

## 1. Artifact provenance (XAPK -> splits)
| artifact | bytes | sha8 |
|---|---|---|
| bolt-client_CA.225.0.xapk (rider XAPK) | 67,149,336 | 39db7771 |
| bolt-driver_DA.147.0.xapk (driver XAPK) | 206,762,768 | 716cb535 |
| ee.mtakso.client.apk (inner base APK) | — | 4662bc4e |
| ee.mtakso.driver.apk (inner base APK) | — | 7a8b9cf6 |

Split-APK composition per app (identical set of 4 config splits):
- config.arm64_v8a.apk  13,321,469 B
- config.armeabi_v7a.apk 19,125,834 B
- config.mdpi.apk        1,136,807 B
- config.xxhdpi.apk       3,440,053 B

## 2. Sealed baselines (under /work/lane36/)
- SHA256SUMS — 21 compact artifacts, relative paths, mode 0600:
  sha256 8ed49658f63d5172dd138b8bf5103a70aafeea4c3ab3e38d3f6aa202a466f02d
  Re-verified at phase-3 seal time: `cd /work/lane36 && sha256sum -c SHA256SUMS` -> 21/21 OK, 0 non-OK.
- TREE-FINGERPRINTS.txt — mode 0600, sha256 a64bacbb6caa9c2b77eda5417b2b11ae18cae522efe019f3c7cd774daeb13283, sealed 2026-10-05T04:29:12Z:
  - jadx_client  files=35,452 (expected 35,452 — MATCH)  aggregate_sha256 14cf732446c15595981490ae54987ffd939ea8342e3e8d11f077173055f9a806
  - jadx_driver  files=64,465 (expected 64,465 — MATCH)  aggregate_sha256 1b540eef5bfca388cd666e10ccc10a33fe8bbb402948bf108bab8ea4cae7e5e7
  - at_client (apktool tree)  files=4,220  aggregate_sha256 8f8a432b27aea0ced698c9b6bec245e4039470adc4828c608d05956f5b27bfe8
  - at_driver (apktool tree)  files=4,936  aggregate_sha256 3c6c62930c66e6d28c50350412ac8d750e48302d0145d968e13327c0d7563880
  - splits (4 config APKs)               aggregate_sha256 87b9bae79afbf81e8dbb267c33da14333ba79c3b756232b308339c56bfaba599
  - xapk_meta_client                      aggregate_sha256 3b7985e046f9950acaa25a4858690d615bb3671204ddc763e1dbd85f319a9fbc
  - xapk_meta_driver                      aggregate_sha256 019da872d4f557e41fff6e8d29b6bd60f57127d31effe0317149bc5e22784ade
  Method: sha256 over the sorted per-file sha256 listing (LC_ALL=C; find <tree> -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum). The ~100k jadx tree files are intentionally EXCLUDED from SHA256SUMS and anchored by these fingerprints instead; trees are read-only and never re-hashed in place.

## 3. Compact artifacts covered by SHA256SUMS (21 entries)
manifest_client.json (10,949 B); manifest_driver.json (8,974 B); secret_catalog.json (27,053 B); secret_catalog.tsv (130 rows + header); client_cert0.der (1,421 B); client_cert0.der.pem (1,980 B); driver_cert0.der (1,421 B); driver_cert0.der.pem (1,980 B); strings_client.txt (1,943,499 B); strings_driver.txt (38,857,527 B); jadx_client.log; jadx_driver.log; apktool_client.log; apktool_driver.log; braze_neveruse_sha8.txt; apk_sigblock.py; extract_certs.py; manifest_analyzer.py; secret_sweep.py; xapk_meta_client/manifest.json; xapk_meta_driver/manifest.json.

## 4. Recorded anomalies (flagged, deliberately NOT fixed)
1. jadx_client.log truncated ~44% (52,269 B) — DB-crash-era artifact (crash at 2026-10-05T01:17Z, disk-full, since cleaned). Tree file count and aggregate fingerprint are EXACT, so decode-tree stability is unaffected; log re-run not required for stage B.
2. jadx_driver completed with 588 decode errors — normal for the heavily obfuscated driver build; tree count and fingerprint exact.
3. Extracted PEM filenames follow the *_cert0.der.pem convention — EXPECTED naming, not a defect; do not "fix".

## 5. Closing attestations (subtask-143, 2026-10-05)
- Zero network, zero DNS, zero gateway contact during stage A phases 1-3.
- Zero secret-validation attempts; ALL secret references are sha8-only.
- Proxy vault /work/bolt/.vaults/proxy-residential: mode 0600 confirmed by passive stat + line-hash check only; NEVER-ROTATE intact.
- Zero PII; zero credential values; zero proxy userinfo.
- Leak-gate (phase 3) over every file in this receipts dir: PASS (0 hits per pattern).
- LANE-REGISTER.md untouched by this receipt (verified byte-identical x3 at 286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
