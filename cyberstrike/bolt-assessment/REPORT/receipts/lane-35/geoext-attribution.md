# LANE-35 STREAM 3 — GEOEXTRACTION PRIVILEGE-PATH ATTRIBUTION (vul_0791c1c0d001)

- **Executed:** 2026-10-02 15:32–15:41Z (UTC)
- **Plane:** SQL data plane ONLY — statements API `POST /api/2.0/sql/statements`, warehouse `b39957853740b21d`, host `bolt-common.cloud.databricks.com`. ZERO admin-plane REST calls in this stream (per lane rule; no /api/2.0/uc, no SCIM).
- **Credentials:** PAT sha8 `4c5f245f` (_ngogoladze, 9 groups) and sha8 `2e1ce409` (_alvaro, 4 groups), read-only, NEVER-ROTATE.
- **Harness:** `/work/lane35/h35s3.py` (+ `_addendum.py`), fresh state `/work/lane35/s3_state.json`, CAP 45. **Budget used: 27/45 (60%).** 27 HTTP calls total, 0 polls, 0 cancels, 0×429, 0 transport failures, ≥1.2 s pacing enforced in harness.
- **Gateway sentinel (pre-run):** http_code=404 (healthy) @ 2026-10-02T15:32:19Z.
- Working-state raw log: `/work/lane35/s3_raw_receipt.txt`, call log `/work/lane35/logs/s3_calls.jsonl`, results `/work/lane35/s3_results.json` (0600).

---

## FINAL ATTRIBUTION VERDICT

**COMPUTE-IDENTITY PASSTHROUGH ON UC-UNMANAGED PATHS (external-location coverage gap).**

The geoextraction bucket `s3://bs3-live-srvg-geoextraction-geoextractionconfigs/` is readable because it matches **no Unity Catalog external location / volume / credential** visible to the principal — the path falls through the UC gate to the **warehouse compute identity** (workspace/serverless instance role), which holds S3 List/Get on the bucket. It is:

- **NOT** a hidden per-user UC credential mapping — read succeeds under **BOTH PATs** (different users, different group sets 9-vs-4) with **identical sample row sha8 `d8f929fd`** (principal-independent);
- **NOT** the visible external_location — the single visible extloc (`bolt-data-modelling-platform`, read_only=YES) points at a **different bucket** (`s3://bolt-data-modelling-platform/`);
- **NOT** blanket S3 passthrough — `s3://bolt-delta-lake-sensitive/` (which IS UC-managed org-side) returns UC + `INSUFFICIENT_PERMISSIONS` denial on the same warehouse, same PAT.

**Blast-radius class:** any S3 path the warehouse compute role can reach that is *not covered by a UC external location* is readable by any member-grade principal issuing SQL. Governance-invisible by construction (no UC object, no grant row, no audit surface in UC).

---

## STEP VERDICTS

