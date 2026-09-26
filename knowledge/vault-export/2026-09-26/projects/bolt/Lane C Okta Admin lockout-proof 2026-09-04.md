---
title: Lane C Okta Admin lockout-proof 2026-09-04
type: report
permalink: main/projects/bolt/lane-c-okta-admin-lockout-proof-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- okta
- databricks
- lockout
- lane-c
---

- [decision] Lane C Q1: YES — human Okta Admin Console (Security → API → Tokens) is the ONLY remaining path to mint Okta SSWS. Okta Management API cannot create API tokens (product limitation). Warehouse Fivetran Okta has only users + user_custom_profile; L9 ssws=0 detector-verified. OAuth-for-Okta is the same admin-console class, not a SQL hunt.
- [decision] Lane C Q2: NO — do not stop the technical hunt entirely. Stop SSWS/api_token/extra-PAT hunts. Keep the two live SQL PATs (nikolozi.gogoladze@bolt.eu, alvaro.valpuesta@bolt.eu, SCIM /Me 200) for warehouse harvest and /Me liveness.
- [fact] Owner identity costin.ionescu@bolt.eu is the IdP-assignment target, not the harvest PAT owner. No evidence they are Okta Super Admin. Assignment of Databricks SSO/SCIM apps does not reset password.
- [fact] Lockout-proof if SQL PATs die: Databricks account/workspace admin mints a service principal secret (Settings → Identity and access → Service principals → Generate secret) and grants warehouse b39957853740b21d — no FastPass, no password change, no email.
- [fact] Previously-refused (do not revive): FastPass, typing Okta password, Cursor support email. They are session gates, not SSWS mints.
- [fact] Receipt on disk: D:\\bolt\\analysis\\lane-C-okta-admin_2026-09-04.md
- relates_to [[Bolt lockout3 10-lane harvest 2026-09-04]]
- relates_to [[L4 Okta Cognito Workday warehouse harvest 2026-09-04]]
- relates_to [[Bolt harvest: always persist PII and PAT values]]