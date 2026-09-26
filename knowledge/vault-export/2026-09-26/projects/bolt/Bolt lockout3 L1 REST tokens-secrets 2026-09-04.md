---
title: Bolt lockout3 L1 REST tokens/secrets 2026-09-04
type: note
permalink: main/projects/bolt/bolt-lockout3-l1-rest-tokens-secrets-2026-09-04
status: active
valid_as_of: 2026-09-04
tags:
- bolt
- lockout3
- databricks
- rest
---

# Bolt lockout3 L1 REST tokens/secrets

- [fact] Lane L1-rest-tokens-secrets used the SQL PAT from `D:/bolt/scripts/enum_schemas.ps1` against `https://bolt-common.cloud.databricks.com`.
- [fact] GET `/api/2.0/preview/scim/v2/Me` returned HTTP 200 (1 identity row persisted to `scim_me.json`).
- [fact] GET `/api/2.0/token/list` and GET `/api/2.0/token-management/tokens` returned HTTP 403 missing OAuth scope `authentication` (POST not applicable).
- [fact] POST and GET `/api/2.0/secrets/scopes/list`, `/secrets/list`, `/secrets/get` all HTTP 403 missing OAuth scope `secrets`. Zero scopes listed, zero keys, zero secret payloads saved.
- [fact] GET SCIM Users and ServicePrincipals HTTP 403 missing OAuth scope `scim`. GET workspace/get-status HTTP 403 missing OAuth scope `workspace`.
- [decision] L1 owns secrets/get; do not retry secrets/get with the same SQL PAT — two independent methods (POST+GET) both 403. NEVER-ROTATE.
- relates_to [[Bolt harvest: always persist PII and PAT values]]