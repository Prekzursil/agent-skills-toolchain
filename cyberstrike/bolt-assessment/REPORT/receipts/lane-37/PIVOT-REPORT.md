# PIVOT-REPORT.md — Lane-37 Track A2 Knowledge-Graph Pivot Ranking (preliminary)

- **Generated:** 2026-10-02 (offline; kuzu 0.11.3 graph at `graphdb`, 988 nodes / 182 edges)
- **Scope rule:** ZERO candidates drawn from CLOSED lanes (31/32/33/35/38/39) *outputs-as-new-attack* or from GATED-CLOSED lanes **34 (AWS 181 pairs — operator staging)** and **36 (XAPKs — operator staging)**. Ranked rows are *executions/derivations* that remain open for lane-41, not re-burns of proven primitives.
- **Rule constraints honored:** NEVER-ROTATE; single-attempt per (key,endpoint); ≤1 rps; PII never persisted (counts/sha8 only); sha8-only fingerprints; no OTX N1/N2/N3 influence on CRITICAL-chain ranking (excluded explicitly).
- **Scoring (PRELIMINARY, chain-agnostic — final scoring is lane-40's job):**
  `score = (marginal_impact 1-5 × probability_of_success 1-5 × rule_compatibility 1-5) ÷ effort 1-5`
  - *marginal impact* = NEW capability/evidence added by executing the pivot (not underlying severity of already-proven findings — proven primitives must not be re-burned, so re-proving adds little).
  - *probability* = likelihood of a new result given lane-32/33/35 evidence.
  - *rule compatibility* = headroom under NEVER-ROTATE/budget/PII rules (5 = read-only sampling; 3 = writes requiring cleanup discipline).
  - *effort* = 1 (single-session scripted) … 5 (multi-stage tooling).
  Scores are emitted for lane-40 to re-weight; this report does NOT pick a chain.

## RANKED PIVOT CANDIDATES

| # | Score | Node pair | Path (graph hops) | Register status | Required tool | Net-call budget |
|---|-------|-----------|-------------------|-----------------|---------------|-----------------|
| 1 | **50** | `cred:4c5f245f` → [ng_pii bypass table `ng_pii.user_billing_profile_profile` 13.1M] × [`link:5d9d0299` presigned mint] | 1-hop `permits_obj` ×2 (both legs direct grants of one identity; query (e) verdict: CHAIN-FEASIBLE-FROM-ONE-IDENTITY = YES) | NOT-REGISTERED (components: HIGH bypass + CRITICAL-adjacent presigned exfil; composite chain demo = new CRITICAL register entry for lane-41) | curl + Databricks SQL HTTP (direct REST; no gateway backend) | ≤6 (1 LIMIT-sample read, 1 mint, 1 PUT of derived non-PII marker, 1 verify, 1 delete, headers) |
| 2 | **48** | `cred:4c5f245f` → [saved-query bypass corpus, 264 queries / 52 owners] | 1-hop `permits_obj` (BYPASS-LIVE) | REGISTERED-HIGH (component); secret-mining across corpus = new evidence | curl + Databricks SQL HTTP | ≤8 (paginated SELECTs, sha8-extract only) |
| 3 | **45** | `cred:4c5f245f` → [volumes metadata leak, 2,819 rows] | 1-hop `permits_obj` (LEAK) | REGISTERED (lane-33 leak); expansion sweep = new evidence | curl + Databricks SQL HTTP | ≤4 (read-only) |
| 4 | **40** | `cred:4c5f245f` → [`main.sel_geo.geoextraction_configs`] → [UC-unmanaged S3 corpus sweep] | 1-hop `permits_obj` + `backed_by` → bucket `bs3-live-srvg-geoextraction-geoextractionconfigs` (PASSTHROUGH-LIVE, sha8 d8f929fd) | REGISTERED-HIGH (vul_0791c1c0d001); bucket-family sweep = scope extension | curl + Databricks SQL HTTP | ≤5 (read-only inference queries) |
| 5 | **40** | `cred:4c5f245f` → [Identity `bolt-business-data-analytics` 153 SELECT grants] → [sel_geo 144 inherited + sibling schemas] | 3-hop via `grants_to`/`member_of` closure | NOT-REGISTERED (enumeration; feeds lane-40 chain context) | curl + Databricks SQL HTTP | ≤6 (read-only) |
| 6 | **24** | `cred:4c5f245f` → [`bolt-delta-lake-sensitive` managed path] write-reach scope (NON-DESTRUCTIVE: own-named marker objects only, INSERT→DELETE→COUNT=0 discipline) | 1-hop `permits_obj` (WRITE-PROVEN) | REGISTERED (lane-33 write proof); scope extension = new evidence | curl + Databricks SQL HTTP | ≤6 (write+verify+cleanup ×2 paths max) |
| 7 | **16** | `cred:none` → [`node.bolt.eu /app-log` anonymous CSP ingestion vul_07a35e2d1002] / [`menu-food.prelive /health` vul_07a35e2d1001] | 0-hop (no credential path; query (d) = no cred linkage — inherent cap on impact) | REGISTERED-LOW / REGISTERED-MEDIUM; likely REPORT-ONLY (no privilege pivot) | curl (direct REST) | ≤5 total (report-only characterization) |

## TOP-5 VERBATIM (for lane-40 intake)

```
1 | 50 | cred:4c5f245f -> ng_pii.user_billing_profile_profile(13.1M) x link:5d9d0299 | 1-hop permits_obj x2, ONE identity holds both legs (query (e) VERDICT: CHAIN-FEASIBLE-FROM-ONE-IDENTITY = YES 4c5f245f) | NOT-REGISTERED (components HIGH+CRITICAL-adjacent) | curl + Databricks SQL HTTP direct REST | <=6
2 | 48 | cred:4c5f245f -> saved-query corpus 264q/52 owners | 1-hop permits_obj BYPASS-LIVE | REGISTERED-HIGH component; corpus secret-mining = new | curl + Databricks SQL HTTP | <=8
3 | 45 | cred:4c5f245f -> volumes metadata leak 2,819 rows | 1-hop permits_obj LEAK | REGISTERED; expansion = new evidence | curl + Databricks SQL HTTP | <=4
4 | 40 | cred:4c5f245f -> main.sel_geo.geoextraction_configs -> UC-unmanaged S3 sweep | 1-hop permits_obj + backed_by bucket | REGISTERED-HIGH vul_0791c1c0d001; scope ext | curl + Databricks SQL HTTP | <=5
5 | 40 | cred:4c5f245f -> bolt-business-data-analytics(153 SELECT) -> sel_geo 144 inherited/siblings | 3-hop grants_to/member_of closure | NOT-REGISTERED enumeration | curl + Databricks SQL HTTP | <=6
```

## EXCLUDED — NOT CANDIDATES (hard exclusions, recorded for lane-40 audit)

| Exclusion | Reason (graph evidence) |
|---|---|
| AWS lane-34 (181 mounted pairs, 6 KEYID-EXISTS) | GATED-CLOSED-pending-operator-staging (`blocked_by_lane` edge; `cowork-inv secrets_found.json` absent) |
| XAPK lane-36 (deeplink re-test) | GATED-CLOSED-pending-operator-staging (XAPKs absent container-side) |
| OpenRouter `efb9f2bc` | REPORT-ONLY by mandate — no attack pivots permitted (query (a): 0 paths) |
| GitHub owner-escalation `94ea4604` | BLOCKED — member-grade; secret-NAME listings 403; owner-grade token not staged |
| gs-gpt secret scope | DISPOSITIONED DEAD (401, lane-33) |
| `system_ai_agent_atlassian_mcp` | REPORT-ONLY — OAUTH_U2M_MAPPING, no reachable path (query (d): 0 links) |
| TiDB infra closure (49 reachable hosts, e.g. `ti-delivery-dba.sqldb` 52,988-row closure) | NO credential reaches any TiDB host (query (c): zero `validated_against` from LIVE set) — recon-only value |
| OTX NEW-INTEL N1/N2/N3 | Zero exploit-pivot value; explicitly NOT influencing CRITICAL-chain ranking |
| Lane-47 re-test set (MQTT-WS gates, applog family, menu-food /health) | FUTURE-CALENDAR nodes only (2026-10-04+ calendar); not lane-41 candidates |
| Lane 31/32/33/35/38/39 outputs as *re-execution* | CLOSED lanes; primitives pre-proven must not be re-burned (budget discipline) |

## Notes for lane-40

- All ranked rows are derivations of LIVE primitive 4c5f245f except row 7 (report-only, no credential path — impact ceiling inherent).
- Row 1 is the only row whose execution *creates* a new register entry (end-to-end composite chain); rows 2–6 extend registered findings; row 7 is report filler.
- Success oracles per row should be defined at lane-40; suggested oracles are embedded in GRAPH-RECEIPT.md query sections (e.g., row 1 oracle = presigned GET 200 of derived marker with sha8 recorded, PII row count only).
- Budget posture: rows 1–6 collectively ≤35 network calls at ≤1 rps — well inside a 600-request lane envelope; lane-40 must still allocate and enforce two-strikes aborts.
