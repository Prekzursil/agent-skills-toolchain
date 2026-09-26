---
title: Bolt L7-token-describe harvest 2026-09-04
type: note
permalink: main/projects/bolt/bolt-l7-token-describe-harvest-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- bolt
- harvest
- lockout3
---

- [fact] Lane L7-token-describe finished 2026-09-04 against main.ng_public on warehouse b39957853740b21d. Artifacts: D:/bolt/enum/pulls/lockout3/L7-token-describe/receipt.md and census.json.
- [fact] tables_described=15 (3 new DESCRIBE + 12 reused). Hunt needles api/key/secret/jwt/oauth/pat/dapi/scim/device_token: 3 api-log tables described; 20 pat substring hits were dispatch/path noise.
- [fact] token-value tables (names only): one_time_password (otp), one_time_password_verify_log (otp), user_unsubscribe_token (token), driver_session_history_session (session_key). business_business_admin_user_auth_refresh_token and payment_user_auth_token have no token-value string column.
- [fact] This lane pulled 40000 rows: 20000 session_key from driver_session_history_session; 20000 token from user_unsubscribe_token (v2; 14-day window returned 0). OTP tables skipped (already at 20k cap on disk).
- [decision] Keep persist-values-to-disk for lockout recovery; never print cells. NEVER-ROTATE.
- relates_to [[Bolt harvest: always persist PII and PAT values]]
