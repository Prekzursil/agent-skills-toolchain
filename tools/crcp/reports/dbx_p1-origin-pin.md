---
title: dbx_p1-origin-pin
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-p1-origin-pin
---

# P1 origin pin

## Summary

Implemented a stdlib-only restricted HTTP transport for CRCP's credentialed ChatGPT requests. The transport permits only `chatgpt.com`, `ab.chatgpt.com`, and `auth.openai.com`; requires HTTPS on port 443; rejects URL user information; disables urllib's automatic redirects; and validates every redirect destination before opening it. Same-origin redirects retain request headers. Allowed cross-origin redirects strip Authorization, proxy authorization, cookies, and the ChatGPT account identifier before proceeding. Redirect method and entity-body handling follows the usual 301/302/303/307/308 behavior, with a five-hop limit.

## Files

- `http_secure.py` — new secure opener, URL policy, explicit redirect handling, and `URLSecurityError`.
- `bridge.py` — full patched module using `open_url` for the backend API request path.
- `write_path.py` — full patched module using `open_url` for conversation init, prepare, and post paths.
- `p1-origin-pin.md` — this implementation report.

All files are under `/dbfs/tmp/crcp-e2e-full/results/`.

## Wiring into existing modules

`bridge.py` imports `.http_secure.open_url` and routes `ChatGPTBridge._request` through it with the existing 45-second timeout. `write_path.py` imports the same helper and routes `conversation_init`, `conversation_prepare`, and `post_conversation` through it while preserving their existing 30/30/120-second timeouts and HTTP error handling. Request construction and response parsing are otherwise unchanged.

The three Python files are complete module files intended to be installed together in the `crcp` package.

## Self-tests

- `py_compile` passed for `http_secure.py`, `bridge.py`, and `write_path.py`.
- Offline simulated transport tests passed for rejecting HTTP, rejecting a non-allowlisted host, rejecting a non-443 port, retaining Authorization on a same-origin redirect, stripping Authorization on an allowed cross-origin 307 redirect, retaining a 307 POST body, and converting a 303 POST to a bodyless GET.
- Package import/wiring smoke test passed with the patched files installed into a temporary copy of `crcp`; both request modules resolved the shared secure opener.
- Source comparison confirmed the request modules contain only the secure-opener import and call-site substitutions for this unit.
- No live endpoint calls were made and no credentials were read or emitted by the tests.

UNIT-COMPLETE: p1-origin-pin