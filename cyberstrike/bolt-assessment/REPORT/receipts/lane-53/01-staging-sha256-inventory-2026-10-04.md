# lane-53 / 01 — Staging sha256 inventory

- **Date:** 2026-10-04 (UTC, pre-flight window).
- **Scope item:** final-round pre-flight part (b).
- **Method:** `sha256sum` per artifact; JSON entry counts via `jq` (array length; distinct = unique canonical-JSON lines; per-entry sha256 content-hash for dedupe); tree manifests = `find <tree> -type f | sort | sha256sum` over the listing.

## Inventory table

| # | Artifact (under /work/on-demand) | Bytes | sha256 | Count result |
|---|---|---|---|---|
| 1 | `drive-staging/wave-2026-09-14/cowork-inv/secrets_found.json` | 340,202 | `2966783c47e55f068eb5e6fdebe698b03edb0d9f187f3ff076864827567d59e9` | **500 entries / 500 distinct** |
| 2 | `drive-staging/wave-2026-09-14/bolteu-github-inv/secrets_found.json` | 38,836 | `b44ca784382916a2942ca3610992c4a58339b84137ae27a58a03a1250a394f70` | **46 findings / 46 distinct** |
| 3 | `apks/bolt-client_CA.225.0.xapk` | 67,149,336 | `39db7771846c094969a1985070645f589fe248652c10f6062d19446ddf8b3ddb` | — |
| 4 | `apks/bolt-driver_DA.147.0.xapk` | 206,762,768 | `716cb5350dfe26bc4abb538e16e08d8231e7a70007a0bdc589c03480eba184dc` | — |
| 5 | `apks/ca225/` tree (1 file: `ee.mtakso.client.apk`) | 47,234,043 | inner sha256 `4662bc4ed09c2778dadb8913568d3befad82a882a041bc9d7db83db223834b64` | manifest-listing sha256 `ce00cc600894a4f54e8a090eca147a1e90fbc88f26c2c4f89a36597c722ac163` |
| 6 | `apks/da147/` tree (1 file: `ee.mtakso.driver.apk`) | 186,483,772 | inner sha256 `7a8b9cf653cc9c920f3c2574e8921cff59928caeb85e424031ac2033a79f7038` | manifest-listing sha256 `ba9b3a7cccbb3df7d40b57b9c10d1f7f0e3123c64609c990e2b21a8945906bf6` |
| 7 | `deep-mine/jwt_triage_v2.tsv` | 112,472 | `b9bcb15ce3a61349e945e180278617b7e587b70cf4b0dcde2b3127a3977a324a` | 1,145 lines |

## Notes

- **cowork-inv copy:** entry fields `{context, sha8, sources, type, value}`; sweep metadata: cap=500, distinct_kept=500, total_grep_lines=26,238, lines_with_credential_match=11,783, total_pattern_occurrences=18,569, sources_scanned=2. Distinct confirmed independently: 500/500.
- **bolteu-github-inv copy:** entry fields `{locations, n_locations, occurrences, repos, sha8, type, value}`; sweep metadata: distinct_secrets=46, total_hits=144, patterns=8. Distinct confirmed: 46/46.
- **Tree shape:** each extracted tree holds exactly 1 file — the inner base APK extracted from its XAPK container (expected staging shape, not an anomaly).
- **jwt_triage_v2.tsv:** 1,145 rows; lane-55 has a 12-row G-09 gap to complete from this file; datahub token (sha8 `f5cc101f`) must NOT be re-burned.

## Dedupe plan (union of both secrets inventories)

- Key: **per-entry sha256 of canonical JSON line** (`jq -c '.[]' | sort -u`).
- cowork distinct = 500; github distinct = 46; **cross-copy overlap = 0** → **union = 546 distinct**.
- Plan: enumerate union keyed on per-entry content-hash so identical entries across the two copies are counted (and later probed) exactly once; carry each entry's existing `sha8` field for fingerprint references. No double-counting occurs.

## Result

**PART (b): PASS.** All seven staged artifacts present and hashed; distinct counts exact (500 + 46, overlap 0, union 546). No fail-closed artifact-absence receipt required.

*Leak-gate: counts and hashes only; no credential values, tokens, or PII in this receipt.*
