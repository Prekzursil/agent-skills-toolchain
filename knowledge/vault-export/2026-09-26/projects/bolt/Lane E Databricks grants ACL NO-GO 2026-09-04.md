---
title: Lane E Databricks grants ACL NO-GO 2026-09-04
type: note
permalink: main/projects/bolt/lane-e-databricks-grants-acl-no-go-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- databricks
- lane-E
- unity-catalog
---

- [decision] Lane E verdict **NO-GO**: bolt-common SQL PATs (ngo primary) cannot expand privilege via Unity Catalog GRANT or warehouse ACL.
- [fact] current_user `nikolozi.gogoladze@bolt.eu`; warehouse `b39957853740b21d` GET HTTP 200; SHOW GRANTS ON CATALOG main = BROWSE + USE CATALOG for `account users` only.
- [fact] SHOW GRANTS ON SCHEMA `main.ng_public` / `main.ng_fivetran_okta` = SELECT/USE SCHEMA/EXECUTE/READ VOLUME only. No MANAGE/OWNERSHIP. schema `is_grantable=YES` count = 0.
- [fact] REST GET `/api/2.0/permissions/warehouses/b39957853740b21d` HTTP 403 scope `access-management` (Python + PowerShell). UC permissions REST HTTP 403 scope `unity-catalog`.
- [fact] SHOW GRANTS ON WAREHOUSE SQLSTATE 42601 PARSE_SYNTAX_ERROR. SHOW GRANTS `account users` ON CATALOG main = PERMISSION_DENIED READ METADATA.
- [fact] CREATE/MODIFY visible on 11 business/incentives schemas via groups; not grant expansion (`is_grantable=NO`). No GRANT/REVOKE executed.
- relates_to [[Bolt lockout3 10-lane harvest 2026-09-04]]
- relates_to [[L4 Okta Cognito Workday warehouse harvest 2026-09-04]]
See also [[LOCKOUT-ACCESS_2026-09-04]].
