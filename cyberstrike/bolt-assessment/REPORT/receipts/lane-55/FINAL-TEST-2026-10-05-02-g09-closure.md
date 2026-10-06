# RECEIPT 02 — LANE-32 G-09 12-ROW GAP CLOSURE (FINAL, 2026-10-05, OFFLINE)
FINAL-TEST 2026-10-05 · subtask-152 stage 2 seal · strictly offline · zero wire calls · sha8-only · zero PII

## Gap arithmetic (lane-32 receipt vs TSV v2)
- TSV v2 non-expired open rows: 16 NO_EXP + 5 DECODE_ERROR = 21.
- Lane-32 (2026-10-01) had dispositioned 8 NO_EXP-shape + 1 decode-error via CREDS-SSOT values;
  8 NO_EXP + 4 decode-error TSV rows remained un-ingested = the 12-row G-09 gap.
- On 2026-10-05 ALL 21 non-expired rows received FINAL dispositions; the 12 gap rows are a
  subset of those closures. G-09 is CLOSED.
- Row-level token identity between TSV rows and the 18 cohort sha8s is UNPROVABLE in-container:
  raw values for TSV rows are absent (v1 prefix material joins 0/931 against the 592-value
  in-container pool). Closure therefore used structure/iss/aud mapping per standing instruction,
  never value re-decode. No row-level attribution is claimed.

## The 12 gap rows, explicitly
- 8 NO_EXP un-ingested: 6× BP-9558 campaigns-shape (data+iat), G3IOT-512 (account-shaped),
  1 marketing journey-trigger row from the DPLC-726/MVRT-1743/TAXP-3732 set — all closed
  REPORT-ONLY today (see table).
- 4 decode-error un-ingested: DRAG101-107, DRAG101-530, EBIKE1-526, PROC-448 (utf8 failures)
  and DRX-24614 (json failure) — of the 5 DECODE_ERROR rows lane-32 had already dispositioned
  one as sha8 99a97e8c UNUSABLE, leaving 4 un-ingested; row-level attribution of 99a97e8c to a
  specific TSV row is unprovable and NOT claimed. All 5 rows are UNUSABLE today with per-row
  reason; tolerant re-decode (wrong padding / JSON5-style / doubled quotes) was attempted only
  against material present in-container — none exists for these rows → UNUSABLE stands with
  reason "raw value not present in container".

## Per-row FINAL dispositions (all 21 non-expired rows)
| row | issue_key | state | alg | payload shape | FINAL verdict | rationale |
|---|---|---|---|---|---|---|
| 18 | BP-9558 | NO_EXP | HS256 | payload_keys=[data,iat], no exp/iss | REPORT-ONLY | campaigns-shape, structure-only, catalog-only |
| 19 | BP-9558 | NO_EXP | HS256 | payload_keys=[data,iat] | REPORT-ONLY | duplicate of row-18 shape, catalog-only |
| 20 | BP-9558 | NO_EXP | HS256 | payload_keys=[data,iat] | REPORT-ONLY | duplicate of row-18 shape, catalog-only |
| 21 | BP-9558 | NO_EXP | HS256 | payload_keys=[data,iat] | REPORT-ONLY | duplicate of row-18 shape, catalog-only |
| 22 | BP-9558 | NO_EXP | HS256 | payload_keys=[data,iat] | REPORT-ONLY | duplicate of row-18 shape, catalog-only |
| 23 | BP-9558 | NO_EXP | HS256 | payload_keys=[data,iat] | REPORT-ONLY | duplicate of row-18 shape, catalog-only |
| 254 | G3IOT-512 | NO_EXP | HS256 | payload_keys=[account_id,domain,id] | REPORT-ONLY | account-shaped, no exp/iss, catalog-only |
| 211 | DPLC-726 | NO_EXP | HS256 | entity/iat/messageTemplateId/recipient | REPORT-ONLY | identifiable third-party recipient; standing rule 8 victim-shaped → catalog-only; secret not in corpus |
| 719 | MVRT-1743 | NO_EXP | HS256 | entity/iat/journeyId/journeyTrigger | REPORT-ONLY | victim-shaped, standing rule 8, catalog-only |
| 720 | MVRT-1743 | NO_EXP | HS256 | entity/iat/journeyId/journeyTrigger | REPORT-ONLY | victim-shaped, standing rule 8, catalog-only |
| 721 | MVRT-1743 | NO_EXP | HS256 | entity/iat/journeyId/journeyTrigger | REPORT-ONLY | victim-shaped, standing rule 8, catalog-only |
| 1070 | TAXP-3732 | NO_EXP | HS256 | entity/iat/messageTemplateId/recipient | REPORT-ONLY | victim-shaped, standing rule 8, catalog-only |
| 1071 | TAXP-3732 | NO_EXP | HS256 | entity/iat/messageTemplateId/recipient | REPORT-ONLY | victim-shaped, standing rule 8, catalog-only |
| 448 | LSS-35948 | NO_EXP | HS256 | exp present, unparseable in generator; kid=acdbec1e-bf18-439f-8348-5470fdecd736 | REPORT-ONLY | kid UUID shape maps to Atlassian JSM third-party family; catalog-only, no re-burn |
| 449 | LSS-35948 | NO_EXP | HS256 | exp present, unparseable; kid=acdbec1e-bf18-439f-8348-5470fdecd736 | REPORT-ONLY | same as row 448 |
| 539 | LSS-54560 | NO_EXP | HS256 | payload_keys=[iat,processId,signerId] | UNUSABLE | internal signing artifact, no auth semantics, no exp/iss, no offline verification path, no victim shape |
| 216 | DRAG101-107 | DECODE_ERROR | — | payload utf8 decode failure | UNUSABLE | tolerant retry impossible: raw value not present in container |
| 218 | DRAG101-530 | DECODE_ERROR | — | payload utf8 decode failure | UNUSABLE | tolerant retry impossible: raw value not present in container |
| 237 | EBIKE1-526 | DECODE_ERROR | — | payload utf8 decode failure | UNUSABLE | tolerant retry impossible: raw value not present in container |
| 934 | PROC-448 | DECODE_ERROR | — | payload utf8 decode failure | UNUSABLE | tolerant retry impossible: raw value not present in container |
| 223 | DRX-24614 | DECODE_ERROR | HS256 | payload json parse failure | UNUSABLE | tolerant retry impossible: raw value not present in container |

Tally of the 21: REPORT-ONLY 15 · UNUSABLE 6 · (this 21-row set exactly equals the 15 REPORT-ONLY
+ 6 UNUSABLE of the global classification — consistent with receipt 01).

## Issuer-mapping basis (substitution sources only)
- servicedesk-jwt-token-issuer → Atlassian JSM tenant (third-party portal; NOT Bolt F18 endpoints).
- campaigns family → bolt-campaigns-subscription class per lane-32/CREDS-SSOT lineage
  (Bolt-owned, campaigns.bolt.eu); not in lane-36 census NEW set; no F18 Retrofit match.
- marketing journey-trigger shapes (entity/recipient/messageTemplateId/journeyId/triggerId) →
  messaging-pipeline tokens (Braze/Iterable-shaped; iamcache.braze.com appears in lane-36 census);
  victim-shaped → catalog-only.
- F18 static auth map: NO row's iss/aud maps to any F18 endpoint → zero endpoint proposals.

## Attestations
Zero network; zero decode attempts against live services; zero mutation; NEVER-ROTATE intact;
claims sha8-only; no victim-shaped token was validated or re-burned; no token values in this
receipt; register untouched.
