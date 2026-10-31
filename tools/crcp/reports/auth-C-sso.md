---
title: auth-C-sso
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/auth-c-sso
---

# auth-C-sso implementation report

## Summary

Implemented a stdlib-only PKCE/OIDC authorization-code flow for the CRCP
Codex/API authentication rail. The module uses the measured OpenAI issuer,
authorization endpoint, token endpoint, public client family, S256 PKCE, and
the documented OpenID/offline scopes. Environment overrides are supported via
`CRCP_OAUTH_CLIENT_ID` and `CRCP_OAUTH_REDIRECT_URI`.

The local callback listener binds only to an HTTP loopback address, matches the
configured callback path, suppresses request logging, requires exactly one code
and state value, and compares state in constant time. Token exchange uses
public-client body parameters and sends no client secret. Provider error bodies
are not exposed because they can echo sensitive data.

High-level login results contain token presence, lengths, and expiry metadata
only. No token, JWT, refresh-token, or cookie value was written to this report.

## API surface

- OIDC constants: `ISSUER`, `AUTHORIZE_URL`, `TOKEN_URL`,
  `DEFAULT_CLIENT_ID`, `DEFAULT_SCOPES`, and `DEFAULT_REDIRECT_URI`.
- PKCE/state: `generate_code_verifier`, `code_challenge_s256`,
  `generate_state`, and `generate_nonce`.
- Authorization: `build_authorize_url`, `parse_callback_query`,
  `start_callback_server`, and `exchange_code_for_tokens`.
- Controlled profile: `prepare_profile_dir` creates an isolated directory and
  applies owner-only POSIX permissions where supported. It intentionally does
  not copy the locked Desktop profile or any credentials.
- Safe reporting: `export_auth_summary` emits presence, value lengths, and JWT
  `exp` metadata only.
- Explicit persistence: `save_token_bundle` is default-off, uses an atomic
  owner-only file, carries a sensitive-data warning, and refuses destinations
  inside `/dbfs/tmp/crcp-auth-session/results`.
- Orchestration: `run_sso_login` supports browser callback login, URL-return
  mode for a display-less host, and later offline code completion when the
  continuation verifier is supplied. Completed results expose only the safe
  authentication summary.

## Windows notes

All operator paths use `pathlib.Path`, `Path.home`-compatible expansion, and
caller-supplied locations; no Windows filesystem path was invented. POSIX mode
bits are best-effort on Windows because Windows ACLs do not map directly to
`chmod`. This unit performs no cookie decryption. If a separate mirror unit
decrypts Chromium material on Windows, DPAPI can be accessed through
`ctypes`/`crypt32` under the same Windows user context.

## Limits and honest gaps

- This flow does not fabricate `__Secure-next-auth.session-token` or any other
  NextAuth cookie.
- Bearer credentials are for the Codex/API plane. A stock ChatGPT web UI may
  still require its own interactive session or a separately validated cookie
  bridge.
- OIDC discovery has no `client_credentials` grant; this module does not offer
  one.
- URL-return mode must return the PKCE continuation verifier to its in-memory
  caller so a later code exchange can prove possession. The operator must treat
  that short-lived verifier as sensitive and avoid logs.
- The default browser launcher cannot force a particular browser user-data
  directory. `prepare_profile_dir` supplies the safe directory primitive for a
  caller that launches a controlled browser explicitly.
- No live authorization or token exchange was performed on this Linux job node.

## Self-test

`python -m py_compile` succeeded for the module and test file. Offline unit
tests passed 4/4, covering PKCE length/format, required authorize URL fields,
state-mismatch rejection, and a mocked token exchange with no network access.

UNIT-COMPLETE: auth-C-sso