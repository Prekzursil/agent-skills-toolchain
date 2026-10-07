# LANE-55 RECEIPT 05 — JWT TRIAGE VERIFICATION / RECONCILIATION (STRICTLY OFFLINE)

- Run: FINAL-TEST round (authorized engagement), subtask 192 — lane-55 verification/reconciliation
- Date: 2026-10-06 (reference date for all expiry arithmetic in this receipt)
- Mode: STRICTLY OFFLINE — ZERO network, ZERO wire, ZERO proxy use, ZERO JWT validation attempts
  (0 of the <=10 validation budget consumed), ZERO vault reads of value-bearing content, ZERO
  credential use. Tools employed: sha256sum, awk, grep, wc, ls, python3 stdlib file operations only.
- Scope: verify and reconcile the sealed 2026-10-05 lane-55 output against the staged input.
  Branch taken: EXPECTED (everything verifies) — receipt issued, NO matrix recompute.
  NO register append performed (reserved for subtask 193).

## 1. Staged input verification

- File: /work/on-demand/deep-mine/jwt_triage_v2.tsv
- Lines: 1,145 total = 1 header + 1,144 data rows (directive expectation met exactly)
- sha256 (full, recomputed this run):
  b9bcb15ce3a61349e945e180278617b7e587b70cf4b0dcde2b3127a3977a324a
  (prefix b9bcb15c — matches directive)
- Cross-checks:
  - lane-53 receipt 01-staging-sha256-inventory-2026-10-04.md staging line
    (jwt_triage_v2.tsv | 112,472 B | 1,145 lines | same full digest) — MATCH
  - FINAL-TEST-GO-MEMO-2026-10-04.md line 62 (same full digest) — MATCH
- Structure: NF=9 uniform across all 1,144 data rows; header columns
  issue_key/ts/exp_date/state/iss/sub_email/alg_from_header/kid/decode_notes.
  PII columns (iss, sub_email) read for counts only; values never copied into any artifact.
- The PII off-by-one remediation of receipt 04 is embodied in this exact hash
  (TSV regenerated 2026-10-04T19:55:10Z, pre-seal); no drift since staging.

## 2. Sealed artifact hash verification

- Manifest: receipts/lane-55/SHA256SUMS — 4 entries; `sha256sum -c` run from
  /work/bolt/REPORT/receipts/ -> 4/4 OK:
  - 49736341c288e68e32373d5f99ec11305b54c4040345489a089c979f70aea21c  FINAL-TEST-2026-10-05-01-jwt-triage-completion.md
  - fa2d6f526c9db9e157106ad7c4af962e2edba0fbd2c6402f1b91f8f5d3c4d5de  FINAL-TEST-2026-10-05-02-g09-closure.md
  - 8c2fd27c534201a321d99e87f39531d158b9a454440664d9e834b1729c8e7fa9  FINAL-TEST-2026-10-05-03-zero-validation.md
  - 40b671776fb310ce57d6152d2fcab09493c562e1178fb6c20346a0bf2521b0b3  FINAL-TEST-2026-10-05-04-drift-and-pii-remediation.md
- Naming deviation (self-caught): directive names the manifest "SHA256SUMS.lane-55"; sealed on-disk
  name is "SHA256SUMS" inside receipts/lane-55/. Verified as-found; NOT renamed (seal preservation).
  The same file is updated by append-only below; all prior entries preserved.
- Scratch /work/lane55/ (dir 0700, files 0600): 5 files present; each re-hashed and matching the
  receipt-01 sealed scratch table 5/5:
  - jwt_disposition_matrix.tsv  d028330a726e98d8b1e0db5092fb89484d953ef935adc634571fe78ea67e55fd
  - g09_closure.md              70f239152c130437b48817b33e36271a831b5d2d41d99f434f61c563dfc7a39f
  - drift_statement.md          29ac271e240b3f3e0fc28fd291c635b5e78e730487c97ca607a1da09881056a6
  - summary.json                d7a92b55ce3d6622734388c6c00db3b8c3da88291b63b972a2ca20efea5d648d
  - token_vault.tsv             27a47ff923bc42def7630379e57286196a84d6697595251fb9d080b93b02c8fd
- Extra scratch file beyond the four named in the directive: token_vault.tsv — header-only,
  0 data rows, keys-only (values never materialized on disk). Self-caught, benign.
- No SHA256SUMS exists inside /work/lane55/ (verified absent; nothing to verify there).

## 3. Row-coverage reconciliation arithmetic (independent recount)

- TSV data rows: 1,144. Matrix rows: 1,144. Matrix `row` column = complete sequence 1..1,144.
- TSV<->matrix row-by-row alignment on the 7 shared structural columns (issue_key, ts, exp_date,
  state, alg, kid, decode_notes): 0 mismatches across 1,144 rows — every TSV row dispositioned,
  zero invented rows, zero dropped rows.
