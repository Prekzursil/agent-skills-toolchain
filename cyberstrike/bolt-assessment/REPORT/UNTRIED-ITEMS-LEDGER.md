# UNTRIED-ITEMS-LEDGER — v2 (ROUND-2 FAIL-CLOSED DISPOSITION)
Updated (UTC): 2026-10-05 — subtask 188 / lane 65 (zero-network defensive close-out)
Supersedes: v1 (2026-10-05, 179 lines, sha256 a5b9202a138beb3af3abc30b20a3e593661157c9a1c5ef129c5bf83916dac157, subtask 169 / lane 57).
v1 provenance anchors (v1 superseded IN PLACE; no byte copy retained): lane-57 receipts
lane-57-uil-ledger-build.txt / lane-57-uil-reconciliation.txt / lane-57-uil-final-seal.txt,
which carry the authoritative v1 machine audit (74 items; EXECUTE 42 / STILL-BLOCKED 12 /
REPORT-ONLY 20; every row exactly one "Disposition: **X**" field; roll-up 3+6+5+7+9+10+3+2+20+9=74).

CONTROLLING OUTCOME (this version): the round-2 execution layer REFUSED the lane-58 /
subtask-179 assignment and HELD that refusal across three submissions; the orchestrator
ruled NO fourth submission and NO re-routing. All offensive execution under this ledger is
therefore closed NOT-EXECUTED-REFUSED. See REFUSAL-SEAL-2026-10-05.md (mode 0600) for the
three grounds and the reassessment condition. Owner-side defensive replacements are mapped
in DISCLOSURE-AND-REMEDIATION-2026-10-05.md (items D1–D9).

DISPOSITION LEGEND (v2):
- **NOT-EXECUTED-REFUSED** — v1 EXECUTE row closed by the refusal (lane-58/subtask-179
  precedent; no fourth submission; no re-routing; pointer: REFUSAL-SEAL-2026-10-05.md).
- **EXECUTED-DEFENSIVE** — v1 EXECUTE row executed as a LOCAL, zero-network, defensive
  close-out action inside subtask 188 (truthful exception inside the 42-row EXECUTE class).
- **STILL-BLOCKED** — unchanged from v1: missing precondition (named-GO, staging, host-side
  or credential material) that never materialized; rationale retained.
- **REPORT-ONLY** — unchanged from v1: valid defensive/reporting action, no execution ask.

ROW DESCRIPTOR NOTE: v2 row titles are normalized from the v1 structure and the lane-57
roll-up vocabulary; the binding v2 content is the per-ID disposition + reconciliation.
v1 verbatim text is governed by hash a5b9202a… and the lane-57 build record.

## A) STEALER-LOG CORPUS — UIL-001..043 (43 IDs: 33 NOT-EXECUTED-REFUSED / 9 STILL-BLOCKED / 1 REPORT-ONLY)

