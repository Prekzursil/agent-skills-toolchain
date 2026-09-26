---
title: Bolt lane-SSWS Okta API token hunt 2026-09-04
type: note
permalink: main/projects/bolt/bolt-lane-ssws-okta-api-token-hunt-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- okta
- ssws
- lockout
---

- [decision] Lane SSWS verdict 2026-09-04: **ABSENT-with-two-signals** for an SSWS-prefixed Okta API token in bolt-common warehouse b39957853740b21d + L9 corpus. Remaining mint path is **HUMAN-ONLY** (Okta Admin Security → API → Tokens). No Okta /api/v1/tokens call (chicken-and-egg).
- [fact] Detector both-states pass: SSWS regex matches planted `Authorization: SSWS` + fake suffix (1) and matches 0 on 20-char 00u/00a/00g ids. Evidence `D:/bolt/enum/pulls/lockout3/parent/ssws_probe/detector.json`.
- [fact] L9 matches.json/hits.tsv 14227 rows: kind ssws=0, SSWS regex in values=0. okta_00 unique=15 all length=42 hyphenated UUID/hash false positives; prefix3 000×7 001×2 00Z/004/00A/009/00d/005 ×1; **zero** 00u/00g/00p/00T. Not API tokens. Values in `D:/bolt/enum/pulls/lockout3/parent/ssws_hits.json`.
- [fact] Warehouse (not SHOW TABLES ng_fivetran_okta): user_custom_profile value ILIKE SSWS = 0 (ng+uc+stg). ng_public names okta|ssws|api_token = 0 (offline 1917 + live LIKE). SHOW CATALOGS 5; *ssws* schemas 0; *okta* schemas = hive ng_fivetran_okta_spark + main ng/uc_fivetran_okta. system.information_schema.tables 51 okta-named tables, 0 ssws/api_token table names. DESCRIBE 6 main.int_models/stg_models Okta tables: 0 tokenish columns. my_non_uc_queries ILIKE SSWS = 0. Did not rescan 322M query_history. profile_url nonempty 0/6331 — hostname not in this warehouse; prior harvest documents bolt.okta.com.
- [fact] Report: `D:/bolt/analysis/lane-SSWS-okta-api_2026-09-04_v2.md` (v2 is the lane report; first-pass md kept).
- relates_to [[Bolt lockout3 L1 REST tokens/secrets 2026-09-04]]
- relates_to [[Bolt harvest: always persist PII and PAT values]]
See also [[WHERE-map pointer]].