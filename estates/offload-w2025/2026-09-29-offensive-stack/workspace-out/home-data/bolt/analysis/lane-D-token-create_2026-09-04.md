# Lane D — POST /api/2.0/token/create — 04.09.2026

UNIT-COMPLETE: lane-D

Host: https://bolt-common.cloud.databricks.com
Endpoint: POST /api/2.0/token/create
Docs: https://docs.databricks.com/api/workspace/tokens/create
Body: lifetime_seconds=300, comment=estate-lockout-probe-do-not-use-if-403
PATs: $TOK / $TOK2 from D:\bolt\scripts\dbx_crossws.ps1 (values not printed). NEVER-ROTATE. Mint is not rotation.
API scope required: authentication.

## HTTP

| label | artifact | HTTP | error_code | message class | token_value key |
|---|---|---:|---|---|---|
| ngo ($TOK) | D:\bolt\enum\pulls\lockout3\parent\rest_recheck\token_create_ngo.json | **403** | 403 | missing-required-scopes (authentication) | absent |
| alvaro ($TOK2, second independent signal only) | D:\bolt\enum\pulls\lockout3\parent\rest_recheck\token_create_alvaro.json | **403** | 403 | missing-required-scopes (authentication) | absent |

ReqId ngo: 837f95c9-c4f2-4a80-bae1-6619add4c1c4
ReqId alvaro: 17712298-46cb-4b53-bf38-d497af683fed

No further POSTs.

## Verdict

**NO-GO** — HTTP 403 class on both SQL PATs. Mint did not succeed (token_value key absent). GO would have required HTTP 200 and token_value present.

Matches prior GET /api/2.0/token/list 403 (missing authentication scope) on the same PATs.
