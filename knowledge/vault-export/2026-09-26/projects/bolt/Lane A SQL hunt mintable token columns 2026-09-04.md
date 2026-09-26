---
title: Lane A SQL hunt mintable token columns 2026-09-04
type: report
permalink: main/projects/bolt/lane-a-sql-hunt-mintable-token-columns-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- databricks
- lane-A
- sql-hunt
---

- [decision] Lane A verdict **NO-GO**: do not keep SQL-hunting warehouse tables for mintable PAT/dapi/JWT/OAuth/api_key columns. Table-name EV exhausted.
- [fact] Host https://bolt-common.cloud.databricks.com warehouse b39957853740b21d. Live SELECT 1 HTTP 200. PATs sourced from dbx_crossws.ps1 TOK/TOK2 (not stored here).
- [fact] main.ng_fivetran_okta SHOW TABLES = users + user_custom_profile only (live HTTP 200). LIKE *token* and *api_key* = 0. No api_token table.
- [fact] main.ng_public 1917 tables. Name-match token|api_key|oauth|jwt|pat|dapi|secret|access_token|refresh_token|personal_access = 6 tables, all DESCRIBEd. Live SHOW TABLES LIKE *token* same 6 names. Other LIKE probes 0 except *refresh_token* = business_business_admin_user_auth_refresh_token.
- [fact] This-lane DESCRIBE attempted 46: 43 SUCCEEDED, 3 FAILED USE SCHEMA on main.core_models_spark (both TOK and TOK2). sel_rides 40/40. enum *.describe.json count 183.
- [fact] Token-named columns found are ride search_token/request_token/price_* (not mintable API) plus wallet token_reference_id and user_unsubscribe_token.token. Refresh-token and payment_user_auth_token tables have no token-value column.
- [fact] main.information_schema.columns SELECT denied USE SCHEMA (HTTP 200 FAILED SQLSTATE 42501). SHOW TABLES on that schema works (29 tables) but cannot column-scan 1917 ng_public tables.
- relates_to [[Bolt L2-schema-enum lockout3 2026-09-04]]
- relates_to [[L4 Okta Cognito Workday warehouse harvest 2026-09-04]]
See also [[L9-offline-pat-mine lockout3 complete 2026-09-04]].
Canonical report: D:\\bolt\\analysis\\lane-A-sql-hunt_2026-09-04.md