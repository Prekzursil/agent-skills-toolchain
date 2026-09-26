---
title: Lane F Databricks cross-workspace PAT probe 2026-09-04
type: report
permalink: main/projects/bolt/lane-f-databricks-cross-workspace-pat-probe-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- databricks
- lane-F
- lockout
---

- [decision] Lane F verdict is NO-GO: the two live bolt-common SQL PATs in `D:\bolt\scripts\dbx_crossws.ps1` (`$TOK` ngo, `$TOK2` alvaro) do not work on bolt-datascience or bolt-geo.
- [fact] 04.09.2026 probe: 3 hosts × 2 PATs. SCIM `/Me`, `token/list`, `secrets/scopes/list`, `sql/warehouses` all HTTP 403 on https://bolt-datascience.cloud.databricks.com and https://bolt-geo.cloud.databricks.com with `Invalid access to Org` (datascience org `3829506390716583`, geo org `1492481942411573`).
- [fact] Control bolt-common: SCIM 200 ngo `nikolozi.gogoladze@bolt.eu` groups_n=10; alvaro `alvaro.valpuesta@bolt.eu` groups_n=5. token/list 403 missing `authentication` scope; secrets 403 missing `secrets` scope. Warehouses 200 n=1 id `b39957853740b21d` Common SQL. SHOW CATALOGS SUCCEEDED n=5: dev, hive_metastore, main, samples, system.
- [fact] Two independent HTTP stacks agreed (Python urllib + curl.exe). Common SCIM 200 was the known-present detector check.
- [fact] Artifacts: `D:\bolt\enum\pulls\lockout3\parent\rest_crossws\` and analysis `D:\bolt\analysis\lane-F-cross-workspace_2026-09-04.md`. NEVER-ROTATE.
- relates_to [[Bolt harvest: always persist PII and PAT values]]
- relates_to [[L4 Okta Cognito Workday warehouse harvest 2026-09-04]]
