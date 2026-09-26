---
title: research Cursor team-policy threat model 2026-08-28
type: report
permalink: main/research/research-cursor-team-policy-threat-model-2026-08-28
status: active
valid_as_of: '2026-08-28'
---

# research Cursor team-policy threat model 2026-08-28

- [fact] MEMBER write to `UpdateTeamAdminSettings` is denied (401 ERROR_NOT_LOGGED_IN). The effort cap test failed closed; this is the PEP holding, not a missing knob.
- [fact] Highest observed issues are MEMBER *reads*: full `GetTeamAdminSettings` blob (TM-002) and `GetTeamMembers` 1911 emails (TM-003). Catalog-vs-allowlist drift (TM-004) explains the Max grey without an OWNER click.
- [decision] HexStrike stays off `api2.cursor.sh` / `api.cursor.com`. Team-scoped authenticated IDE RPCs are not ownership of Cursor production. No owner outreach (operator: would collapse the test).
- [decision] Do not attempt further real-team policy writes. Empty/nudge 401s were sufficient.
- relates_to [[research Cursor effort cap cannot be changed by this seat 2026-08-28]]
- relates_to [[research Cursor effort restrictions vs user API key 2026-08-28]]

File: `C:/Users/Prekzursil/Cowork/output/cursor-team-policy-threat-model.md`