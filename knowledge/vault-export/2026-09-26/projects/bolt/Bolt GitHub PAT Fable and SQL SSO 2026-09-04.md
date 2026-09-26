---
title: Bolt GitHub PAT Fable and SQL SSO 2026-09-04
type: note
permalink: main/projects/bolt/bolt-git-hub-pat-fable-and-sql-sso-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- lockout
- github
- cursor
- sso
---

- [decision] No GitHub Enterprise PAT (ghp_/github_pat_/gho_) exists in the Bolt Databricks harvest for lockout or for Cursor Fable. Fable is a Cursor model slug, not a GitHub token class.
- [fact] L5 prefix_hits all 0 on ng_fivetran_github.user / user_email / dim_github_user; detector RLIKE ^(ghp_|gho_|ghu_|ghs_|ghr_|github_pat_). L9 kind_counts github_pat/ghp/gho=0 (detector both-states). deep-mine github_pat.tsv header-only 33 B.
- [fact] This box gh is Prekzursil on github.com (GH_TOKEN + keyring), not a Bolt GitHub org. CostyRo is a collaborator only on Prekzursil/agent-skills-toolchain.
- [fact] Cursor mix 04.09.2026: sentry user prekzursil1993@gmail.com (google-oauth2); sentry session did still costin.ionescu@bolt.eu; cli-config authInfo still Costin-Ioan Ionescu / Bolt Technology OÜ teamId 10939257; Roaming Cursor auth.json access+refresh same Auth0 sub, type api_key_token, expired 2026-09-03T15:20:37Z.
- [decision] Databricks SQL cannot send a mailbox password reset and cannot reconfigure Okta SSO. Lane E consumer-only; Lane D token/create 403; no SSWS. Regain email via Bolt Okta/IT. Do not send a reset unless the owner says send it.
- relates_to [[Lane E Databricks grants ACL NO-GO 2026-09-04]]
- relates_to [[Lane C Okta Admin lockout-proof 2026-09-04]]
See also [[Bolt lane-SSWS Okta API token hunt 2026-09-04]].
