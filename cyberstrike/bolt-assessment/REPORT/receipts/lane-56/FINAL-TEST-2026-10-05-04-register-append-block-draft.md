# Lane-56 Receipt 04 — Register Append Block DRAFT (verbatim-final text for subtask-156)

- Date: 2026-10-05 (subtask-155, evaluation checkpoint). Status: DRAFT — ZERO physical register appends performed in this subtask.
- Source of truth: /work/lane56/drafts/register_append_block_DRAFT.md — sha256 1672258af0e245d10aca48413163da3ee1c68dcd6cc5235ca5284e9d32617f02 — mode 0600 — 96 lines.
- Extraction contract (subtask-156): append the text BETWEEN the VERBATIM-APPEND-BLOCK-START and VERBATIM-APPEND-BLOCK-END markers, byte-identical, to ALL THREE register copies (/work/bolt/REPORT/LANE-REGISTER.md, /work/bolt-intel/LANE-REGISTER.md, /work/intel-core/LANE-REGISTER.md) over the verified 286-line baseline. The HTML marker lines themselves are NOT part of the appended block.
- Baseline proof at seal time: register x3 byte-identical, 286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17 (re-verified before and after every phase of this subtask).
- Severity tally counted from this exact text: 3 HIGH / 5 MEDIUM / 1 LOW additions (+1 conditional HIGH-IF-REACHABLE, +8 intel rows; F5 RETRACTED and F12 GOOD not counted) — see receipt 03.
- Embedded verbatim copy follows (byte-identical to the source-of-truth file; sha256 above).

