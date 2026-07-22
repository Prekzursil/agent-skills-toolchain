# auth-D-cli — CLI wiring for auth subcommands

## Summary

Implemented a full replacement `crcp.__main__` that preserves the existing auth status/watch, health, liveness/readiness, ChatGPT, bus, inbox, publish, and version commands while adding machine-oriented session tooling beneath `crcp auth`.

New command tree:

- `auth mirror [--user-data PATH] [--json] [--export DIR] [--decrypt]`
- `auth deeplink build [--path PATH] [--query KEY=VAL ...]`
- `auth deeplink open URL`
- `auth deeplink status`
- `auth sso login [--redirect-uri URI] [--print-url] [--code CODE] [--timeout N]`
- `auth sso authorize-url [--redirect-uri URI]`

JSON is the default for the new commands. Successful results return 0, operational failures reported by sibling modules return 1, and parser/configuration/integration errors return 2. Unexpected runtime failures return 1 with details suppressed so an upstream exception cannot echo credentials.

## API surface

The module retains `build_parser()` and `main(argv=None)`. New command handlers are:

- `cmd_auth_mirror`
- `cmd_auth_deeplink_build`, `cmd_auth_deeplink_open`, `cmd_auth_deeplink_status`
- `cmd_auth_sso_login`, `cmd_auth_sso_authorize_url`

Sibling imports are lazy. Missing modules or expected symbols produce a clear JSON configuration error instead of preventing `crcp --help` or unrelated commands from loading. The mirror adapter honors `--user-data` even with the current no-argument sibling entrypoints by applying a scoped override to their default-directory resolver and restoring it immediately.

Terminal JSON passes through recursive credential redaction. Token, JWT, cookie value, encrypted value, authorization-code, client-secret, and PKCE-verifier fields are never emitted. Credential-like query parameters in returned URLs are also redacted.

## Windows notes

The CLI passes `Path` objects to the mirror helpers and does not hard-code a Windows drive or job-node path. With no override, the sibling mirror module resolves the measured Desktop user-data location from `%APPDATA%` and handles its two measured cookie databases. `--decrypt` is accepted only with `--export`; Windows DPAPI/VSS behavior remains owned by `auth_mirror.py`.

`auth deeplink open` delegates platform launch behavior to `auth_deeplink.py`. Only `codex://` is treated as registered by that module; the CLI does not claim `chatgpt://` support.

Interactive SSO delegates browser and callback handling to `auth_sso.py`. For a two-invocation display-less flow, generate a PKCE verifier outside terminal output, place it in `CRCP_OAUTH_CODE_VERIFIER` for both `--print-url` and later `--code` invocations, and keep it out of shell history. The CLI forwards it but always redacts it. `CRCP_OAUTH_REDIRECT_URI` and `CRCP_OAUTH_CLIENT_ID` remain supported by the sibling implementation.

## Limits and honest gaps

- This Linux job node cannot validate Windows protocol activation, DPAPI, VSS, or the exclusive lock behavior of a live Desktop cookie database.
- No OAuth exchange, browser launch, callback listener, or other network action was used in self-tests.
- `auth sso authorize-url` is explicitly a URL preview: its generated verifier is intentionally neither printed nor persisted, so callers should use `auth sso login --print-url` with a securely supplied `CRCP_OAUTH_CODE_VERIFIER` for a completable offline flow.
- CLI wiring cannot create the missing `__Secure-next-auth.session-token` or `cf_clearance`. Deeplinks do not carry OAuth credentials, and bearer SSO tokens do not by themselves establish a ChatGPT web-cookie session.
- The public OIDC path is authorization-code plus refresh-token with PKCE S256; there is no client-credentials fallback.

## Self-test

`python -m unittest discover -v -s /dbfs/tmp/crcp-auth-session/results -p 'test_auth_cli_wire.py'`

Result: 8 tests passed. Coverage includes all new nested parsers and options, existing auth/health/ChatGPT registration, auth help, missing-sibling JSON errors, malformed query handling, and output redaction. An assembled-package smoke test also passed for:

- `python -m crcp auth --help`
- `python -m crcp auth deeplink build --path chat --query conversation_id=example`
- `python -m crcp auth mirror --user-data <empty-profile>` (metadata-only, `not_found`)
- `python -m crcp auth sso login --print-url --redirect-uri <local-callback>` (no network; verifier redacted)

UNIT-COMPLETE: auth-D-cli
