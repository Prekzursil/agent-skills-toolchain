---
title: auth-A-mirror
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/auth-a-mirror
---

# CRCP auth-A-mirror implementation report

## Summary

Implemented `auth_mirror.py` as a standard-library-only, Windows-first module for ChatGPT Desktop cookie-path discovery, metadata-only SQLite inventory, locked-file VSS copying, user-bound OSCrypt/DPAPI decryption, controlled browser-import exports, CDP cookie formatting, and CLI-facing mirror functions.

The implementation treats cookie contents as secrets. Inventory output contains only host, name, path, flags, expiry, source path, and encrypted byte length. Decryption is denied unless `allow_decrypt=True`; secret-bearing exports are always refused beneath `/dbfs/tmp/crcp-auth-session/results/`. Public function reports contain counts and metadata, never cookie values.

The mirror reports `partial_without_nextauth` whenever `__Secure-next-auth.session-token` is absent. This matches the measured Desktop jar and makes clear that the exported Desktop cookies alone are not a complete ChatGPT web login.

## API surface

- `default_user_data_dir() -> Path`: resolves `%APPDATA%\Codex\web\Codex`; Linux requires an explicit `APPDATA` value instead of fabricating a Windows profile.
- `cookie_db_paths(user_data) -> list[Path]`: returns the measured primary and `codex-browser-app` partition cookie databases.
- `inventory_cookies(db_path) -> list[dict]`: reads metadata only and converts Chromium expiry timestamps to Unix time.
- `copy_via_vss(src, dest) -> Path`: creates a temporary `Win32_ShadowCopy` through PowerShell/CIM, copies the locked file, and deletes the shadow.
- `decrypt_cookie_value(encrypted_value, local_state, *, allow_decrypt=False) -> bytes | None`: unwraps the Local State key through `CryptUnprotectData`, decrypts Chromium `v10`/`v11` AES-GCM through Windows CNG, and supports legacy direct-DPAPI blobs.
- `export_cookies_json(...)` and `export_cookies_netscape(...)`: explicit-opt-in, caller-path import artifacts with a hard results-directory guard.
- `format_cdp_cookie(cookie_dict) -> dict`: produces `Network.setCookie` parameters.
- `format_edge_import_instructions() -> str`: gives value-free operator guidance for a separate Edge/CDP profile.
- `run_mirror_inventory() -> dict`: inventories available databases and returns counts, hosts, names, paths, missing paths, and honest status.
- `run_mirror_export(out_dir, *, decrypt=False) -> dict`: writes metadata JSON by default; when explicitly requested, writes local decrypted JSON outside the results tree and returns counts only.

## Windows notes

The live Desktop Cookies file is expected to be exclusively locked. A recognized sharing/SQLite-open failure causes inventory and decrypt reads to try `copy_via_vss`. Creating a VSS snapshot commonly requires elevation and working Windows VSS/CIM services. Failures are deliberately reduced to `VSS_REQUIRED` or `FILE_LOCKED` messages so PowerShell output and machine-specific context are not propagated.

DPAPI decryption must run under the same Windows user identity that owns the Desktop profile. Current Chromium `v10`/`v11` blobs use the DPAPI-unwrapped `Local State` key and Windows BCrypt AES-GCM. Legacy cookie blobs are sent directly to DPAPI. No Windows cookie paths beyond those recorded in the supplied discovery report are used.

For Edge import, use a separate controlled browser profile and a trusted local CDP client. Never place cookie exports in logs, shell history, tickets, or the CRCP results directory.

## Limits and honest gaps

- This job node is Linux, so actual Windows DPAPI, BCrypt, exclusive-lock, elevation, and VSS behavior could not be exercised here. Those paths are best-effort and fail closed.
- Future Chromium app-bound encryption formats beyond legacy DPAPI and `v10`/`v11` OSCrypt are not implemented.
- A VSS copy can fail because of policy, filesystem type, disabled services, or insufficient privilege; stopping Desktop and reading the closed database is preferable when operationally acceptable.
- Cookie mirroring cannot synthesize the missing NextAuth or Cloudflare clearance cookies. The measured Desktop jar therefore remains partial for stock ChatGPT web login; normal PKCE/web SSO is the completion path.
- Decrypted export JSON is intentionally an explicit local secret artifact. The caller is responsible for restrictive ACLs, short retention, and secure deletion.

## Self-test

Executed on Python 3.11/Linux with no network and no real credentials:

```text
python -m unittest discover -s /dbfs/tmp/crcp-auth-session/results -p 'test_auth_mirror.py' -v
Ran 7 tests in 0.094s
OK
```

Tests cover measured path construction, a synthetic Chromium Cookies SQLite fixture, timestamp conversion, metadata-only guarantees, missing-NextAuth status, explicit decrypt authorization, Linux DPAPI behavior, secret-output refusal, JSON export, CDP formatting, and metadata-only mirror export. Both deliverable Python files also pass `py_compile`.

UNIT-COMPLETE: auth-A-mirror