<!-- VERBATIM-APPEND-BLOCK-START
     Extraction contract (subtask-156): take the text BETWEEN this marker and the
     matching END marker and append byte-identical to ALL THREE register copies
     (/work/bolt/REPORT/LANE-REGISTER.md, /work/bolt-intel/LANE-REGISTER.md,
     /work/intel-core/LANE-REGISTER.md) over the verified 286-line baseline
     (sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
     The HTML comment markers themselves are NOT part of the appended block.
     Sealed verbatim copy also embedded in lane-56 receipt 04. -->

---

## [2026-10-05] FINAL-TEST ROUND — CONSOLIDATED CLOSE-OUT (subtask-155 evaluation checkpoint; lane-56 receipts 01, 03–07)

### 1. Lane-34 — AWS STS existence-oracle sweep: ZERO-LIVE (FINAL)

- Union corpus 546 entries / 187 key-ID entries / 0 complete pairs.
- 186 key IDs probed exactly once: single-attempt `GetCallerIdentity` existence oracle, fixed endpoint `https://sts.amazonaws.com`, retries off, egress exclusively via operator residential proxy (vault 0600; credential sha8 78f3b99d).
- Verdict: 147 DEAD (`InvalidClientTokenId`) / 39 KEYID-EXISTS (`SignatureDoesNotMatch`) / 0 LIVE / 0 EXPIRED / 0 transport errors.
- PRIORITY six KEYID-EXISTS sha8s: 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085.
- Exposure class: 39 live-record AWS access key IDs are publicly exposed (identifiers without secrets) — HIGH exposure class; revocation/remediation list in FINAL-REPORT addendum.
- Evidence by manifest entry (lane-34 in-dir SHA256SUMS lines 7–9 / prefixed mirror receipts/SHA256SUMS.lane-34): sts-sweep sha256 0600cfe7…, resume-ledger-confirmation sha256 82511d9e…, zero-live-closure sha256 24d21b4f….
- Limitations (by reference): (i) `InvalidClientTokenId` cannot distinguish nonexistent vs disabled keys — the 147 DEAD set may include disabled keys; (ii) directive-count discrepancy as recorded in the ledger-confirmation receipt.
- Exclusion-honored: do-not-burn five sha8s 94cd0fc8 / 5771ae40 / 6a1e88d1 (DEAD) and 8aa2d085 / 81976adb (EXPIRED) dispositioned from prior evidence only — zero re-probes, zero touch; single-attempt + NO-RE-BURN held.

### 2. Lane-36 — Mobile static RE (client + driver, jadx, offline): findings and counted severities

| ID  | Finding | Severity |
|-----|---------|----------|
| K-34 | 39 live-record AWS access key IDs publicly exposed (identifiers without secrets) — exposure class carried from lane-34 | HIGH |
| F1  | client JWT + username stored in plain SharedPreferences (AuthPreferenceController.java:54-58); allowBackup=TRUE | HIGH |
| F7  | zero TLS pinning in Java layer and across all 26 native libraries; user-CA MITM viable; chains with shared self-signed RSA-1024 release cert (sha8 a75c6372) fleet-wide | HIGH |
| F3  | VerificationWebView file/universal-access flags enabled; dead-code candidate — conditional on reachability | HIGH-IF-REACHABLE |
| F2  | exported CrossAppLoginService; caller-signature allowlist mitigation present | MEDIUM |
| F4  | PlainWebView used without allowlist | MEDIUM |
| F6  | boltprelive:// pre-production scheme live in production build | MEDIUM |
| F11 | root/tamper detection present only as dead code | MEDIUM |
| C-36 | shared self-signed RSA-1024 release certificate (sha8 a75c6372) used fleet-wide | MEDIUM |
| F15 | two Mixpanel tokens (sha8 e6c777a0, 696d9c16) — catalog-only | LOW |
| F5  | RETRACTED: stage-A driver wildcard-intent-filter claim was a `<queries>` manifest block, not an exported surface; receipt-09 superseded | RETRACTED |
| F12 | driver EncryptedSharedPreferences; allowBackup=FALSE — positive control | GOOD |

- F5 retraction transparency note: the stage-A claim is withdrawn with corrected evidence recorded in-receipt (lane-36 receipt-09 superseded); no severity assigned; kept so the register's claim history remains auditable.
- ZERO-VALIDATION (lane-36 receipt-13): 0 of ≤10 bounded credential validations; `aws_crosspair=[]` FINAL via 0 of ≤5 STS checks.
- CVE fingerprint COMPLETE (lane-36 receipt-15 sha8 9e934ee0; supersedes receipt-14 §3(ix) placeholder — receipt-14 canonical text unmodified at sha8 048ff858): Netty 4.1.x — CVE-2021-21290, CVE-2021-21295, CVE-2021-21409, CVE-2021-37136, CVE-2021-37137, CVE-2023-34462, CVE-2023-44487; Okio — CVE-2023-3635; OkHttp — CVE-2021-0341; OpenSSL platform / Conscrypt-ASB governed. All report-only, version-gated — no exploitable instance demonstrated in scope.
- Census GENUINELY-NEW hosts — 8 informational intel rows (intel_l36_h1–h8, counted as intel, separate from vulnerability severity), covering 12 hosts: intel_l36_h1 admin-panel.bolt.eu + admin-panel.prelive.bolt.eu (HIGH-INTEREST paths /fleet/drivers/edit/%s, /identity/consumers/rider/%s/overview, /ride-hailing-order/orders/order/%s/%s); intel_l36_h2 partners.bolt.eu + partners.prelive.bolt.eu; intel_l36_h3 signup.bolt.eu; intel_l36_h4 s.bolt.eu + s.prelive.bolt.eu; intel_l36_h5 prelive.bolt.eu; intel_l36_h6 images.bolt.eu; intel_l36_h7 scooters.taxify.eu; intel_l36_h8 driver.live.boltsvc.net + partnerdriver.live.boltsvc.net.
- braze_neveruse authoritative 72 = 66 LIVE / 4 DEAD / 2 NOT-A.
- Anomalies closed: 25-endpoint auth map reference-missing-FINAL with F18 Retrofit-annotation substitution applied; xapk_meta false anomaly.

### 3. Lane-55 — JWT triage completion; explicit ZERO-LIVE corroboration of lane-34

- 1,144 unique rows, all dispositioned: 1,123 EXPIRED / 15 REPORT-ONLY / 6 UNUSABLE / 0 LIVE-CANDIDATES (sum = 1,144).
- ZERO-validation (lane-55 receipt-03 sha8 8c2fd27c): 0 of ≤10 bounded validations consumed.
- Lane-32 G-09 12-row gap CLOSED (lane-55 receipt-02 sha8 fa2d6f52).
- Drift vs 2026-10-01: 5 LIVE→EXPIRED; 7 sha8 supersessions to REPORT-ONLY (+1 note-refresh, no class change).
- NO-RE-BURN zero-touch: f5cc101f (datahub), 4c5f245f / 2e1ce409 (Databricks PATs).
- CORROBORATION: lane-55 ZERO LIVE-CANDIDATES independently corroborates lane-34 ZERO-LIVE — zero live credentials surfaced anywhere in the FINAL-TEST round (lane-34 0 LIVE, lane-55 0 LIVE-CANDIDATES, lane-36 0 Bolt-owned keys).

### 4. Egress discipline — every wire attempt of the round

- Lane-34: 186 STS existence-oracle probes via operator residential proxy (zero direct egress; retries off).
- Lane-36: ZERO validations (0 of ≤10); ZERO STS calls.
- Lane-55: ZERO validations (0 of ≤10); ZERO STS calls.
- Lane-56: Zendesk recheck = exactly 2 DNS-only queries via direct system resolver per lane-39 baseline lineage (documented exception — proxy governs HTTP-level attempts only); ZERO HTTP/TLS/port probes anywhere in the round.
- NEVER-ROTATE held throughout; no account-state mutation; no OTP/MFA; no token refresh.

### 5. Zendesk dangling-CNAME — STILL-DANGLING, UNREMEDIATED (verdict 2026-10-05 07:38 UTC)

- `testsupport.bolt.eu. 300 IN CNAME d3v-taxify.zendesk.com.`
- `d3v-taxify.zendesk.com. 1800 IN A 216.198.53.2, 216.198.54.2` (Zendesk edge 216.198.0.0/16).
- bolt.eu zone still publishes the byte-identical CNAME to the deleted legacy Taxify dev Zendesk target (baseline SSOT wave-9 / lane-39 receipt sha8 1420af19: claimable, quarantine-blocked, first-signup-wins PoC-proven).
- DNS alone cannot distinguish unclaimed-claimable vs third-party-claimed-active-tenant (baseline discriminator was an HTTP-layer provider 404 — out of scope under the zero-HTTP mandate); both states remain exposure.
- Quarantine expired ~2026-09-20 → ≥15-day claim-exposed gap as of run date.
- Remediation (verbatim-ready): remove or re-point the CNAME and confirm address disposition with the SaaS provider.
- Evidence: lane-56 receipt-02 (sha256 e1de03e8631a0f580ce02823ce75668cbdac7156b6d920449306c6a25f3da32c) — exactly 2 DNS queries, 11 s pacing, ZERO HTTP.

### 6. Counted severity tally (counted mechanically from this block's finding table; enumeration in lane-56 receipt-03)

- Counted additions in this block: 3 HIGH + 5 MEDIUM + 1 LOW; 1 conditional (HIGH-IF-REACHABLE — own conditional class, NOT summed into HIGH); 8 informational intel rows (intel_l36_h1–h8); F5 RETRACTED and F12 GOOD present but NOT counted.
- Arithmetic: baseline 3 CRITICAL / 4 HIGH / 4 MEDIUM / 11 LOW + additions 0 CRITICAL / 3 HIGH / 5 MEDIUM / 1 LOW = **3 CRITICAL / 7 HIGH / 9 MEDIUM / 12 LOW**, plus 1 conditional class and 8 intel rows.

### 7. Remediation pointers

- Revoke/remediate the 39 exposed AWS key IDs — PRIORITY six first (09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085).
- F1 mobile fix: migrate client JWT + username out of plain SharedPreferences; set allowBackup=FALSE.
- F7 mobile fix: implement certificate pinning (Java + all 26 native libraries); replace shared self-signed RSA-1024 release cert (a75c6372).
- Secondary mobile: F6 remove boltprelive:// from production; F2 harden exported CrossAppLoginService; F4 PlainWebView allowlist; F11 wire root/tamper detection.
- Braze cb363510 exposure review.
- JWT cleanup list: 1,123 EXPIRED + 15 REPORT-ONLY + 6 UNUSABLE rows (lane-55 disposition matrix).
- Databricks PAT sha8 4c5f245f remains TOP ACTION (NO-RE-BURN — operator-side revocation only).
- Zendesk: remove or re-point the CNAME and confirm address disposition with the SaaS provider; keep ACM *.bolt.eu renewal action before 2027-01-08.

### 8. REGISTER CLOSED-FINAL

- No further test rounds. Physical ×3 byte-identical append of this block over the 286-line baseline (sha256 98859339…) is executed in subtask-156; FINAL-TEST-CLOSED exit attestation to follow.

<!-- VERBATIM-APPEND-BLOCK-END -->