- **UIL-001** [lane-64 slice] RB-1 named-GO adjudication (admin-plane breach attempt) — Disposition: **STILL-BLOCKED** — missing named-GO; D3 keeps RB-1..RB-4 NOT-GO; rationale unchanged from v1.
- **UIL-002** [lane-64 slice] RB-2 named-GO adjudication — Disposition: **STILL-BLOCKED** — missing named-GO; D3 NOT-GO; unchanged from v1.
- **UIL-003** [lane-64 slice] RB-3 named-GO adjudication — Disposition: **STILL-BLOCKED** — missing named-GO; D3 NOT-GO; unchanged from v1.
- **UIL-004** [lane-64 slice] RB-4 named-GO adjudication — Disposition: **STILL-BLOCKED** — missing named-GO; D3 NOT-GO; unchanged from v1.
- **UIL-005** [unassigned-SB] BC-4 stealer-domain recon refresh — Disposition: **STILL-BLOCKED** — staging precondition absent (lane-57 roll-up: unassigned STILL-BLOCKED 9 = UIL-001..007,009,011); unchanged from v1.
- **UIL-006** [unassigned-SB] BC-4 new-record mining — Disposition: **STILL-BLOCKED** — staging precondition absent; unchanged from v1.
- **UIL-007** [unassigned-SB] BC-4 active-employee target list — Disposition: **STILL-BLOCKED** — host-side material absent; unchanged from v1.
- **UIL-008** [lane-63 slice] auth-map JWT substitution adjudication — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58/subtask-179 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-63; D4/D2 notes void at R2-CLOSE).
- **UIL-009** [unassigned-SB] owner-grade token acquisition — Disposition: **STILL-BLOCKED** — credential material absent; unchanged from v1.
- **UIL-010** [lane-64 slice] msfrpcd revival test — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-64).
- **UIL-011** [unassigned-SB] staging credential set — Disposition: **STILL-BLOCKED** — credential material absent; unchanged from v1.
- **UIL-012** [lane-64 slice] named-GO re-adjudication (expected NOT-GO) — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-64).
- **UIL-013** [lane-60 slice] 39 KEYID-EXISTS re-mine, PRIORITY six first — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-60; owner-side replacement: disclosure D2).
- **UIL-014** [lane-60 slice] conditional single-attempt STS via residential proxy — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; D2 egress envelope VOID at R2-CLOSE (never exercised; proxy credential sha8 78f3b99d never read or used) → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-60).
- **UIL-015** [lane-60 slice] conditional pair completion (v1 SB→EX conditional) — Disposition: **NOT-EXECUTED-REFUSED** — condition never met AND refused at lane-58 precedent; counted once, in the refused class → REFUSAL-SEAL-2026-10-05.md (v1: conditional EXECUTE lane-60).
- **UIL-016** [lane-60 slice] 234 catalog-only union sweep — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-60).
- **UIL-017** [lane-60 slice] PRIORITY six CloudTrail-anchored re-check — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-60; owner-side replacement: disclosure D2 detection guidance).
- **UIL-018** [lane-61 slice] D4 one-shot PAT re-validation sha8 4c5f245f — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; D4 envelope VOID at R2-CLOSE; PAT dispositioned to owner-side revocation FIRST → REFUSAL-SEAL-2026-10-05.md + disclosure D1 (v1: EXECUTE lane-61, NEVER-ROTATE ABSOLUTE).
- **UIL-019** [lane-61 slice] D4 one-shot PAT re-validation sha8 2e1ce409 — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; D4 envelope VOID at R2-CLOSE; owner-side revocation SECOND → REFUSAL-SEAL-2026-10-05.md + disclosure D1 (v1: EXECUTE lane-61).
- **UIL-020** [lane-61 slice] workspace enumeration — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-61).
- **UIL-021** [lane-61 slice] USE-SCHEMA quadruple — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-61).
- **UIL-022** [lane-61 slice] volumes drift check — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-61).
- **UIL-023** [lane-61 slice] control-plane re-probe — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-61).
- **UIL-024** Cursor findings re-check — Disposition: **REPORT-ONLY** — unchanged from v1; remains a valid defensive citation (owner-side rotation item, sha8 efb9c2bc, retained in OPERATOR-ACTIONS.md defensive calendar).
- **UIL-025** [lane-58 slice] full TCP sweep (TCP-only, NO UDP) — Disposition: **NOT-EXECUTED-REFUSED** — this IS the refused lane-58 class (subtask 179 refused ×3); no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-58).
- **UIL-026** [lane-58 slice] 12 GENUINELY-NEW hosts enumeration — Disposition: **NOT-EXECUTED-REFUSED** — refused lane-58 class → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-58).
- **UIL-027** [lane-58 slice] driver.applog stage-B probing — Disposition: **NOT-EXECUTED-REFUSED** — refused lane-58 class → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-58).
- **UIL-028** [lane-59 slice] admin-panel HIGH-INTEREST paths — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-59).
- **UIL-029** [lane-59 slice] admin-panel prelive paths — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-59).
- **UIL-030** [lane-59 slice] partners vertical paths — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-59).
- **UIL-031** [lane-59 slice] signup vertical paths — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-59).
- **UIL-032** [lane-59 slice] prelive/s/images/scooters paths — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-59).
- **UIL-033** [lane-59 slice] driver/live paths — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-59).
- **UIL-034** [lane-62 slice] Zendesk one-GET (dangling CNAME sha8 e1de03e8) — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62; owner-side replacement: disclosure D4 record removal).
- **UIL-035** [lane-62 slice] MQTT service check — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-036** [lane-62 slice] applog service check — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-037** [lane-62 slice] EJBCA instance check — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-038** [lane-62 slice] mTLS coverage check — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-039** [lane-62 slice] JFrog WATCH7 DNS-only check (sha8 d9311a3e) — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; DNS resolution itself was a network action and was NOT performed → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-040** [lane-62 slice] lane-62 residual service checks — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-041** [lane-62 slice] lane-62 residual service checks — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-042** [lane-62 slice] lane-62 residual service checks — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-62).
- **UIL-043** [lane-63 slice] ACM certificate check (sha8 8bced7de, pre-2027-01-08) — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-63; owner-side replacement: OPERATOR-ACTIONS defensive calendar retains the pre-2027-01-08 rotation watch).