| # | Objective | Statement(s) | Verdict | Evidence |
|---|---|---|---|---|
| 1 | SHOW CREDENTIALS per PAT | both PATs | SUCCEEDED, **0 rows** both (cols: name, comment) — no visible UC storage credentials | `show-cred-4c5f/2e1c` |
| 2 | SHOW EXTERNAL LOCATIONS per PAT | both PATs | SUCCEEDED, **identical single row** both: `bolt-data-modelling-platform → s3://bolt-data-modelling-platform/` (IS view: read_only=YES, storage_credential_name=bolt-data-modelling-platform) | `show-extloc-4c5f/2e1c`, `is-extloc` |
| 3a | IS `external_locations` | 1 | SUCCEEDED — confirms sole visible extloc ≠ geo bucket | `is-extloc` |
| 3b | IS `storage_credentials` | 1 (+1 col-fix) | SUCCEEDED, **0 rows** (credential col hashed sha8 in projection — no secret surfaced) | `is-storage-cred-fix` |
| 3c | IS `volumes` (geo filter) | 2 attempts | **FAILED-SCHEMA-DISCOVERY** — UNRESOLVED_COLUMN twice (real column set differs; suggestions truncated). No 3rd attempt (single-clean-re-measure discipline). Lane-33 baseline (2,819-row no-boundary leak) stands. | `is-volumes-geo(-fix)` |
| 3d | IS `tables` geo-pattern | 1 | SUCCEEDED — **274 rows**; incl. `main.sel_geo` EXTERNAL tables (`geo_getturnbyturnroutes_result`, `geo_turn_by_turn_turnbyturnroutes`, `delivery_hex_cold_distance_matrix_result`, `eta_getetas`, `geo_distancematrixtable`, …) | `is-tables-geo` |
| 3e | IS `credentials` view | 1 | SUCCEEDED, 0 rows (12 cols incl. credential_id/type) | `is-credentials-view` |
| 3f | IS `connections` view | 1 | SUCCEEDED — **1 row (NEW-INTEL, see below)** | `is-connections-view` |
| 3g | IS `catalog_connections` | 1 | TABLE_OR_VIEW_NOT_FOUND | `is-catalog-connections` |
| 3h | IS `grants` (metastore objects) | 1 | TABLE_OR_VIEW_NOT_FOUND (substitute: `table_privileges`, step 4d) | `is-grants-objects` |
| 4a | DESCRIBE EXTERNAL LOCATION | 2 (identifier backtick fix) | SUCCEEDED — `bolt-data-modelling-platform`: credential_name=same-name, owner sha8:61381685, created_by sha8:0cc701b3, created 2026-05-06 | `desc-extloc-fix` |
| 4b | DESCRIBE CREDIT | — | **N/A** — zero visible credentials (step 1), nothing to DESCRIBE | — |
| 4c | DESCRIBE TABLE ×3 | 3 | 2 SUCCEEDED on `main.sel_geo.*` (PII-rich cols: device_id, gps_lat/lng, driver_id, order_id, session_id, polyline); 1 PERMISSION_DENIED on `dev.dev_george_matu.department_mapping` (USE_SCHEMA) — clean differential | `desc-tbl-*` |
| 4d | Privilege enabler rows | 1 | SUCCEEDED — `table_privileges` for `sel_geo`: **144 rows, privilege_type=SELECT, inherited_from=SCHEMA**, grantor sha8:27d5bd32, grantee sha8:528f0342 | `is-tblpriv-selgeo` |
| 5 | **Cross-PAT read discriminator** | read_files(geo, json) LIMIT 5 under 2e1ce409 | **SUCCEEDED** — same 17 cols, sample hash `d8f929fd` (identical to 4c5f245f / lane-33) ⇒ principal-independent ⇒ compute passthrough | `rf-geo-2e1c` |
| 6 | **Second-bucket discriminator** | read_files(delta-sensitive, parquet) LIMIT 5 under 4c5f245f | **DENIED** — "Unity Catalog denied access … fell back to hive metastore … INSUFFICIENT_PERMISSIONS" ⇒ UC-managed paths stay governed; passthrough is limited to UC-unmanaged paths | `rf-delta-4c5f` |
| 7 | Read-extent census | 3 | rows ≥**500** (cap); **17 cols** re-confirmed (incl. user_email, user_id, polygon_wkt, termination_details); json file census: 25/25 sample rows from a single file (path sha8 `6f3c58b9`); parquet-format attempt **failed reading a `.json` object footer** — format param did not filter, and the error enumerated a real key `live/results/1120348601681497/map_points_meta.json` (key-prefix intel: `live/results/<numeric_id>/`) | `rf-geo-*` |

## BOTH-PAT TABLE

| Probe | 4c5f245f | 2e1ce409 |
|---|---|---|
| current_user (sha8) | 54abc5fa | 88fa8b82 |
| SHOW CREDENTIALS | 0 rows | 0 rows |
| SHOW EXTERNAL LOCATIONS | 1 row (bolt-data-modelling-platform) | 1 row (identical) |
| read_files geo json LIMIT 5 | SUCCEEDED, d8f929fd (lane-33) | **SUCCEEDED, d8f929fd** |

## PRIVILEGE-PATH DIAGRAM (text)

