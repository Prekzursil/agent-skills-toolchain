---
title: Lane D Databricks token create NO-GO 2026-09-04
type: note
permalink: main/projects/bolt/lane-d-databricks-token-create-no-go-2026-09-04
status: active
valid_as_of: '2026-09-04'
---

# Lane D Databricks token create NO-GO 2026-09-04

- [decision] Lane D mint probe is **NO-GO**. `POST /api/2.0/token/create` on `bolt-common.cloud.databricks.com` returned HTTP 403 on both SQL PATs. Do not retry this endpoint with the same PATs.
- [fact] ngo `$TOK` HTTP 403, error_code 403, message class missing-required-scopes (`authentication`), `token_value` key absent. Artifact `D:/bolt/enum/pulls/lockout3/parent/rest_recheck/token_create_ngo.json` (144 B). ReqId `837f95c9-c4f2-4a80-bae1-6619add4c1c4`.
- [fact] alvaro `$TOK2` HTTP 403, error_code 403, same message class, `token_value` key absent. Artifact `D:/bolt/enum/pulls/lockout3/parent/rest_recheck/token_create_alvaro.json` (144 B). ReqId `17712298-46cb-4b53-bf38-d497af683fed`. One extra POST only, as second independent signal.
- [fact] Request body was `lifetime_seconds=300` and comment `estate-lockout-probe-do-not-use-if-403`. Official shape: https://docs.databricks.com/api/workspace/tokens/create
- [fact] Matches prior `GET /api/2.0/token/list` 403 (missing `authentication` scope) on the same PATs.
- [decision] NEVER-ROTATE existing PATs. Creating a new token would have been mint, not rotation; mint did not succeed.
- relates_to [[Bolt lockout3 L1 REST tokens/secrets 2026-09-04]]
- relates_to [[Bolt harvest: always persist PII and PAT values]]
See also [[WHERE-map pointer]].