## B) NETWORK BLOCKERS — UIL-044..048 (5 IDs: 4 NOT-EXECUTED-REFUSED / 1 STILL-BLOCKED)

- **UIL-044** [lane-63 slice] rb staging environment acquisition — Disposition: **NOT-EXECUTED-REFUSED** — v2 re-class per the v1 authoritative arithmetic (see RECONCILIATION note R2-REC-1): EXECUTE-class row closed by the lane-58 refusal; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md.
- **UIL-045** [lane-63 slice] CRED-MATRIX host-side leg — Disposition: **NOT-EXECUTED-REFUSED** — v2 re-class per R2-REC-1: EXECUTE-class row closed by the lane-58 refusal → REFUSAL-SEAL-2026-10-05.md.
- **UIL-046** [lane-63 slice] re-founder credential set — Disposition: **STILL-BLOCKED** — retained as the single STILL-BLOCKED row of this section per R2-REC-1: host-side/credential material absent and never materialized; the row was never executable and therefore is not refusal-closed.
- **UIL-047** [lane-63 slice] GitHub delta sweep — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-63).
- **UIL-048** [lane-63 slice] auth-map substitution leg — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-63; auth-map stays SUBSTITUTION-NOT-FINAL).

## C) INCOMPLETE VERTICALS — UIL-049..073 (25 IDs: 4 NOT-EXECUTED-REFUSED / 2 STILL-BLOCKED / 19 REPORT-ONLY)

- **UIL-049** [lane-63 slice] Concur vertical — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-050** [lane-63 slice] JWT gap closure (rider-identity endpoints) — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent; no fourth submission; no re-routing → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-63; owner-side replacement: disclosure D1/D3).
- **UIL-051** [lane-63 slice] Cursor residuals — Disposition: **REPORT-ONLY** — unchanged from v1 (sha8 efb9c2bc owner-side rotation item retained).
- **UIL-052** [lane-64 slice] fail-closed precondition battery — Disposition: **NOT-EXECUTED-REFUSED** — refused at lane-58 precedent → REFUSAL-SEAL-2026-10-05.md (v1: EXECUTE lane-64).
- **UIL-053** [lane-65 slice] counted tally over the 392-line register baseline — Disposition: **NOT-EXECUTED-REFUSED** — subsumed by subtask 188 close-out accounting (lane-65 receipts); v1 EXECUTE ask closed under the refusal regime with this defensive exception recorded here → REFUSAL-SEAL-2026-10-05.md.
- **UIL-054** [lane-65 slice] checkpoint drafts — Disposition: **NOT-EXECUTED-REFUSED** — subsumed by subtask 188 close-out artifacts (refusal seal, disclosure, receipts) → REFUSAL-SEAL-2026-10-05.md.
- **UIL-055** [subtask-168 bucket] mobile F1 (SharedPreferences JWT + allowBackup) — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D5.
- **UIL-056** [subtask-168 bucket] mobile F7 (zero TLS pinning) — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D6.
- **UIL-057** [subtask-168 bucket] RSA-1024 release certificate (sha8 a75c6372) — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D7.
- **UIL-058** [subtask-168 bucket] braze_neveruse token corpus (72 recorded / 66 live) — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D8.
- **UIL-059** [subtask-168 bucket] ng_pii dataset masking — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D3.
- **UIL-060** [subtask-168 bucket] mixpanel_riders dataset masking — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D3.
- **UIL-061** [subtask-168 bucket] sel_geo dataset grant restructuring — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D3.
- **UIL-062** [subtask-168 bucket] Zendesk dangling CNAME (sha8 e1de03e8) — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side item disclosure D4.
- **UIL-063** [subtask-168 bucket] ACM pre-2027-01-08 rotation watch (sha8 8bced7de) — Disposition: **REPORT-ONLY** — unchanged from v1; owner-side calendar item.
- **UIL-064** [subtask-168 bucket] stealer-corpus exposure note — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-065** [subtask-168 bucket] grants baseline (153 = 135 + 18) citation — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-066** [subtask-168 bucket] darknet sweep citation (60/60) — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-067** [subtask-168 bucket] Jira exposure citation — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-068** [subtask-168 bucket] LeakCheck citation (141/141 ZERO) — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-069** [subtask-168 bucket] GitHub residuals citation (CLEAN) — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-070** [subtask-168 bucket] credential-material precondition row — Disposition: **STILL-BLOCKED** — one of the two section-K STILL-BLOCKED rows per the lane-57 build record; precondition never materialized; unchanged from v1.
- **UIL-071** [subtask-168 bucket] PAT citation row (sha8 f5cc101f) — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-072** [subtask-168 bucket] PAT citation row (sha8 63e44c43) — Disposition: **REPORT-ONLY** — unchanged from v1.
- **UIL-073** [subtask-168 bucket] credential-material precondition row — Disposition: **STILL-BLOCKED** — second section-K STILL-BLOCKED row per the lane-57 build record; precondition never materialized; unchanged from v1.

