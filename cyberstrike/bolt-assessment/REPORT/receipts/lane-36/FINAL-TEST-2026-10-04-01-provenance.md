# FINAL-TEST-2026-10-04-01 — LANE-36 STAGE A — PROVENANCE & BASELINE SEAL (subtask 132)

- Round: FINAL-TEST (directive 2026-10-04). Subtask: 132 (lane-36 stage A, offline static RE).
- Consolidation date: 2026-10-06. Execution artifacts generated 2026-10-04/05 under /work/lane36 (dir 0700).
- Mode: STRICTLY OFFLINE. Zero network, zero DNS, zero validation, zero PII. sha8-only fingerprints (first 8 hex of sha256 of VALUE). NEVER-ROTATE intact.

## A. Input provenance re-verification

| Artifact | Path | Size (B) | sha8 | Subtask-117 baseline | Verdict |
|---|---|---|---|---|---|
| Rider XAPK | /work/on-demand/apks/bolt-client_CA.225.0.xapk | 67,149,336 | 39db7771 | 39db7771 | MATCH |
| Driver XAPK | /work/on-demand/apks/bolt-driver_DA.147.0.xapk | 206,762,768 | 716cb535 | 716cb535 | MATCH |
| Inner client APK | /work/on-demand/apks/ca225/ee.mtakso.client.apk | 47,234,043 | 4662bc4e | 4662bc4e | MATCH |
| Inner driver APK | /work/on-demand/apks/da147/ee.mtakso.driver.apk | 186,483,772 | 7a8b9cf6 | 7a8b9cf6 | MATCH |

**Drift: NONE.** All four staged artifacts byte-match the subtask-117 baseline. Full-file sha256 values are recorded in /work/lane36/SHA256SUMS (21 entries, re-verified `sha256sum -c` 21/21 OK at consolidation time).

## B. Extracted-tree fingerprints (from TREE-FINGERPRINTS.txt)

- jadx_client: 35,452 files, aggregate sha8 14cf7324
- jadx_driver: 64,465 files, aggregate sha8 1b540eef
- at_client (apktool): 4,220 files, aggregate sha8 8f8a432b
- at_driver (apktool): 4,936 files, aggregate sha8 3c6c6293
- splits/: aggregate sha8 87b9bae7

Documented anomalies (informational, no impact): jadx_client.log truncated ~44% (decompile completed, tree complete); apktool driver decode logged 588 recoverable errors (resource-level only); PEM extractions named *_cert0.der.pem (public certificates).

## C. Split-APK layout (per XAPK internal manifest)

- ca225: base (ee.mtakso.client.apk) + 4 config splits: arm64_v8a, armeabi_v7a, mdpi, xxhdpi.
- da147: base (ee.mtakso.driver.apk) + 4 config splits: arm64_v8a, armeabi_v7a, mdpi, xxhdpi.
- Exact per-split sizes enumerated in /work/lane36/splits/ and receipt FINAL-TEST-2026-10-05-05.

## D. LANE-REGISTER deviation note (observed, not written by this lane)

- Expected baseline (subtask 117): 286 lines, sha256 98859339… on all three copies.
- Observed at consolidation: 402 lines, sha8 68f15cfb, three copies (REPORT/bolt-intel/intel-core) still byte-identical.
- Cause: closure appends by later lanes (incl. lane-36 stage-B receipts). No copy divergence; lane-36 stage A performs no register writes. NO ACTION; carry the 402/68f15cfb state forward to the close-out pre-check instead of the stale 286 baseline.

## E. Cross-references

- Detailed seal: FINAL-TEST-2026-10-05-05-lane36-stageA-baseline-seal.md.
- Structure: receipt -02 (this series). Secrets: receipt -03. Endpoints: receipt -04.
- Manifest: SHA256SUMS.lane-36 (this directory).

## F. Attestation

No network or DNS was performed in this subtask. No credential material was validated, decoded against live services, or exfiltrated. No artifact in this receipt contains a raw credential value or PII (sha8 fingerprints only; public-cert full SHA-256 permitted per task rules).
