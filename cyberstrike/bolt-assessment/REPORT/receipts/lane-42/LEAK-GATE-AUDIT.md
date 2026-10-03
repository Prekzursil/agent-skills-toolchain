# LANE-42 STEP 3 — FINAL LEAK-GATE AUDIT RECEIPT

Date: 2026-10-02 | Scope: LOCAL-FILESYSTEM-ONLY, ZERO network calls | Harness: /work/lane42/leakgate.py
Auditor: lane-42 closing agent | Register state at audit: 3 copies, 235 lines, sha256 a3a12a55e17c00d3… (byte-identical, cmp OK ×2)

## A. Audit set (10 files)

| # | Artifact | Result |
|---|----------|--------|
| 1 | /work/bolt/REPORT/FINAL-ASSESSMENT-REPORT.md (331 lines, sha8 a7298c16) | 0 true hits |
| 2 | receipts/lane-42/STAGING-RECHECK.md (sha8 2c00a07a) | 0 hits |
| 3 | receipts/lane-42/CREDS-DRIFT-RECON.md (sha8 6a525764) | 0 hits |
| 4 | receipts/lane-42/REGISTER-APPEND.md (sha8 a010a23b) | 0 hits |
| 5 | receipts/lane-42/REGISTER-COPIES.sha256 | 0 hits (checksum list) |
| 6 | receipts/lane-42/FINAL-REPORT-SEAL.md (sha8 e375701a) | 1 candidate → false positive (B.1) |
| 7 | receipts/lane-42/SHA256SUMS.lane-42 | 0 hits (checksum list) |
| 8 | /work/bolt/REPORT/LANE-REGISTER.md | 1 candidate → pre-sealed, outside append (B.2) |
| 9 | /work/bolt-intel/LANE-REGISTER.md | 1 candidate → identical pre-sealed line (B.2) |
| 10 | /work/intel-core/LANE-REGISTER.md | 1 candidate → identical pre-sealed line (B.2) |

## B. Battery descriptions and candidate-hit triage

**Battery 1 — credential shapes** (regex classes; patterns described, raw shapes NOT spelled in this receipt):
JWT-header base64 segment; Bearer-token echo; AWS access-key classes AKIA/ASIA/ABIA/ACCA
fixed-prefix + 16-char class; GitHub fine-grained and app-token prefix classes; Databricks
`dapi`-prefix class; Slack xox-prefix class; SendGrid three-segment class; OpenAI sk-prefix
class; Google API-key prefix class; Authorization-header echoes.
**Battery 2 — PII values**: email-address values; international and 10/11-contiguous phone
shapes (hex-run-exempt to avoid sha256 false positives); lat/lng coordinate pairs at real
precision (≥4 decimals both components); exact row-value samples (none present — artifacts
cite counts and sha8 fingerprints only).
**Battery 3 — generic secret blobs** adjacent to key-like labels (≥32 mixed-class chars,
pure-hex exempt): 0 hits across all 10 files.
**Battery 4 — fingerprint discipline**: full 64-hex token count in sha8-mandated artifacts.

Candidate hits (4 total) — triage:

1. **FINAL-REPORT-SEAL.md:24, JWT-header class** — FALSE POSITIVE. The match is the
   battery's own *descriptive enumeration* of scanned shape-families in the STEP-2
   construction-check line (slash-delimited pattern-name list). No token material.
2. **Register line 31 (all 3 copies identical), email-value class** — PRE-EXISTING SEALED
   CONTENT. Line 31 lies in the lane-39-sealed block (182-line prefix re-sealed at
   4c67fec5 by lane-40). The lane-42 append occupies lines 183–235 only. The value is a
   third-party legacy personal address already dispositioned at its sealing lane
   (inactive-since-2018 capture, report-only rule). **Sealed-artifact no-mutation rule
   honored: NOT altered.** Carried observation for owner-side editorial decision only.
3./4. Same line in the bolt-intel and intel-core copies — byte-identity of all three copies
   confirmed (cmp OK ×2); identical disposition as B.2.

**Independent append-block scan (register lines 183–235, all batteries): 0 hits.**

