---
title: L4 Okta Cognito Workday warehouse harvest 2026-09-04
type: note
permalink: main/projects/bolt/l4-okta-cognito-workday-warehouse-harvest-2026-09-04
status: active
valid_as_of: '2026-09-04'
---

- [fact] Lane L4-okta-cognito-workday enumerated bolt-common warehouse b39957853740b21d on 04.09.2026.
- [fact] main.ng_fivetran_okta and main.uc_fivetran_okta each have only 2 tables: users, user_custom_profile. No api_token, tokens, oauth_tokens, factors, or authenticator tables. SHOW TABLES LIKE *token*|*oauth*|*factor*|*api_token*|*secret*|*otp*|*authenticator* returned 0 rows.
- [fact] main.ng_fivetran_okta_spark does not exist; hive_metastore.ng_fivetran_okta_spark has 0 tables.
- [fact] main.uc_fivetran_okta.users has column credentials_password_hash_value; already pulled to lockout2 (6331 rows / 54 cols). main.ng_fivetran_okta.users (10372 rows / 19 cols) has no hash column. Users tables were not rewritten.
- [fact] user_custom_profile is a 5-col KV store; 52 distinct attribute names, 0 token-like names. Prior pull lockout/okta_profile.json has 86016 rows.
- [fact] main.ng_fivetran_cognito is Cognito Forms GRC (29 tables: assessment, disputes, warehouse inspection forms), not AWS Cognito IdP. 0 token/otp/secret columns after DESCRIBE.
- [fact] main.ng_fivetran_workday has employees + fivetran_audit only; employees has PII name/email cols, 0 token cols. Workday peopleanalytics worker_collective_agreement_factor is an HR factor table (USE SCHEMA denied).
- [fact] Databricks secrets/scopes/list HTTP403 (missing secrets scope). Unity Catalog tables list HTTP403.
- [decision] L4 new warehouse pulls = 0 rows; hunt closed for api_token/tokens/oauth_tokens in these schemas.
- relates_to [[Bolt harvest: always persist PII and PAT values]]
See also [[bolt-cred-audit verdict 2026-09-04]].
