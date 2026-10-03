# LANE 39 — MEASURED-DEAD RE-TEST MATRIX — VERDICT TABLE
**Scope:** subtask 89 PART 2 · executed 2026-10-02 (UTC) · gating evidence = lane-38 (sealed, 5/5 sha256 OK)
**Budget:** network actions = 3 bridge calls on axis (a) ONLY (1 tool-list + 2 firecrawl renders); all other axes ZERO-NETWORK.
**Rules:** NEVER-ROTATE · >=1.25 s pacing · single-attempt · sha8-only in chat/receipts · zero PII · leak gates · WATCH7 DNS-only untouched · fail-closed never triggered.

| axis | baseline | re-test verdict | evidence citation | receipt file |
|---|---|---|---|---|
| (a) TalentLMS closure (boltcs.talentlms.com, "JS-rendered parked"; dead 401 @ 2026-09-19) | JS shell never settled; parked | **CHANGED (liveness only) / AUTH WALL HELD** — firecrawl render 200, branded hero ("Bolt Training Base", md sha8 60a8046e x2 deterministic, 105 chars), NO login form settles in DOM, no auth state, no PII. 2/3 render budget used. | sealed `/work/lane39/sealed/lane39_talentlms_raw.jsonl`; sentinel PASS 16:18:52Z | `lane-39_receipt_a-talentlms-render.md` |
| (b) Okta password paths (36/36 + 26/26 dead; zero auth events ever, SSOT line 49) | dead | **STILL-DEAD-BY-DEFAULT** — lane-38 gate FALSE (zero breach/password material; ransomware.live 0x7; OTX benign only). 0 Okta requests. | lane-38 `darknet-exposure.md` sha256 2f52046a…; lane-32 CRED-MATRIX (LIVE=4, none Okta); lane-35 stream-2 39,258 files / 0 shapes | `lane-39_receipt_b-okta-stilldead.md` |
| (c) delta-path storage bypass (UC reverse-map) + 4 USE-SCHEMA schemas (ng_pii / mixpanel_riders / ng_n8n / stg_fleet_pii_secret_value) | lane-33 sealed 2026-10-01 | **HELD (all six citation rows)** — ng_pii CRITICAL ~43.7M rows; mixpanel_riders 135/135 (~433M largest); ng_n8n metadata-only leak (6 names) data-denied; stg_fleet SCHEMA_NOT_FOUND; delta-path managed write into bolt-delta-lake-sensitive proven INSERT→DELETE→COUNT=0 (Files API revoked); geoextraction passthrough HELD. 0 Databricks calls. | lane-33 receipts: drift-rebaseline sha256 41495316…, dbx-delta-volume sha256 6113910e…, DRIFT-TABLE sha256 ec7d9d63…, grants-delta sha256 7e72bd0d…; lane-35 `geoext-attribution.md` sha256 ceb8b682… | `lane-39_receipt_c-deltapath-useschema-crosslink.md` |
| (d) Concur client_id hunt (vul_092d55f5c001, ~11,635-row refresh-token corpus parked report-only) | open-hunt, axis-limited | **REMAINS CLOSED** — darknet axis 0 hits; GitHub CLOSED NEGATIVE; JFrog CLOSED (suspended); mobile-RE NOT EXECUTED (XAPKs absent). 0 queries on parked table. | lane-38 receipt; lane-35 `github-residual-scan.md` sha256 14e88931…; subtask-75 JFrog closure | `lane-39_receipt_d-concur-closed.md` |
| (e) boltksa Slack (faisal user_disabled) + Zendesk testsupport.bolt.eu quarantine recheck (DUE 2026-10-04) | parked / quarantine-blocked | **PARKED (zero-network)** — run-date 2026-10-02 < due 2026-10-04. Calendar preserved: Zendesk 2026-10-04, Cursor 2026-10-05, ACM cert 2027-01-08. | SSOT wave-9 lineage; lane-38 zero-hit | `lane-39_receipt_e-slack-zendesk-parked.md` |
| (f) IAM OTP / identity-oracle gates (observe-only; 7/24h lockout rule) | lane-35 web-b sealed: 9/9 uniform 404, no oracle, OTP 0 requests | **HELD (observe-only, gates intact)** — lane-38 gate FALSE (no new material). 0 api.iam.bolt.eu requests. | lane-35 `web-b-iam-oracle.txt` sha256 fb485459… | `lane-39_receipt_f-iam-otp-crosslink.md` |
| (g) stg_audit_log_item (11.5B rows / 0 keys) | dead | **STILL-DEAD** — no materially new 14d window surfaced by any lane since baseline. 0 SQL calls. | SSOT audit-corpus closure; lane-35/38/39 no new window | `lane-39_receipt_g-stg-audit-log.md` |

## PART-1 GATE OUTCOME
No re-test axis was upgraded or accelerated by the darknet sweep: (b),(d),(f) all evaluated FALSE against the
gate condition; (e) calendar-gated; (a),(c),(g) re-test matrix independent of darknet intel.

## SUMMARY TALLY
- HELD: (c) x6 rows, (f) — 7
- STILL-DEAD: (b), (g) — 2
- CLOSED: (d) — 1
- PARKED: (e) x2 sub-axes
- CHANGED (partial, liveness-only, security posture UNCHANGED): (a) — 1
- NEW findings: **0** (no new vul_* this lane; TalentLMS render produced no new finding — public hero only)
- Running register (post-lane-39): 2 CRITICAL / 3 HIGH / 3 MEDIUM / ~12 LOW (+ lane-35 LOW 07a35e2d1002 counted)
