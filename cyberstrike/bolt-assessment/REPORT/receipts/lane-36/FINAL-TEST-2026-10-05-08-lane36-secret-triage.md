# FINAL-TEST RECEIPT 08 — lane-36 Stage A: Secret-Catalog Triage (catalog-only, zero validation)

- Engagement: Bolt Technology OÜ red-team (operator directive 2026-10-04, verbatim authority on record)
- Round / subtask: FINAL-TEST / subtask-143 (lane-36 mobile RE, stage A, phase 2)
- Date: 2026-10-05
- Register impact: NONE (register close-out is subtask-147)
- OFFLINE ATTESTATION: catalog-only triage — ZERO validation attempts of any kind; no secret values were ever written to any output; every reference below is sha8-only. Full report: /work/lane36/analysis/secret_triage.md sha256 9998548a7071f4c58e1b8dcf403d724b7534022a9e31562be8708c94622a0673

## 1. Corpus
- secret_catalog.json (27,053 B) / secret_catalog.tsv (130 rows + header) — sealed in directory baseline SHA256SUMS (8ed49658f63d5172dd138b8bf5103a70aafeea4c3ab3e38d3f6aa202a466f02d).
- 130 entries (client 18 / driver 112) collapse to 22 DISTINCT sha8s.
- HEADLINE VERDICT: ZERO Bolt-owned real credentials embedded in either production app. Every TRUE match is a third-party, standard client-side integration key.

## 2. Per-family verdicts (sha8-only)
CLIENT (ee.mtakso.client CA.225.0):
- braze_uuid_key x1 — TRUE, sha8 cb363510 — source res/values/strings.xml line 255, key name 'braze_api_key' (Braze SDK public app identifier; client-side by design; path verified).
- gcp_apikey x5 — TRUE, 2 distinct sha8s: 6fa2307a (x2), d540704a (x3) — API-key-shaped Android/GCP client integrations.
- github_pat x11 — ALL FALSE, 3 distinct sha8s — hex/base64 fragments in dependency metadata; none match any classic GitHub token-prefix family.
- sentry_uuid_key x1 — sha8 bf2e62e3 — Sentry DSN/identifier-like, not a credential.

DRIVER (ee.mtakso.driver DA.147.0):
- gcp_apikey x4 — TRUE, 1 distinct sha8: bb75e81d — same class as client GCP keys.
- github_pat x104 — ALL FALSE, 11 distinct sha8s; dominant sha8 d680cca6 x93 = repeated token inside assets/sentry-external-modules.txt (dependency list); remainder are hex fragments/hashes/resource ids.
- pem_block x2 — sha8 3021d90e x2 — scanner verdict OVERRIDDEN to FALSE: the matches are the PUBLIC netty SslUtils.java lines 44-45 PROBING_CERT/PROBING_KEY constants (present only in driver classes5.dex; visible at strings_driver.txt lines 693573-693613). Zero private key material; block content NOT recorded anywhere.
- sentry_uuid_key x1 — sha8 93196d68 — identifier-like.
- uuid_generic_keyctx x1 — sha8 1d4cdc12 — identifier-like.

## 3. Cross-lane confirmations (read-only)
- aws_crosspair = [] CONFIRMED: grep -aE 'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}' over SIX corpora (jadx_client, jadx_driver, at_client, at_driver, strings_client.txt, strings_driver.txt; sealed catalog files excluded) -> 0 matches. PRIORITY six key-IDs (sha8 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085) ABSENT from lane-36. The 186-key-ID union is therefore UNCHANGED: 147 DEAD / 39 KEYID-EXISTS. Lane-36 AWS cross-pairing verdict: ZERO new pairs.
- do-not-burn sha8s 94cd0fc8 / 5771ae40 / 6a1e88d1 / 8aa2d085 / 81976adb: ABSENT from lane-36 corpora; never validated; untouched.
- braze_neveruse_matches = [] CONFIRMED: intersection of the 22 lane-36 catalog sha8s with the 72 key-lines of braze_neveruse_sha8.txt is EMPTY (no lane-36 secret appears in the never-use/rotation-quarantine set).

## 4. Anomaly — braze_neveruse count drift (documented read-only; file NOT modified)
- File braze_neveruse_sha8.txt (1,255 B) = 75 lines = 3 header lines + 72 key-lines.
- Header verdict-map sums to 68 live + 3 dead + 2 NOT-A-CREDENTIAL = 73 != 72 key-lines (internal off-by-one).
- Prior STATE recorded '66 keys'. Net drift +6 vs STATE and +/-1 internal.
- Disposition: reconcile in stage B against the /work/lane37 graphdb export; NO in-place fix (file is sealed in SHA256SUMS; read-only handling).

## 5. Closing attestations (subtask-143, 2026-10-05)
- Zero network; zero validation attempts (catalog-only); NEVER-ROTATE intact; proxy vault untouched except passive stat + line-hash check.
- sha8-only secret references; zero credential values; zero PII; zero proxy userinfo.
- Leak-gate over this receipts dir: PASS (0 hits: key-ID shapes, BEGIN-blocks, PAT prefixes, JWT prefixes, GCP-key prefixes, URL userinfo, email/phone shapes).
- LANE-REGISTER.md untouched (byte-identical x3, 286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
