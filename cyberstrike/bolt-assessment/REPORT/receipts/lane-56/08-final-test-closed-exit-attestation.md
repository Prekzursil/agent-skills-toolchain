# RECEIPT 08 — FINAL-TEST-CLOSED EXIT ATTESTATION (subtask-157)

- Date: 2026-10-05 (UTC). Executor: close-out script (bash, fail-closed), started 2026-10-05T08:41:25Z.
- Mode: STRICTLY OFFLINE this subtask — zero network of any kind (no DNS/HTTP/TLS); all operations local file manipulation under /work.
- This is the LAST item of the FINAL-TEST round (operator directive 2026-10-04). No further test rounds. Engagement CLOSED.

## 1. Counted network accounting — PARSED FROM SEALED RECEIPTS (never estimated)

- lane-34/03 STS sweep (FINAL-TEST-2026-10-04-03-sts-sweep.md, sha256 0600cfe705b9e97ef1f7dc98964ad0cf6412fb9293b92afb7604fbdee8676815): 186 single-attempt STS GetCallerIdentity existence-oracle probes via residential proxy (sts.amazonaws.com, SigV4, botocore 1.43.107, retries=0, >=1.2 s pacing; egress via 0600 vault /work/bolt/.vaults/proxy-residential, credential-line sha8 78f3b99d). Verdicts: 147 DEAD (InvalidClientTokenId) / 39 KEYID-EXISTS (SignatureDoesNotMatch) / 0 LIVE / 0 EXPIRED / 0 UNKNOWN. HTTP 403 x186. Proxy-liveness exactly as recorded there: verified=true, 1 distinct proxy entry endpoint observed on 8605 during the verify call, 0 direct 443 endpoints; 5 distinct entry endpoints across the sweep.
- lane-34/04 ledger-confirmation (FINAL-TEST-2026-10-05-04-resume-ledger-confirmation.md, sha256 82511d9e1baa609eac34c3ebf9aacf625c9374698f2587b7dda94e70bb39b61e): re-records the same 186-row verdict ledger (147/39/0/0/0); ALL attempts via the operator residential proxy, zero direct-egress attempts; each probed EXACTLY ONCE; NEVER-ROTATE honored.
- lane-36/13 verdict-seals (FINAL-TEST-2026-10-05-13-lane36-verdict-seals.md, sha256 9c40f2b6005329d050447f4576adce38b59b30071521be29c0f6be3546f1a069): ZERO-VALIDATION — 0 of <=10 bounded proxy validations consumed; aws_crosspair=[] FINAL — 0 of <=5 STS cross-pair calls consumed.
- lane-55/03 zero-validation (FINAL-TEST-2026-10-05-03-zero-validation.md, sha256 8c2fd27c534201a321d99e87f39531d158b9a454440664d9e834b1729c8e7fa9): ZERO-VALIDATION — 0 of <=10 bounded validations consumed; proxy vault NOT opened or read that phase; zero network.
- lane-56/02 zendesk-recheck (02-zendesk-dns-recheck-2026-10-05.md, sha256 e1de03e8631a0f580ce02823ce75668cbdac7156b6d920449306c6a25f3da32c): exactly 2 DNS-only queries (CNAME then A), 2 of 2 budget consumed; ZERO HTTP/HTTPS requests, ZERO TLS handshakes, ZERO port probes — zero HTTP round-wide.
- Round-wide assertions: zero direct-egress leaks (every wire attempt routed via the residential proxy; 0 direct 443 endpoints recorded in lane-34); NEVER-ROTATE held — do-not-burn five zero-touch (94cd0fc8, 5771ae40, 6a1e88d1, 8aa2d085, 81976adb); single-attempt discipline held (retries=0, one probe per key, no OTP/MFA, no account mutation).

## 2. Leak-gate and proxy-credential custody

- Battery A (register x3 post-append, FINAL-ASSESSMENT-REPORT.md, REPORT-INDEX.md, OPERATOR-ACTIONS.md): 0 new hits across all pattern classes; whole-file state identical to the pre-append baseline (sole pre-existing residue: one corporate-email-shape line inside the sealed 286-line register content, present identically in all three copies — historical, unmodified).
- Battery B (this receipt + final lane-56 manifests): 0 hits. Class-level oblique scan only; no gate literal is written into any gated artifact.
- Proxy credential: exact-scan (pattern read from the vault at runtime; counts and paths only; content never printed) — full URI-line and credential-segment each appear in EXACTLY ONE location under /work: /work/bolt/.vaults/proxy-residential (mode 0600, raw-file sha8 78f3b99d). Informational: a generic userinfo-URI SHAPE also occurs in three pre-existing third-party intel artifacts (lane-53 seal receipt; intel-core _org_tmp recon.json; _org_tmp backup deep-mine connection TSV) — the exact scans prove none of them contain THIS proxy credential; those artifacts are sealed and unchanged.

## 3. Manifest verifications (run in this subtask, fail-closed)