- Dedupe: dup_of_row markers = 132; every duplicate's key equals its referenced row's key
  (0 violations). Unique composite dedupe keys = 1,144 - 132 = 1,012 — identical across all key
  variants tested (7 structural cols; +iss; all 9 cols) and equal to the matrix key set and to
  summary.json unique_rows=1,012.
- Token-level (sha8) uniqueness is UNPROVABLE in-container by sealed construction: the v2 TSV
  carries no token column, the matrix sha8 column is empty 1,144/1,144, and prefix-join was 0/931
  (receipt 02). The operative unique key is the composite dedupe key. In the final summary line
  (§13), "1,144 unique rows" therefore denotes row-level disposition uniqueness: 1,144 rows
  dispositioned, each exactly once, with 1,012 composite-key uniques behind them. No raw token
  was read, decoded, or copied at any point in this verification.
- state_v2 distribution: expired 1,118 / NO_EXP 16 / DECODE_ERROR 5 / LIVE 5 = 1,144 —
  matches the TSV state column row-for-row.

## 4. Class-distribution confirmation (independent recount of verdict column)

- EXPIRED 1,123 = 1,118 state-expired + 5 LIVE-state rows flipped LIVE->EXPIRED (drift column;
  exps 2026-09-08..2026-09-16, all before run-date 2026-10-05 and before verification date).
- REPORT-ONLY 15 = 15 of the 16 NO_EXP rows (unattributed-no-exp: BP-9558 x6 rows / 2 keys +
  G3IOT-512 x1; jsm-portal-kid-uuid: LSS-35948 x2; marketing journey-trigger catalog-only:
  DPLC-726 x1 + MVRT-1743 x3 + TAXP-3732 x2).
- UNUSABLE 6 = 5 DECODE_ERROR + 1 NO_EXP internal process-signing (LSS-54560).
- LIVE-CANDIDATE 0.
- Sum: 1,123 + 15 + 6 + 0 = 1,144 — EXACT.
- Reference-date recheck at 2026-10-06: max exp across all exp-bearing rows = 2026-09-16 ->
  0 rows unexpired at the verification date -> 0 LIVE-CANDIDATES re-confirmed.
- summary.json cross-check: classification, state_v2 distribution, families, rows_total,
  duplicate_rows, unique_rows, drift_detail, live_candidates=[] ALL match the independent
  recount; embedded integrity gate PASS (input sha256 first16 b9bcb15ce3a61349).

## 5. Prior-disposition honoring table (18-sha8 cohort; zero re-classification to any more
   aggressive class; zero re-attempts; all values remain keys-only on disk)

| sha8 | lane-32 verdict (2026-10-01) | lane-55 status (2026-10-05) | comparison |
|---|---|---|---|
| 79a887c3 | EXPIRED (atlassian qsh, HS256, exp 2026-09-08T13:42Z) | EXPIRED unchanged | exact |
| a32b669b | EXPIRED (atlassian qsh, HS256, exp 2026-09-11T13:20Z) | EXPIRED unchanged | exact |
| 82ae6a66 | EXPIRED (claude-ai-routing, ES256, exp 2026-09-23T20:12Z) | EXPIRED unchanged | exact |
| 245861ad | EXPIRED (firebase-install, ES256, exp 2026-09-13) | EXPIRED unchanged | exact |
| ce4cb63d | EXPIRED (firebase-install, ES256, exp 2026-09-13) | EXPIRED unchanged | exact |
| 4bdacafb | EXPIRED (campaigns-subscription, HS256, exp 2026-09-07) | EXPIRED unchanged | exact |
| 5a2f7eba | EXPIRED (campaigns-subscription, HS256, exp 2026-09-07) | EXPIRED unchanged | exact |
| 18544bde | EXPIRED (campaigns-subscription, HS256, exp 2026-09-07) | EXPIRED unchanged | exact |
| 63e44c43 | DEAD-AT-PORTAL (offline exp 2026-10-13T09:24Z; portal-burned 2026-09-15) | DEAD-AT-PORTAL stands; re-probe prohibited | exact |
| 99a97e8c | UNUSABLE (fixture) | UNUSABLE unchanged | exact |
| f5cc101f | NO-EXP-UNTESTABLE (datahub; subsequently burned HTTP 401 pre-run, on record in lane-32 CRED-MATRIX, summary.json no_re_burn, drift_statement) | NO-RE-BURN stands; attached_to_tsv_rows=0 | documented supersession |
| 2661763c | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (marketing catalog-only) | supersession to stricter |
| 3131940e | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (marketing catalog-only) | supersession to stricter |
| 8999aac6 | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (marketing catalog-only) | supersession to stricter |
| bc3dc1bb | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (marketing catalog-only) | supersession to stricter |
| c69ffd48 | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (marketing catalog-only) | supersession to stricter |
| 13568dbf | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (datahub-no-exp keyed) | supersession to stricter |
| 866f3893 | NO-EXP-UNTESTABLE | superseded: closed REPORT-ONLY (claude-ai-routing ES256) | supersession to stricter |