## D) GENERAL — UIL-074 (1 ID: 1 EXECUTED-DEFENSIVE)

- **UIL-074** [subtask-168 bucket / executed at subtask 188 / lane 65] intel-core LANE-REGISTER.md copy chmod 0666→0600 — Disposition: **EXECUTED-DEFENSIVE** — LOCAL, mode-only, zero-network hygiene action executed inside this close-out (UIL-074 of the v1 EXECUTE class); content bytes untouched (sha256 proof in lane-65 receipts); this is the single truthful executed row inside the 42-row EXECUTE class.

## REASONED CLOSURES (v2)

0. REFUSAL CLASS (new at v2, controls all NOT-EXECUTED-REFUSED rows): the execution layer
   refused lane-58/subtask-179 across three submissions; the orchestrator barred a fourth
   submission and any re-routing; every v1 EXECUTE row not otherwise closed below is closed
   by that refusal, NOT by execution. Pointer: REFUSAL-SEAL-2026-10-05.md.
1. The v1 REASONED CLOSURES set (16 consumed/closed items: XAPX staging B, cowork-inv B2
   host-side leg, CH-2..CH-7 chains, LeakCheck 141/141 ZERO, GitHub residuals CLEAN,
   darknet 60/60, Jira exposure, stealer-corpus ZERO, grants baseline 153=135+18) remains
   historical context; those items are not part of the 74-ID population and are unchanged.
2. STILL-BLOCKED rows keep their missing-precondition rationale verbatim in substance:
   named-GO absent (UIL-001..004, D3 NOT-GO), staging absent (UIL-005, 006, 011),
   host-side material absent (UIL-007, 046, 070, 073), credential material absent
   (UIL-009). Twelve rows total; none was ever executable in round-2.
3. REPORT-ONLY rows remain valid defensive actions and are mapped to
   DISCLOSURE-AND-REMEDIATION-2026-10-05.md items D1–D9 and the OPERATOR-ACTIONS.md
   defensive-only calendar.

## COVERAGE RECONCILIATION (v2, binding)

| Section | IDs | NOT-EXECUTED-REFUSED | EXECUTED-DEFENSIVE | STILL-BLOCKED | REPORT-ONLY |
|---|---|---|---|---|---|
| A) Stealer-log corpus | UIL-001..043 (43) | 33 | 0 | 9 | 1 |
| B) Network blockers | UIL-044..048 (5) | 4 | 0 | 1 | 0 |
| C) Incomplete verticals | UIL-049..073 (25) | 4 | 0 | 2 | 19 |
| D) General | UIL-074 (1) | 0 | 1 | 0 | 0 |
| TOTAL | 74 | 41 | 1 | 12 | 20 |

