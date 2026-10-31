---
title: dbx_p1-auth-snapshot
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-p1-auth-snapshot
---

# P1 Auth Snapshot

## Summary

Implemented immutable, redaction-safe credential snapshots for the CRCP ChatGPT bridge. The bridge is a token consumer only: it reads credentials written by the primary auth owner and **never performs OAuth refresh**.

On each request, the bridge uses one immutable snapshot. If a request receives HTTP 401, it compares the current `auth.json` nanosecond mtime with the snapshot mtime. It reloads and retries exactly once only when the file changed. An unchanged mtime, a second 401, or exhausted authentication retry degrades with a sanitized `BridgeDegradedError`. HTTP response bodies are not included in errors.

## Files

- `credential_snapshot.py` — new complete module containing frozen `CredentialSnapshot`, opaque `CredentialHandle`, stable auth-file loading, expiry metadata, safe public status, and `is_stale_mtime`.
- `bridge.py` — complete bridge module wired to credential snapshots and conditional reload-on-401 behavior.
- `p1-auth-snapshot.md` — this implementation and verification report.

No `auth.py` replacement is required; the bridge no longer uses auth helpers to retain raw credential fields.

## Wiring into existing modules

- `bridge.ChatGPTBridge.reload()` calls `load_from_auth_json()` and rejects an expired snapshot without attempting refresh.
- `bridge.ChatGPTBridge._maybe_reload()` retains proactive file-change pickup between requests using `is_stale_mtime()`.
- Request headers are created only through the opaque credential handle. The snapshot dataclass representation excludes the handle, and `public_status()` emits presence flags and metadata only.
- The 401 handler checks the snapshot mtime, reloads only on a changed file, and makes at most one retry.
- Existing `list_conversations`, `get_conversation`, `me`, export, and pack entry points retain their interfaces.
- The assembled bridge preserves the result tree's hardened `http_secure.open_url` transport integration.

## Self-tests

Executed isolated stdlib-only tests with temporary synthetic credentials:

- Python compilation succeeded for both delivered modules.
- Snapshot loading captured auth mode, filesystem mode, nanosecond mtime, and expiry metadata.
- Frozen snapshot and opaque handle representations did not contain the synthetic credential marker.
- Public status serialization did not contain the synthetic credential marker.
- `is_stale_mtime()` returned false for the known file and true after an mtime change.
- HTTP 401 plus changed mtime reloaded credentials and succeeded on exactly one retry.
- HTTP 401 plus unchanged mtime raised `BridgeDegradedError` after one request.
- Sanitized degradation errors contained no synthetic credential marker.
- Static scan found no OAuth endpoint, refresh operation, refresh credential handling, or response-body echo in the delivered auth-snapshot modules.

UNIT-COMPLETE: p1-auth-snapshot