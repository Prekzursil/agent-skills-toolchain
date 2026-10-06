# Lane-56 Receipt 01 — Aggregate FINAL-TEST Round Verdicts (lanes 34 / 36 / 55 + cross-lane correlation)

- Date: 2026-10-05 (subtask-155, evaluation checkpoint — STRICTLY OFFLINE: zero wire calls from this subtask; Zendesk DNS recheck executed separately by the pentester, verdict embedded by reference to sealed receipt 02)
- Register state: DRAFTS ONLY — zero physical register appends in this subtask; register ×3 re-verified byte-identical (286 lines, sha256 98859339…) before and after every phase; no sealed artifact modified.
- Identifier policy: all identifiers sha8-only; zero PII values; zero token/secret values.

## 1. Lane-34 — AWS STS existence-oracle sweep: ZERO-LIVE (FINAL, by reference)

- Union corpus 546 entries / 187 key-ID entries / 0 complete pairs; 186 key IDs probed exactly once (single-attempt `GetCallerIdentity` at fixed `https://sts.amazonaws.com`, retries off, residential-proxy egress only): 147 DEAD / 39 KEYID-EXISTS / 0 LIVE / 0 EXPIRED / 0 transport errors; PRIORITY six sha8s 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085.
- Exposure class: 39 live-record AWS access key IDs are publicly exposed (identifiers without secrets) — HIGH exposure class.
- Evidence by manifest entry: sts-sweep 0600cfe7 (lane-34 in-dir SHA256SUMS line 7 / mirror line 4), resume-ledger-confirmation 82511d9e (line 8 / line 5), zero-live-closure 24d21b4f (line 9 / line 6 — appended this subtask). Data: sts_verdicts.tsv (186 rows, recounted 147+39), sts_ledger.json 0a0f2b07.
- Limitations by reference: `InvalidClientTokenId` cannot distinguish nonexistent vs disabled keys (147 DEAD may include disabled keys); directive-count discrepancy as recorded in 82511d9e.
- Exclusion-honored: do-not-burn five 94cd0fc8 / 5771ae40 / 6a1e88d1 (DEAD) and 8aa2d085 / 81976adb (EXPIRED) zero-touch; zero re-probes.

## 2. Lane-36 — Mobile static RE, stage A (baseline/census/secrets triage) + stage B (deep static findings)

Stage A (sealed): baseline 21 artifacts (8ed49658); endpoint census 272 rows (39 NEW / 115 CHANGED / 6 KNOWN); shared self-signed RSA-1024 release cert (a75c6372, "Play Frosting" stamp); NO TLS pinning; secrets triage 130 entries with ZERO Bolt-owned credentials; `aws_crosspair=[]` CONFIRMED; braze_neveruse empty.

Stage B verdicts (manifest 13/13; inventory lane36_final_inventory.md 70c785f2):

- F1 HIGH — client JWT + username in plain SharedPreferences (AuthPreferenceController.java:54-58); allowBackup=TRUE.
- F7 HIGH — zero TLS pinning in Java layer + all 26 native libraries; user-CA MITM viable; chains with shared self-signed RSA-1024 release cert (a75c6372) fleet-wide.
- F3 HIGH-IF-REACHABLE (conditional) — VerificationWebView file/universal-access flags; dead-code candidate; counted in its own conditional class, NOT summed into unconditional HIGH.
- F2 MEDIUM — exported CrossAppLoginService; caller-signature allowlist mitigation present.
- F4 MEDIUM — PlainWebView without allowlist.
- F6 MEDIUM — boltprelive:// pre-production scheme live in production build.
- F11 MEDIUM — root/tamper detection present only as dead code.
- F5 RETRACTED (transparency note, no severity) — stage-A driver wildcard-intent-filter claim was a `<queries>` manifest block, not an exported surface; lane-36 receipt-09 superseded; retraction recorded transparently in register wording.
- F12 GOOD (positive control, not counted) — driver EncryptedSharedPreferences; allowBackup=FALSE.
- F15 LOW — two Mixpanel tokens (e6c777a0, 696d9c16) catalog-only.
- Shared self-signed RSA-1024 release cert (a75c6372) fleet-wide — MEDIUM (C-36).
- ZERO-VALIDATION: 0 of ≤10 bounded validations + `aws_crosspair=[]` FINAL via 0 of ≤5 STS checks (lane-36 receipt-13).
- CVE fingerprint COMPLETE (receipt-15 9e934ee0; supersedes receipt-14 §3(ix) placeholder; receipt-14 canonical unmodified at 048ff858): Netty 4.1.x — CVE-2021-21290, CVE-2021-21295, CVE-2021-21409, CVE-2021-37136, CVE-2021-37137, CVE-2023-34462, CVE-2023-44487; Okio — CVE-2023-3635; OkHttp — CVE-2021-0341; OpenSSL platform / Conscrypt-ASB governed. All report-only, version-gated.
- Census: 12 GENUINELY-NEW hosts recorded as 8 informational intel rows intel_l36_h1–h8 (admin-panel(.prelive).bolt.eu with HIGH-INTEREST paths /fleet/drivers/edit/%s, /identity/consumers/rider/%s/overview, /ride-hailing-order/orders/order/%s/%s; partners(.prelive).bolt.eu; signup.bolt.eu; s(.prelive).bolt.eu; prelive.bolt.eu; images.bolt.eu; scooters.taxify.eu; driver(.live).boltsvc.net / partnerdriver.live.boltsvc.net).
- braze_neveruse authoritative 72 = 66 LIVE / 4 DEAD / 2 NOT-A.
- Anomalies closed: 25-endpoint auth map reference-missing-FINAL with F18 Retrofit-annotation substitution (driver `@POST`/`@GET` endpoint set applied); xapk_meta false anomaly.

