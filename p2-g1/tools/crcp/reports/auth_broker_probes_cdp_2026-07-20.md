# Live probes + CDP + broker notes — 2026-07-20

See also: live_auth_probes_2026-07-20.json, desktop_cdp_cookies_2026-07-20.json

## Databricks secrets
- list-scopes: many scopes present including `codex-harness-prekzursil`, `jfrog-artifactory-secrets`, `anthropic`, `api_keys`, ...
- codex-harness-prekzursil keys: **auth_json** only

## Probe table (Bearer + ChatGPT-Account-Id)
| Endpoint | Status | Keys / notes |
|----------|--------|--------------|
| GET /api/auth/session | 200 | WARNING_BANNER only — **no NextAuth session** |
| GET /api/auth/providers | 200 | openai, openai-dev, openai-sidetron, openai-sidetron-dev |
| GET /api/auth/csrf | 200 | csrfToken |
| GET /backend-api/settings | 404 | detail Not Found |
| GET /backend-api/models | 200 | models[], categories[], default_model_slug=gpt-5-5 |
| POST /backend-api/accounts/check | 405 | Method Not Allowed |
| GET /backend-api/accounts/check | 403 | |
| GET /backend-api/accounts/check/v4-2023-04-27 | 200 | accounts, account_ordering |
| GET /backend-api/me | 200 | user object, orgs, email, client_id |
| platform.openai.com org users/projects | 200 HTML | SPA shell, not REST with this token |

## Desktop CDP
- Package path updated: OpenAI.Codex_26.715.7063.0
- Works with: `--remote-debugging-port=9222 --remote-allow-origins=*`
- Without allow-origins: WS handshake 403
- getAllCookies: 16 cookies; **no** next-auth.session-token; has _puid, oai-sc, CF

## Broker live run (port 9333)
- status: **API_AUTH_OK_NO_NEXTAUTH**
- cookies injected: 26/26 (has _puid, oai-sc; no next-auth session-token)
- page probes: session=WARNING_BANNER; me=200; models=200; csrf=200
- profile: %USERPROFILE%\.crcp\browser-broker-profile
- CLI: `python -m crcp auth broker --port 9333`
- Desktop CDP inventory: `python -m crcp auth broker --desktop-cdp-inventory --port 9222`
  (requires ChatGPT.exe --remote-debugging-port=9222 --remote-allow-origins=*)
