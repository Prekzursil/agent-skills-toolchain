---
title: auth-B-deeplink
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/auth-b-deeplink
---

# auth-B-deeplink — implementation report

## Summary

Implemented the standalone `auth_deeplink.py` module for building and opening
ChatGPT Desktop `codex://` deep links. The implementation uses only the Python
standard library, performs URL encoding without embedding credentials, and
returns structured launch results instead of requiring callers to handle OS
launcher exceptions.

The deliverables are:

- `auth_deeplink.py`
- `test_auth_deeplink.py`
- `auth-B-deeplink.md`

No files owned by other units were written.

## API surface

### `build_codex_deeplink(*, path: str = "", query: dict | None = None) -> str`

Builds a URL whose scheme is always `codex`. Leading path slashes are
normalized, unsafe path characters are percent encoded, and query parameters
are encoded with `urllib.parse.urlencode`. Sequence values use repeated query
parameters.

Examples:

- Empty: `codex://`
- Open: `codex://open`
- Conversation: `codex://chat?conversation_id=abc-123`

### `open_deeplink(url: str) -> dict`

Validates that the URL uses the `codex` scheme and asynchronously hands it to
the platform launcher. The result contains `ok`, `url`, and `method`; a failed
request also contains a metadata-only `error`. Exception messages are not
copied into the result, preventing command details or query values from leaking
through diagnostics.

### `describe_protocol_registration() -> dict`

Reports the measured discovery facts: `codex://` is registered by the Windows
MSIX AppxManifest, `chatgpt://` is not registered, and deep links open the
packaged app without transporting OAuth credentials or establishing a web
session.

### `run_deeplink_cli(action, **kwargs) -> dict`

Provides structured dispatch for `status`, `build`, and `open`. Unsupported
actions and missing/invalid arguments return `ok: false` with a safe error.

## Windows notes

On Windows, opening first uses `os.startfile`, which delegates to the registered
ShellExecute protocol handler. A direct `ShellExecuteW` call through
`ctypes`/`shell32` is the fallback. This implementation does not assume or
fabricate a Windows installation path.

On macOS it invokes `open`; on Linux it invokes `xdg-open`. Launcher handoff is
asynchronous, so `ok: true` confirms OS acceptance only, not successful
navigation inside Desktop.

## Limits and honest gaps

- Only `codex://` was observed as registered on the measured Windows MSIX
  installation. `chatgpt://` is deliberately not accepted.
- Deep links are app navigation hints. They do not carry OAuth tokens and do
  not authenticate a browser or create a ChatGPT web session.
- The Linux job node cannot verify the installed Windows MSIX handler or its
  application-level routing behavior.
- No GUI launcher was invoked during self-test.

## Self-test

Executed from `/dbfs/tmp/crcp-auth-session/results`:

```text
python -m unittest -v test_auth_deeplink.py
python -m py_compile auth_deeplink.py test_auth_deeplink.py
```

Result: all 9 unit tests passed, and both Python files compiled successfully.
Tests cover required examples, path normalization, Unicode/path quoting, query
quoting, repeated query values, empty queries, and the CLI build action.

UNIT-COMPLETE: auth-B-deeplink