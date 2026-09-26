---
title: research Cursor team-policy control validation 2026-08-28
type: report
permalink: main/research/research-cursor-team-policy-control-validation-2026-08-28
status: active
valid_as_of: '2026-08-28'
---

# research Cursor team-policy control validation 2026-08-28

- [fact] V-001: `newModelDefault=ENABLED` is independent of frozen `parameterRestrictions.allowedValues`. Update appending xhigh/max → 401 ERROR_NOT_LOGGED_IN (not 400). GET has no checksum field.
- [fact] V-001.3: Cloud Agents `GET /v1/models` for claude-fable-5 / claude-opus-5 effort is only low/medium/high. grok-4.6 and gpt-5.6-luna still list xhigh/max. Agents is not a Claude-Max bypass.
- [fact] V-002: all UpdateTeamAdminSettings identity variants (no auth, bad JWT, tampered sig, teamId 0/1, no checksum, empty allowlist) → identical 401 ERROR_NOT_LOGGED_IN. No 400; no TOCTOU split. ListTeamApiKeys with same JWT → 401 ERROR_UNAUTHORIZED "User not authorized for this team" (different string).
- [fact] V-003: SetModelAccess / UpdateModelPolicy / AddModelToAllowlist / SetParameterRestriction → 404. Org group allowlist update → 401 ERROR_NOT_LOGGED_IN. Create/Delete spray not fired.
- [fact] V-004: byokDisabled false; ListUserApiKeys 200; CreateUserApiKey not called. No MEMBER RPC to set BYOK model tier.
- [fact] V-006: session JWT HS256; claims have type=session, no role, no teamId. alg:none not sent. Tampered payload+old sig → 401.
- [decision] JWT alg:none, live state.vscdb edits, Cloud Agent create, and DashboardService write-spray remain out of scope.
- relates_to [[research Cursor team-policy threat model 2026-08-28]]

Updated: `C:/Users/Prekzursil/Cowork/output/cursor-team-policy-threat-model.md`