**Battery 4 result — full 64-hex tokens:** registers 0/0/0; report 2, both dispositioned
ALLOWED-INTEGRITY-SEAL class (not credential/PII fingerprints): line 8 = sealed register
hash a3a12a55e17c00d31255c3349bd178265fced34c4f348f54a85edc0250ef9866; line 200 =
byte-exact exfil-payload match sha256 e1cb4be09a9102cac6df1df802018adf729a41ca86aea23995cd2c6e1a5208ed
(composite-CRITICAL evidence seal). Every credential/PII reference across report +
registers + receipts is sha8-only or path-only. PASS.

## C. STS key-ID disposition (carried observation, formal acceptance)

receipts/lane-41/CH-1-EVIDENCE.md lines 25 and 35 embed an AWS error-XML echo
(`<AWSAccessKeyId>` inside S3 `SignatureDoesNotMatch` bodies; key-ID sha8 445bb452).
Disposition: **ACCEPTED — identifier-only.** (i) AWS access-key IDs are not secrets
without the secret-access-key component, which the team never possessed — the
SignatureDoesNotMatch errors themselves prove no valid signing material existed;
(ii) the identifier is a temporary STS session key-ID, expired by definition post-TTL;
(iii) zero secret material adjacent (the StringToSign element is the canonical request,
not a secret); (iv) lane-41 is a SEALED artifact — integrity preserved, NOT mutated.
No action required beyond this recorded acceptance.

## D. Prior sealed-lane spot-verification (sha256sum -c re-runs, 2026-10-02)

| Sums file | Result | Notes |
|-----------|--------|-------|
| SHA256SUMS.lane-30 (from REPORT root) | **15 OK / 1 superseded / 0 missing** | phase0/OPERATOR-ACTIONS.md mismatch = SANCTIONED: dated "Subtask-75 refresh 2026-10-01T22:15Z" section appended in-file post-seal; content inspected; not tampering |
| SHA256SUMS.lane-32 | **10/10 OK** | — |
| SHA256SUMS.lane-34 | **3/3 OK** | — |
| SHA256SUMS.lane-36 | **1/1 OK** | — |
| lane-38/SHA256SUMS.lane-38 | **5/5 OK** | — |
| lane-39/SHA256SUMS.lane-39 | **9/9 OK** | — |
| lane-40/SHA256SUMS.lane-40 | **9/9 OK non-register + 3 superseded** | The 3 register entries (frozen at 4c67fec5, 182 lines) superseded by the sanctioned lane-42 STEP-1 append; all three copies now byte-identical at a3a12a55… / 235 lines, re-sealed in receipts/lane-42/REGISTER-COPIES.sha256 |
| lane-41/SHA256SUMS.lane-41 | **10/10 OK** | — |
| lane-41/runbooks/SHA256SUMS | **5/5 OK** | DEVIATION NOTE: task expectation cited 6/6; the sealed sums file lists exactly 5 entries (README + RB-1..RB-4). All 5 verify OK; no 6th entry ever existed. |

**Total: 58 OK / 4 superseded-by-sanctioned-append / 0 tampering / 0 missing.**

## E. Register + permissions + dating

- Register copies: /work/bolt/REPORT, /work/bolt-intel, /work/intel-core — each 235 lines,
  sha256 a3a12a55e17c00d31255c3349bd178265fced34c4f348f54a85edc0250ef9866; cmp identical.
- Perms: FINAL-ASSESSMENT-REPORT.md and every receipts/lane-42/ artifact = **0600**.
- Dating: every lane-42 narrative receipt carries internal 2026-10-02 stamps (checksum-list
  files dated by companion receipts per workspace convention).

## F. VERDICT

**LEAK-GATE: GREEN.** True-positive hit count across all batteries and all 10 artifacts:
**0**. All candidate matches dispositioned (1 battery-description false positive; 3
pre-existing sealed content outside the lane-42 append, unmutated). Sealed prior lanes
unmodified except two documented sanctioned supersessions (subtask-75 OPERATOR-ACTIONS
refresh; lane-42 STEP-1 register append), both re-sealed under their successor receipts.