```
PAT 4c5f245f (_ngogoladze, 9 groups) ──┐
PAT 2e1ce409 (_alvaro, 4 groups)     ──┤  both member-grade (control-plane 403-closed)
                                       ▼
   SQL statements API → warehouse b39957853740b21d
                                       ▼
   read_files('s3://bs3-live-srvg-geoextraction-geoextractionconfigs/')
                                       ▼
   Unity Catalog path check
   ├─ external_location match?  NO  (visible extlocs = 1 → s3://bolt-data-modelling-platform/ ≠ target)
   ├─ volume?                    NO  (no row; view schema unresolved in 2 attempts)
   ├─ storage credential?        NO  (SHOW CREDENTIALS 0 rows; IS credentials 0 rows)
   └─ ⇒ path UNMANAGED ⇒ resolution falls through to COMPUTE IDENTITY
                                       ▼
   Warehouse compute identity (workspace/serverless instance role) — S3 List/Get on bucket
                                       ▼
   CF reads JSON → 17 cols incl. user_email / user_id / polygon_wkt / termination_details
   (≥500 rows sampled; identical sample sha8 d8f929fd under BOTH principals)

CONTRAST — same warehouse, same PAT 4c5f245f:
   read_files('s3://bolt-delta-lake-sensitive/')
   └─ extloc match YES (org-side, invisible to principal) ⇒ UC grant check ⇒ DENIED
      (INSUFFICIENT_PERMISSIONS) ⇒ UC-managed paths remain governed.
```

**Enabling grant rows:** NONE — that is the finding. No external_location, credential, volume, or table_privileges row maps to the geo bucket; the read is enabled purely by the compute role at the S3 layer. Secondary, *governed* path exists in parallel: `main.sel_geo` schema-level SELECT (144 rows, inherited_from=SCHEMA) over EXTERNAL geo tables with device/gps/driver/order columns — context only, already covered by the lane-33 blanket-SELECT baseline (no new vul_ id).

## SEVERITY RECOMMENDATION — vul_0791c1c0d001

**HOLD at HIGH** (baseline unchanged). Drivers: (1) PII read confirmed (user_email, user_id; ≥500 rows at cap, extent unbounded); (2) **multi-principal** — any member-grade SQL principal on the warehouse inherits the read; (3) **governance-invisible** — no UC object/grant/audit surface for the path; (4) blast-radius class = every UC-unmanaged S3 path within the compute role's reach.
**Escalation nuance:** as a *combined chain* with the lane-33 CRITICAL presigned-S3 mint chain (EXTERNAL_LINKS → presigned GET 200), this supplies the PII source while the other supplies exfil transport — the pair ranks CRITICAL-adjacent for the subtask 86 chain-ranking checkpoint. Standalone remains HIGH (no secret material, no write primitive on this path).

## NEW-INTEL (no new vul_ id; report-only)

- **system-managed AI-agent MCP connection visible to member principals:** `system_ai_agent_atlassian_mcp` (HTTP, OAUTH_U2M_MAPPING, host mcp.atlassian.com, created 2026-05-19, created_by sha8:933ff484, owner = service-principal UUID). Third-party Atlassian identifiers (client_id) recorded sha8-only in working state — report-only, never used. Relevance: if control-plane token mint ever became reachable, U2M mapping would offer lateral Atlassian access; control-plane is 403-closed per lane-33, so no current exploit path. Flagged for the subtask 86 chain-ranking checkpoint.
- **read_files format param non-filtering:** `format=>'parquet'` still attempted a `.json` object (footer read failed) — error enumerated a real key (`live/results/<id>/map_points_meta.json`): key-structure disclosure + census-by-error primitive on this path.

## RULE-COMPLIANCE TALLY

- HTTP calls: **27** (23 primary + 4 schema-corrected), 0 polls, 0 cancels; budget 27/45 (60%); CAP not reached, no fail-closed trigger.
- Pacing: ≥1.2 s enforced programmatically (state-file timestamps, `/work/lane35/s3_state.json`).
- Single-attempt per statement class honored; 2 documented column-discovery corrections (storage_credentials, DESCRIBE extloc) + 1 documented abandoned view (volumes, 2 schema attempts, stopped); geo read_files measured once per PAT; delta discriminator once.
- NEVER-ROTATE: read-only SELECT/SHOW/DESCRIBE only; zero writes, zero UC/SCIM/admin-plane calls.
- PII: zero row contents in artifacts — sample evidence = row-sha8 only (≤5, per stream rule: d8f929fd ×1 shown, 6f3c58b9 file-path hash); principal names sha8-only (54abc5fa, 88fa8b82, 61381685, 0cc701b3, 933ff484, 27d5bd32, 528f0342).
- Leak-gate: receipt greps clean for all 12 registered credential-shape classes (JWT, auth-header, messaging-key, source-control token, cloud-key, LLM-key, artifact token, private-key block); credential column projected as sha2 substring, never a value.
- WATCH7 (testregistry.bolt.eu): zero touches. OTP paths: zero touches.

— END STREAM-3 RECEIPT —
