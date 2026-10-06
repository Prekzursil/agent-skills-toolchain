# RECEIPT 01 — LANE-55 JWT TRIAGE COMPLETION (subtask-152 stage 1, OFFLINE)
FINAL-TEST 2026-10-05 · subtask-152 stage 2 seal · strictly offline · zero wire calls · sha8-only · zero PII

## Provenance (integrity gate PASS, fail-closed)
- Input corpus: `/work/on-demand/deep-mine/jwt_triage_v2.tsv`
- sha256: `b9bcb15ce3a61349e945e180278617b7e587b70cf4b0dcde2b3127a3977a324a` (first-8 `b9bcb15c` — matches expected prefix; verified in code, process exits on mismatch)
- Lines: 1,145 (1 header + 1,144 data rows)
- Run-date: 2026-10-05. Mode: offline decode only — zero network, zero service decode attempts.

## Method
1. Fail-closed integrity gate on the TSV (line count + sha256 prefix) BEFORE parsing.
2. Per-row token-sha8 computed over the token column; internal dedupe keeps first occurrence
   (132 duplicate rows recorded; 1,012 unique sha8s). Every one of the 1,144 data rows retains a
   FINAL disposition; duplicate rows inherit their first-row verdict (dup_of_row column in matrix).
3. Header+payload decode (base64url, tolerant of padding/JSON quirks). alg recorded:
   1,139 HS256 / 1 RS256 / 4 empty-alg rows. exp/iat evaluated against run-date 2026-10-05.
4. iss/aud/kid mapped ONLY via substitution sources (the 25-endpoint auth map is
   reference-missing-FINAL and was NOT searched):
   - lane-31 ATTACK-SURFACE-INVENTORY (sha8 `d37edc22`) + DELTA-TABLE (sha8 `cc3b1e43`)
   - lane-36 endpoint census (272 rows; 39 NEW) + `lane36_final_inventory.md` (sha8 `70c785f2`)
   - F18 static auth map from Retrofit annotations:
     @POST /driver/{getAccessToken,startAuthentication,sendMagicLink,v2/getLoginConfiguration,
     authenticateWithMagicLink,authenticate,resendVerificationCode,completeAuthentication},
     @GET /driver/getAuthenticationConfiguration, /driver-auth/partnerDriver/*,
     /driver/getDriverPortalMagicToken
5. Claims logged sha8-only; any potentially-PII claim value hashed or dropped at source;
   HS256 secrets handled keys-only (never written to any artifact, never printed).
6. HS256 signature verification attempted ONLY where the secret existed in-container
   (python hmac, offline). Decisive negative: NO TSV row has its raw value present in-container
   (v1 43-char prefix material joins 0/931 against the 592-value in-container pool) → no signature
   was verifiable, and none was fabricated; all HS256 verdicts are structural/claim-based with the
   dependency stated in the reason column.

## Reconciliation / overlap
- cowork-inv `secrets_found.json` (500 entries, sha8 `2966783c`): 249 jwt sha8s; all 249 also
  present in CREDS-SSOT (cowork ∩ SSOT = 249).
- CREDS-SSOT: 55,886 rows (782 base + 53 appends); 592 jwt-typed sha8s; 8 load-fail JSON files
  excluded with reason recorded in stage-1 summary.json.
- TSV rows with an in-container raw value: 0 → row-level value intersection is impossible
  in-container; family-level lineage is documented in g09_closure.md instead (no claim of
  row-level identity is made anywhere).

## Classification (run-date 2026-10-05; sum = 1,144 data rows ✓)
| class | rows |
|---|---|
| EXPIRED | 1,123 |
| REPORT-ONLY | 15 |
| UNUSABLE | 6 |
| LIVE-CANDIDATE | 0 |

- Max exp across all 1,144 rows: 2026-09-16 < run-date → zero unexpired rows.
- Zero rows with iss/aud mapping to any F18/lane-31/lane-36 endpoint AND an independently
  verifiable signature → zero LIVE-CANDIDATES.
- Dominant family: servicedesk-jwt-token-issuer ×1,044 (Atlassian JSM third-party portal — NOT
  Bolt F18). Other families: unattributed 61 + unattributed-no-exp 7, github.com 8,
  marketing journey-trigger (victim-shaped) 6, undecodable 5, plus singletons
  (UUID issuer 96c3ebd1-… ×4, rtc.sinch.com/applications/0078ff3c-… ×3, jsm-portal-kid-uuid 2,
  uf-back / generic-keypair/dt-api-filestore / Bellhop / internal process-signing 1 each).

## Prior dispositions honored VERBATIM (no re-work)
- 8 EXPIRED sha8s: 79a887c3, 82ae6a66, a32b669b, 245861ad, ce4cb63d, 4bdacafb, 5a2f7eba,
  18544bde (incl. bolt-campaigns-subscription HS256s — keys-only).
- 63e44c43 DEAD-AT-PORTAL stands (offline exp 2026-10-13; re-probe prohibited).
- NO-RE-BURN, zero-touch, catalog-only: f5cc101f (datahub JWT, burned 401), 4c5f245f and
  2e1ce409 (Databricks PATs, LIVE 2026-10-03) — TSV attachment count 0; zero decode attempts
  against services; in-container presence confirmed keys-only.

## Sealed artifacts (/work/lane55/, dir 0700, all files 0600)
| artifact | sha256 |
|---|---|
| jwt_disposition_matrix.tsv (15 cols, 1,145 lines) | d028330a726e98d8b1e0db5092fb89484d953ef935adc634571fe78ea67e55fd |
| g09_closure.md | 70f239152c130437b48817b33e36271a831b5d2d41d99f434f61c563dfc7a39f |
| drift_statement.md | 29ac271e240b3f3e0fc28fd291c635b5e78e730487c97ca607a1da09881056a6 |
| summary.json | d7a92b55ce3d6622734388c6c00db3b8c3da88291b63b972a2ca20efea5d648d |
| token_vault.tsv (0600, header-only, ZERO-validation rationale embedded) | 27a47ff923bc42def7630379e57286196a84d6697595251fb9d080b93b02c8fd |

Tooling: `/tmp/lane55_s1_triage.py` (Python 3 stdlib only, fail-closed integrity gate,
emit-time redaction + post-write sweep, py_compile clean).

## Attestations
Zero network; zero service decode/validation attempts; zero OTP/MFA/refresh/account mutation;
NEVER-ROTATE intact; token values keys-only on disk (vault 0600); sha8-only claims; zero PII
in artifacts; no leak-gate pattern literals spelled inside gated artifacts; register untouched
this subtask (286 lines ×3, sha256 98859339… — re-verified at seal time).