## 3. Lane-55 — JWT triage completion (manifest 4/4; artifacts matrix d028330a, summary d7a92b55, drift 29ac271e, g09_closure 70f23915)

- 1,144 unique rows, all dispositioned: 1,123 EXPIRED / 15 REPORT-ONLY / 6 UNUSABLE / 0 LIVE-CANDIDATES (sum = 1,144); max exp 2026-09-16 < run-date 2026-10-05.
- ZERO-validation receipt-03 (8c2fd27c): 0 of ≤10 bounded validations consumed.
- Lane-32 G-09 12-row gap CLOSED (receipt-02 fa2d6f52).
- Drift vs 2026-10-01: 5 LIVE→EXPIRED (LSS-64291, LSS-72037, MVRT-2215, PAWT-128, TAXP-4393) + 7 sha8 supersessions to REPORT-ONLY (+1 note-refresh).
- NO-RE-BURN zero-touch: f5cc101f (datahub), 4c5f245f / 2e1ce409 (Databricks PATs).
- PII incident from stage 1 remediated at source; final gate 0 hits (receipt-04 40b67177).

## 4. Cross-lane correlation (substitution sources: lane-31 ATTACK-SURFACE-INVENTORY d37edc22 + DELTA-TABLE cc3b1e43)

- Mobile endpoints × lane-31/35/47 register rows: cross-checked via the lane-31 inventory + delta substitution sources; the F18 Retrofit driver-endpoint set was applied in place of the reference-missing 25-endpoint auth map; no unregistered live endpoint family beyond intel rows intel_l36_h1–h8.
- Found keys ∩ CREDS-SSOT = 3 prior-coverage gcp sha8s ONLY (d540704a, 6fa2307a, bb75e81d) — no new Bolt-owned credentials.
- Found keys ∩ braze72 authoritative set = 0.
- Found keys ∩ 186-key-ID STS corpus (lane-34) = 0.
- LIVE identities × lane-37 asset-graph = NONE.

## 5. Round-level ZERO-LIVE statement

Zero live credentials surfaced anywhere in the FINAL-TEST round: lane-34 0 LIVE (0 of 186 probed key IDs), lane-55 0 LIVE-CANDIDATES (0 of 1,144 rows), lane-36 0 Bolt-owned keys (aws_crosspair=[] FINAL). The only credential-class exposure carried forward is the 39 live-record AWS key IDs (identifiers without secrets — HIGH exposure class) plus the operator-side NO-RE-BURN set (f5cc101f, 4c5f245f, 2e1ce409).

## 6. Egress discipline — every wire attempt of the round

- Lane-34: 186 STS existence-oracle probes via operator residential proxy (vault 0600; credential sha8 78f3b99d; zero direct egress).
- Lane-36: ZERO validations (0 of ≤10); ZERO STS.
- Lane-55: ZERO validations (0 of ≤10); ZERO STS.
- Lane-56: exactly 2 DNS-only queries for the Zendesk recheck via direct system resolver per lane-39 baseline lineage (documented exception; proxy governs HTTP-level attempts only); ZERO HTTP/TLS/port probes anywhere in the round.
- NEVER-ROTATE held throughout; no account-state mutation; no OTP/MFA; no token refresh.

## Integrity attestations

- Register ×3 verified before AND after every phase of this subtask: byte-identical, 286 lines, sha256 98859339… — no drift.
- Sealed artifacts untouched: lane-34 receipts 8 pre-existing entries byte-preserved (only manifest append + new file); lane-36 13/13; lane-55 4/4; lane-56 pre-existing 2 entries untouched.
- FINAL-ASSESSMENT-REPORT.md hashed before and after drafting (receipt 05 carries both values); never written.
- Leak-gate: institutional battery over all new artifacts — see receipt 07 (patterns described obliquely there).
