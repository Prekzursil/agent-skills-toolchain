---
title: Cursor team-policy inference PEP V-005b 2026-08-28
type: note
permalink: main/research/cursor-team-policy-inference-pep-v-005b-2026-08-28
status: active
valid_as_of: '2026-08-28'
---

- [fact] ChatService StreamUnifiedChatWithTools enforces Bolt team modelAllowlist: claude-fable-5-thinking-high completed; claude-fable-5-thinking-max and thinking-xhigh fail with ERROR_MODEL_BLOCKED after HTTP 200 stream start.
- [fact] Aborting at response.created looks like a false 200; wait for assistant text or response.failed.
- [fact] There is no aiserver.v1.UserService. CreateUserApiKey is DashboardService (name/scopes/expires_at), not provider BYOK. Empty CreateUserApiKey mints a crsr_ key; accidental mint id 917983 was revoked.
- [fact] Provider BYOK secrets are local cursorAuth/azureApiKey and Bedrock keys. ValidateBedrockIamRole empty returns ERROR_NOT_LOGGED_IN. GetSessionToken destination PORTAL exists; not called.
- [decision] TM-004 does not upgrade to Critical; restriction is not UI-only.
- relates_to [[Cursor team-policy threat model]]
See also [[WHERE-map pointer]].