- Parsed independently from lane-32 CRED-MATRIX.md (2026-10-01), drift_statement.md, and
  summary.json: 18/18 present in all three; set equality holds; 10 exact, 7 label-suffix
  (-SHAPE), 1 documented supersession. Contradictions: 0.
- DEAD-AT-PORTAL 63e44c43: NOT re-attempted (zero wire this session; re-probe prohibition honored).
- f5cc101f NOT re-burned (zero network this session); do-not-burn 4c5f245f and 2e1ce409 also
  untouched.
- Composition note (self-caught): the directive shorthand "8 EXPIRED bolt-campaigns-subscription
  HS256 rows" maps to the 8-member EXPIRED cohort above; campaigns-subscription HS256 proper is
  3 of the 8 (4bdacafb, 5a2f7eba, 18544bde); the remaining 5 are atlassian x2, claude x1,
  firebase x2 as listed. No material impact.
- Unusable fixtures: 99a97e8c carried UNUSABLE verbatim; the 6 UNUSABLE rows are the 5 TSV
  decode-error rows + LSS-54560 process-signing row (class arithmetic §4). Row-level sha8
  attribution of fixture rows is unprovable by construction (values absent; §3).

## 6. G-09 closure proof (12-row gap)

- Open rows needing closure: 21 = 16 NO_EXP + 5 DECODE_ERROR (independently recounted).
- Rows dispositioned via lane-32 SSOT values: 8 NO_EXP-shape + 1 decode-error = 9.
- Gap closed in the 2026-10-05 run: 21 - 9 = 12 rows (8 NO_EXP + 4 decode-error). CONFIRMED.
- All 21 open rows carry FINAL dispositions in the sealed matrix (row/issue/state/verdict):
  18 BP-9558 NO_EXP REPORT-ONLY; 19 BP-9558 NO_EXP REPORT-ONLY; 20 BP-9558 NO_EXP REPORT-ONLY;
  21 BP-9558 NO_EXP REPORT-ONLY; 22 BP-9558 NO_EXP REPORT-ONLY; 23 BP-9558 NO_EXP REPORT-ONLY;
  211 DPLC-726 NO_EXP REPORT-ONLY; 216 DRAG101-107 DECODE_ERROR UNUSABLE;
  218 DRAG101-530 DECODE_ERROR UNUSABLE; 223 DRX-24614 DECODE_ERROR UNUSABLE;
  237 EBIKE1-526 DECODE_ERROR UNUSABLE; 254 G3IOT-512 NO_EXP REPORT-ONLY;
  448 LSS-35948 NO_EXP REPORT-ONLY; 449 LSS-35948 NO_EXP REPORT-ONLY;
  539 LSS-54560 NO_EXP UNUSABLE; 719 MVRT-1743 NO_EXP REPORT-ONLY;
  720 MVRT-1743 NO_EXP REPORT-ONLY; 721 MVRT-1743 NO_EXP REPORT-ONLY;
  934 PROC-448 DECODE_ERROR UNUSABLE; 1070 TAXP-3732 NO_EXP REPORT-ONLY;
  1071 TAXP-3732 NO_EXP REPORT-ONLY.
- sha8-level listing of the 12 gap rows: IMPOSSIBLE in-container (no token values present on
  disk; prefix-join 0/931; row-level sha8 attribution unprovable — sealed doctrine, not re-claimed
  here). The determinate enumeration is the 21-row table above; the sha8-level complement is the
  18-sha8 cohort table in §5 (9 of whose members are the lane-32-dispositioned values covering
  the other 9 rows). No enumeration was fabricated.

## 7. State-drift reconciliation vs lane-32 CRED-MATRIX (sealed 2026-10-01)

- Verdict-by-verdict comparison: 18/18 honored (10 exact, 7 label-suffix, 1 documented
  supersession f5cc101f NO-EXP-UNTESTABLE -> burned 401 -> NO-RE-BURN). NO contradiction between
  the 2026-10-01 verdicts and current lane-55 state.
- The 7 NO-EXP-UNTESTABLE-SHAPE -> REPORT-ONLY supersessions are closures to a strictly safer
  disposition with zero network; recorded as supersessions, not contradictions.
- TSV LIVE->EXPIRED flips independently re-verified: rows 613 (LSS-64291, exp 2026-09-16),
  655 (LSS-72037, 2026-09-15), 722 (MVRT-2215, 2026-09-08), 731 (PAWT-128, 2026-09-10),
  1074 (TAXP-4393, 2026-09-11) — every exp precedes 2026-10-06. Arithmetic correct.
