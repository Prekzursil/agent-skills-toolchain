# RECEIPT 04 — LANE-55 DRIFT STATEMENT + STAGE-1 PII INCIDENT RECORD (REDACTED, SEALED)
FINAL-TEST 2026-10-05 · subtask-152 stage 2 seal · strictly offline · sha8-only · zero PII

## A. Drift vs 2026-10-01 verdicts

### A.1 TSV-row drift: 5 rows LIVE → EXPIRED (exp crossed run-date)
All five carry exp values 2026-09-08..2026-09-16; the TSV `state` column was computed at corpus
generation time (2026-09-03) while those exps were still in the future. No other TSV row changed
class. No network was used to re-check — arithmetic against run-date 2026-10-05 only.

| row | issue_key | exp_date | flip |
|---|---|---|---|
| 613 | LSS-64291 | 2026-09-16 | LIVE → EXPIRED |
| 655 | LSS-72037 | 2026-09-15 | LIVE → EXPIRED |
| 722 | MVRT-2215 | 2026-09-08 | LIVE → EXPIRED |
| 731 | PAWT-128 | 2026-09-10 | LIVE → EXPIRED |
| 1074 | TAXP-4393 | 2026-09-11 | LIVE → EXPIRED |

### A.2 Cohort sha8 supersessions (lane-32 → lane-55)
Seven sha8s formally superseded NO-EXP-UNTESTABLE-SHAPE → REPORT-ONLY on 2026-10-05:
`2661763c`, `3131940e`, `8999aac6`, `bc3dc1bb`, `c69ffd48` (marketing journey-trigger shapes —
victim-shaped, standing rule 8), `13568dbf` (internal DataHub issuer, HS256, secret not in
corpus, iat-only), `866f3893` (claude-ai-routing, iat-only).
Reconciliation of the directive's "7 listed + 1 = 8": the eighth position corresponds to
`63e44c43` (DEAD-AT-PORTAL), whose disposition NOTE was refreshed — offline exp 2026-10-13 is
now past the run-date horizon of reachability and re-probe remains prohibited — with NO class
change. No other cohort sha8 changed class (8 EXPIRED and 99a97e8c UNUSABLE carried verbatim;
f5cc101f / 4c5f245f / 2e1ce409 remain NO-RE-BURN).

### A.3 Global effect
EXPIRED 1,123 · REPORT-ONLY 15 · UNUSABLE 6 = 1,144 (sum equals data-row count; zero
unverifiable rows). Row-level residual gaps: NONE.

## B. Stage-1 PII incident record (detected, remediated, sealed)
- What happened: during the FIRST generation pass of the disposition matrix, the stage-1 parser
  read an adjacent column (subject-email claim column) as the issuer column due to a
  column-index off-by-one (issuer is column index 4; the parser consumed index 5). One
  subject-email claim value was consequently rendered into two artifacts (matrix + summary).
- Detection: post-generation self-audit leak-gate battery over the freshly written artifacts
  flagged an email-shaped string during stage-1 review, before any receipt sealing.
- Containment & fix (all applied in stage 1, before sealing):
  1. Source fix: column index corrected (iss = idx 4) and the subject-email column was dropped
     from emission entirely — no pass-through.
  2. Redaction-by-construction: an emit-time sanitizer now rewrites email-shaped strings and
     token-shaped strings to neutral placeholders for EVERY field written to disk.
  3. Post-write sweep: a second, independent pattern sweep runs over each artifact after write;
     any hit aborts the run fail-closed.
  4. Full regeneration: all five /work/lane55/ artifacts were regenerated from scratch from the
     corrected parser; no artifact containing the leaked value was sealed, hashed, or referenced.
- Final state: full leak-gate battery over /work/lane55/ (JWT token shapes, authorization-header
  prefixes, AWS key-ID shapes, code-host PAT prefixes, ASCII-armored private-key blocks,
  email-shaped strings, URL-userinfo shapes) = 0 hits; same battery re-run at seal time
  (this receipt) = 0 hits. No token value, credential, or subject identifier appears in any
  sealed artifact — checks are described abstractly here, pattern literals are not spelled out.
- Institutional lessons recorded:
  1. Column-index hygiene on headerless/shifted TSVs: assert expected column count and spot-check
     decoded shapes per column BEFORE any emission; never trust positional reads silently.
  2. Redaction-by-construction beats post-hoc scrubbing: emit filters must run unconditionally,
     with an independent post-write sweep as a second line of defense.
  3. Incident containment includes artifact lifecycle: first-pass artifacts are never hashed into
     a manifest; only regenerated, swept artifacts are sealed.

## C. Residual gaps (structural, not row-level)
1. TSV raw token values are absent in-container (v1 43-char prefix material joins 0/931 against
   the 592-value in-container pool) → offline signature verification and tolerant re-decode are
   IMPOSSIBLE for TSV rows and were NOT fabricated. Every structure-dependent disposition states
   this dependency in its reason column.
2. Eight CREDS-SSOT JSON files fail to parse (malformed JSON) and were excluded from the
   592-value pool; reason recorded; exclusion documented, not silently dropped.

## Attestations
Zero network; zero re-burn; NEVER-ROTATE intact; sha8-only; zero PII values in this receipt or
any lane-55 artifact; register untouched this subtask.