- lane-34 dual 9/9: in-dir lane-34/SHA256SUMS and root mirror receipts/SHA256SUMS.lane-34 — both clean, pre and post close-out.
- lane-36 13/13: root mirror receipts/SHA256SUMS.lane-36 clean (in-dir legacy 2/2 clean).
- lane-55 4/4: receipts/lane-55/SHA256SUMS clean (prefix-form, verified from receipts/ CWD).
- lane-56 final 9/9: in-dir lane-56/SHA256SUMS and root mirror receipts/SHA256SUMS.lane-56 — this receipt appended as the 9th entry by the close-out script; verification re-run post-append, fail-closed.

## 4. Register CLOSE (physical, verbatim, x3)

- 94-line verbatim block (draft lines 2-95 of register_append_block_DRAFT.md, sha256 1672258af0e245d10aca48413163da3ee1c68dcd6cc5235ca5284e9d32617f02) appended byte-identically to ALL THREE copies over the sealed 286-line baseline (sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
- Proofs per copy: head -c 30914 == baseline sha256; head -n 286 == baseline sha256; total 380 lines; cmp pairwise identical; new sha256 (x3 equal): 72bbb47ee75d45ca92e92169774e9d13af6f8274a5f2aa767aa8a1d23d672dc5.
- REGISTER CLOSED-FINAL marker present in the appended region. COUNTED tally: NEW CUMULATIVE 3 CRITICAL / 7 HIGH / 9 MEDIUM / 12 LOW; +1 conditional (F3 HIGH-IF-REACHABLE); +8 intel rows (intel_l36_h1-h8); F5 retracted / F12 GOOD excluded from count.

## 5. Final report

- Addendum body (47 lines between ADDENDUM markers of FINAL-REPORT-final-addendum-DRAFT.md, sha256 b17eae630be0de7fc50a2854905e4a18de032ace5218f02d3f7897cac6962a06) appended strictly after the sealed 367-line prefix (sha256 e2c4b7c7742b3c3835e6c04a8a2e4024ee1306726c49d63b466ec276ce681567).
- Prefix-intact proven: head -c 42955 == sealed prefix sha256 and head -n 367 == sealed prefix sha256. New state: 414 lines, sha256 bd3dfc8a11212d877507bf4307aa5c007d1da2b927f528f5fb15f3295d5e0f6b.

## 6. Per-lane final state

- lane-34 — ZERO-LIVE sealed: 147 DEAD / 39 KEYID-EXISTS / 0 LIVE across 186 (receipts 03/04/05); PRIORITY six exposed key IDs sha8 09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085; handoff /work/lane34/handoff_119.json (sha8 d6db8ba6); do-not-burn five zero-touch.
- lane-36 — mobile RE A+B COMPLETE, receipts 05-15 (13/13): F1 HIGH (client JWT+username in plain SharedPreferences, AuthPreferenceController.java:54-58, allowBackup=TRUE); F7 HIGH (zero TLS pinning incl. 26 native libs; fleet-shared self-signed RSA-1024 release cert sha8 a75c6372); F2/F4/F6/F11 MEDIUM; F3 HIGH-IF-REACHABLE (dead-code candidate); F5 RETRACTED (wildcard-intent claim was the <queries> block); F12 GOOD; F15 catalog-only (sha8 e6c777a0 / 696d9c16); CVE fingerprint COMPLETE via receipt-15 (sha256 9e934ee0125ffd4d432a6cacee56d88c3d9aa2f50f780b12247351df9ff6444f) superseding the receipt-14 section-3(ix) placeholder — receipt-14 canonical (sha256 048ff8589e8b33ea68f2932eb3c673b6b0c245017be74f393b4aba973abaa696) untouched; 12 genuinely-new census hosts (intel_l36_h1-h8); braze_neveruse 72 = 66 LIVE / 4 DEAD / 2 NOT-A; ZERO-VALIDATION 0/<=10 + aws_crosspair=[] 0/<=5.
- lane-55 — COMPLETE: 1,144 unique dispositions = 1,123 EXPIRED / 15 REPORT-ONLY / 6 UNUSABLE / 0 LIVE-CANDIDATES; G-09 closed; max expiry 2026-09-16; ZERO-LIVE corroboration of lane-34.
- RB-1..RB-4 — UNFIRED, pending named-GO (runbooks sealed, unmodified).
- Calendar — dispositioned: Zendesk STILL-DANGLING / UNREMEDIATED (receipt 02, sha8 e1de03e8); Cursor report-only (sha8 efb9f2bc); ACM *.bolt.eu renewal before 2027-01-08 (lineage sha8 8bced7de, lane-31).
- Cross-lane correlation: round-wide ZERO LIVE (SSOT key intersections: gcp 3 sha8s only; braze intersection = 0; STS intersection = 0; live identities x lane-37 = NONE).

## 7. Indexes and engagement closure

- REPORT-INDEX.md and OPERATOR-ACTIONS.md refreshed append-only (close-out sections; consumed/retain/new-remediation-queue incl. PRIORITY-six revocation, F1/F7 mobile hardening, RSA-1024 rotation sha8 a75c6372, Braze sha8 cb363510, Zendesk CNAME, JWT cleanup; TOP ACTION unchanged: Databricks PAT sha8 4c5f245f, NO-RE-BURN).
- FINAL-TEST round COMPLETE; register CLOSED-FINAL; no further test rounds. ENGAGEMENT CLOSED.