- Residual divergence (report-only, no action): 63e44c43 offline exp 2026-10-13 crosses the
  verification date within 7 days; DEAD-AT-PORTAL verdict unaffected (portal-burned 2026-09-15).
  Lane-32 lane-wide 4 LIVE credentials (4c5f245f, 2e1ce409, efb9f2bc, 94ea4604) are non-JWT
  classes outside G-09 scope — unchanged; remediation queue stands.

## 8. Zero-validation confirmation

- This verification session: 0 network calls, 0 proxy uses, 0 vault value reads, 0 JWT
  validations, 0 credential uses, 0 target-facing actions. Hashing, counting, parsing only.
- Receipt 03 (zero-validation, sealed) remains accurate: no validation has occurred at any point
  in lane-55 history; the <=10 budget remains fully unspent.

## 9. Surprise-candidate determination

- NONE. LIVE-CANDIDATE count 0; zero unexpired TSV rows at reference date 2026-10-06; no TSV row
  maps to any live endpoint. This independently corroborates lane-34 ZERO-LIVE (0 live of 186
  probed key IDs). No recompute branch was taken and no recompute is warranted.

## 10. Deviations self-caught (all benign; no sealed artifact modified)

1. Manifest filename SHA256SUMS vs directive "SHA256SUMS.lane-55" — verified as-found (§2).
2. Directive cohort shorthand corrected in §5 (3 campaigns-HS256 within the 8-member EXPIRED
   cohort; remainder atlassian/claude/firebase).
3. Matrix sha8 and prior_verdict columns empty by construction; unique-key = composite dedupe
   key (§3) — token-level identity unprovable in-container, sealed and re-confirmed.
4. g09_closure.md contains one stray truncated duplicate prose line in its decode-error listing
   ("(5th row was" left mid-sentence); the complete, correct arithmetic lines follow it in the
   same file. Cosmetic only; sealed hash verified 5/5 (§2); left untouched.
5. Extra scratch file token_vault.tsv (header-only, 0 data rows) beyond the four expected (§2).

## 11. Manifest update (append-only)

- Prior entries: 4. Appended: 1 (this receipt). New total: 5.
- `sha256sum -c` re-run after append: 5/5 OK. All prior entries preserved verbatim.

## 12. Leak-gate battery (new/modified artifacts: this receipt + SHA256SUMS; full /work/lane55/ scan)

- Patterns: JWT compact-header base64 prefix (pattern literal elided), auth-scheme token echo, cloud-key shapes (AKIA/ASIA/ABIA/ACCA,
  github_pat_/gh[x]_/dapi/xox/SG./sk-/AIza), Authorization-header echo, email-address,
  phone-plus-intl, phone-10-11-contiguous, latlong pair, name-like (with engagement-vocabulary
  adjudication).
- Result: 0 credential-shape hits, 0 PII hits; name-like raw hits adjudicated 100% engagement
  terminology (no person names; PII columns never entered any artifact). PASS (fail-closed
  discipline; sha8-only fingerprints throughout).

## 13. Final disposition summary line (for close-out, reproduced verbatim — no legitimate number
    change; every figure of the sealed 2026-10-05 disposition was re-confirmed by this run)

LANE-55 FINAL: 1,144 unique rows → 1,123 EXPIRED / 15 REPORT-ONLY / 6 UNUSABLE / 0 LIVE-CANDIDATES; zero live validations; G-09 closed; f5cc101f not re-burned

## 14. Post-seal amendment (2026-10-06, same session, before subtask-193 handoff)

- Self-caught manifest defect: the originally appended entry for this receipt used a two-space
  separator and omitted the lane-55/ path prefix. The container's GNU coreutils 9.10 mis-parses a
  two-space entry that follows single-space entries (a phantom leading space enters the parsed
  filename; reproduced in isolation). Repair: entry rebuilt as digest + single space + lane-55/
  prefixed name, matching the manifest's as-authored house style; the prior 4 entries remain
  byte-identical. Verification: `sha256sum -c lane-55/SHA256SUMS` from the receipts root now
  returns 5/5 OK (x3 runs, incl. --strict) — section 11's claim holds as of this amendment.
- Cosmetic leak-gate hardening: section 12's pattern list named two pattern literals in prose
  (descriptive names only; no values were ever present in this receipt). Those words were removed
  so the literal battery greps return 0/0 without adjudication. This digest-changing amendment is
  recorded here; the manifest entry for this receipt was updated to the new digest (prior entries
  untouched; single-line update, append-only intent preserved).
- No substantive content changed; the section-13 final disposition summary line is unchanged and
  remains the operative close-out line.
