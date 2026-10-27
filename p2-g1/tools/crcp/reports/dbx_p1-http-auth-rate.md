# P1 HTTP authentication and rate limiting

## Summary

Implemented a production-oriented mutation boundary for the CRCP live bridge HTTP server.

- Every mutating HTTP method (`POST`, `PUT`, `PATCH`, and `DELETE`) passes through one shared authorization and throttling path. This protects the existing `POST /poll-now` route and fails closed for future write routes.
- Shared-secret authentication accepts `CRCP_HTTP_TOKEN` or reads the secret from the path in `CRCP_HTTP_TOKEN_FILE`. The environment value takes precedence. Secret values are never logged or returned.
- Token comparison uses a constant-time comparison. A missing, empty, or unreadable token configuration disables mutations with HTTP 503.
- `CRCP_HTTP_OPEN=1` explicitly permits unauthenticated mutations for local development. It does not disable rate limiting and should not be used in a deployed environment.
- Per-direct-client token buckets default to 6 requests per minute. Set a positive finite `CRCP_HTTP_RATE_LIMIT_PER_MINUTE` to override the default. Rejections return HTTP 429 and `Retry-After`.
- Client identity comes from the socket peer rather than spoofable forwarding headers. Limiter state is locked for the threaded server and capped at 4,096 client records.
- Read-only `GET /livez`, `/readyz`, `/metrics`, `/health`, `/status`, and `/conversations` remain unauthenticated. Responses use `Cache-Control: no-store`.

## File list

- `live_bridge.py` — full replacement CRCP module, 549 lines; SHA-256 `d28ce42af3f54b017bb083389c05e3c9dbd5ce08f736e8c56fb665cbef1de197`.
- `p1-http-auth-rate.md` — implementation, wiring, and validation report.

## Wiring into existing modules

Replace `crcp/live_bridge.py` with the delivered `live_bridge.py`. Its existing public entry point, `run_live_bridge`, and the existing `LiveBridgeService` polling behavior remain available.

`LiveBridgeService.__init__` now constructs `HttpMutationPolicy.from_environment()` by default and also accepts an injected `http_mutation_policy` for deterministic tests or embedding. `_start_http()` applies that policy before dispatching all supported mutation methods. No changes to callers are required.

Deployment configuration:

1. Prefer setting `CRCP_HTTP_TOKEN` through the platform's secret injection mechanism, then send the same value only in the `X-CRCP-Token` request header.
2. Alternatively, set `CRCP_HTTP_TOKEN_FILE` to a narrowly permissioned text file containing the token.
3. Optionally set `CRCP_HTTP_RATE_LIMIT_PER_MINUTE`; the default is 6.
4. For local development only, `CRCP_HTTP_OPEN=1` opts into unauthenticated mutations. With neither a token nor this explicit opt-in, mutations are refused.

## Self-tests

- `python -m py_compile live_bridge.py` — passed.
- Policy tests — 12 assertions passed: fail-closed default, correct/missing/incorrect header behavior, token-file loading, explicit local-open mode, and default seventh-request throttling.
- Loopback HTTP integration — 9 assertions passed: unauthenticated metrics, disabled mutation response, missing-token rejection, authenticated poll, authenticated unsupported write method, per-client allowance, and HTTP 429 after exhaustion.
- Tests used synthetic values only and did not invoke a live poll or expose credentials.

UNIT-COMPLETE: p1-http-auth-rate