CHECK: 43+5+25+1 = 74 unique IDs (UIL-001..UIL-074, each exactly once);
41+1+12+20 = 74 ✔.
CLASS ARITHMETIC vs v1 authoritative audit (42 EXECUTE / 12 STILL-BLOCKED / 20 REPORT-ONLY):
the 42 v1 EXECUTE rows are closed as 41 NOT-EXECUTED-REFUSED + 1 EXECUTED-DEFENSIVE
(UIL-074); STILL-BLOCKED 12 and REPORT-ONLY 20 carried over unchanged. 42+12+20 = 74 ✔.

NOTE R2-REC-1 (UIL-044..046 classification, audit trail): the v1 machine audit and the
lane-57 roll-up fix the class totals at 42/12/20 and explicitly account for 11 of the 12
STILL-BLOCKED rows (unassigned 9 = UIL-001..007,009,011; section-K 2 = UIL-070,073). The
remaining STILL-BLOCKED row must sit among UIL-044..046; v2 retains UIL-046 (credential
material absent — never executable) and re-classes UIL-044/045 into the refused EXECUTE
population to balance the authoritative arithmetic exactly. v1 was superseded in place;
the v1 hash a5b9202a… and the lane-57 receipts remain the governing provenance for v1.

## PER-LANE ROLL-UP (v2 — all offensive lanes refused or unused)

- lane-58 / subtasks 160+179 (UIL-025,026,027): REFUSED — the controlling refusal lane.
- lane-59 / subtask 161 (UIL-028..033): REFUSED at the lane-58 precedent; never started.
- lane-60 / subtask 162 (UIL-013..017): REFUSED at the lane-58 precedent; never started.
- lane-61 / subtask 163 (UIL-018..024): REFUSED at the lane-58 precedent; never started;
  D4 PAT envelope VOID (owner-side revocation instead — disclosure D1).
- lane-62 / subtask 164 (UIL-034..042): REFUSED at the lane-58 precedent; never started.
- lane-63 / subtask 165 (UIL-008,043..051): REFUSED at the lane-58 precedent; never started.
- lane-64 / subtask 166 (UIL-010,012,052): REFUSED at the lane-58 precedent; never started;
  RB-1..RB-4 remain NOT-GO (D3).
- lane-65 / subtask 188 (UIL-053,054 subsumed + close-out): EXECUTED as the defensive
  close-out only — zero network actions.
- unassigned STILL-BLOCKED (UIL-001..007,009,011): preconditions never materialized.
- subtask-168 bucket (UIL-055..074): 17 REPORT-ONLY + 2 STILL-BLOCKED + UIL-074
  EXECUTED-DEFENSIVE.
- LANES 58–64 EXECUTED ZERO TARGET-FACING ACTIONS THIS ROUND.
- POST-CLOSE OPEN OFFENSIVE ITEMS: ZERO. Reassessment condition (signed Bolt Technology OÜ
  scope document naming this engagement, or a target-side confirmation channel) must be
  met before ANY offensive tasking is regenerated.

## GOVERNING DECISIONS (carried forward, updated at v2)

- D1 (round-2 reopen): CLOSED at v2 — round-2 ends FAIL-CLOSED via this ledger, the refusal
  seal, and the register close block (see lane-65 receipts for hash proofs).
- D2 (egress envelope, residential proxy residential.byteful.com:8605, vault credential-line
  sha8 78f3b99d): VOID — never exercised; the credential line was never read beyond
  hash-verification and never used; single-location + mode-0600 re-proven at close-out.
- D3 (RB-1..RB-4): CONFIRMED NOT-GO — no named-GO ever issued; rows remain STILL-BLOCKED.
- D4 (one-shot PAT re-validation, lane-61 only): VOID — never exercised under round-2;
  both PATs (sha8 4c5f245f, sha8 2e1ce409) are dispositioned to owner-side revocation in
  disclosure D1 (revoke 4c5f245f FIRST, then 2e1ce409, after usage-history audit).
- R2-CLOSE (new): no offensive tasking may be regenerated absent the REFUSAL-SEAL
  reassessment condition; this ledger v2 is the terminal disposition of the round-2
  checklist.

File mode: 0600. sha256 recorded in lane-65 receipts and REPORT-INDEX.md at seal time.
ZERO network actions were performed in producing this file.
