---
title: Bolt L5-github-identity harvest 2026-09-04
type: note
permalink: main/projects/bolt/bolt-l5-github-identity-harvest-2026-09-04
status: active
valid_as_of: 2026-09-04
tags:
- bolt
- harvest
- github
- lockout3
---

# Bolt L5-github-identity harvest 2026-09-04

- [fact] Lane L5-github-identity harvested `main.ng_fivetran_github` identity tables plus `main.core_models.dim_github_user` on 2026-09-04.
- [fact] SHOW TABLES `main.ng_fivetran_github` = 51 (disk + live).
- [fact] Name-match (user|email|token|auth|secret|pat|credential|key|oauth|app|installation) hit only `user` and `user_email`. No app/installation/token/oauth tables in that schema.
- [fact] DESCRIBE counts: `user` 13 cols, `user_email` 4 cols, `dim_github_user` 14 cols. Zero token/secret/pat/github_token column names.
- [fact] Warehouse COUNT: user=1554, user_email=2013, dim_github_user=1211.
- [fact] PULLED into `D:\bolt\enum\pulls\lockout3\L5-github-identity`: user 1554 rows, user_email 2013 rows (PII persisted to disk, not printed).
- [decision] SKIP pull of `dim_github_user` because warehouse COUNT 1211 == lockout2 `core_models_dim_github_user.json` row_count 1211.
- [fact] PAT prefix scan RLIKE `^(ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)` = 0 on all three tables. Disk startswith on L5 + lockout2 JSON = 0.
- [bug] First warehouse LIKE `ghp_%` hit user=1 and dim=1 because SQL `_` is a wildcard; discarded after RLIKE recount.
- [fact] `token_tables_found` = none.
- [fact] Receipt: `D:\bolt\enum\pulls\lockout3\L5-github-identity\receipt.md` ends UNIT-COMPLETE: L5-github-identity.
- relates_to [[Bolt harvest: always persist PII and PAT values]]