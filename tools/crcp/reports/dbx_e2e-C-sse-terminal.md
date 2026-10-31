---
title: dbx_e2e-C-sse-terminal
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-e2e-c-sse-terminal
---

# e2e-C-sse-terminal — SSE terminal classification for write path

## Summary

Implemented P0 terminal validation for ChatGPT conversation streams. HTTP acceptance is now tracked independently from turn completion. A response is `SUCCESS` only when it contains `[DONE]` or a finished assistant message and contains no explicit error. Truncated, empty, or malformed responses are `UNCERTAIN_ACCEPTED`; explicit errors are `FAILED` and take precedence over terminal markers.

`send_message` now returns top-level `status`, `http_ok`, and `ok` fields. `ok` is true only for `SUCCESS`. The existing `success` field is retained as a compatibility alias of `ok`. Legacy-path fallback remains limited to HTTP failure, so an HTTP 200 uncertain response is not posted a second time.

## File list

- `sse_validate.py` — standalone stdlib-only SSE/event classifier with verdict constants.
- `write_path.py` — full replacement of the original module, wired to classify every HTTP-success response stream and propagate the verdict.
- `e2e-C-sse-terminal.md` — implementation and validation report.

## Wiring notes

- Install `sse_validate.py` beside `write_path.py` in the `crcp` package so the relative import `.sse_validate` resolves.
- `post_conversation` preserves numeric HTTP status in `status`, exposes `http_ok`, and adds `sse_status`; its `ok` is terminal-success-only.
- `send_message` exposes the SSE verdict as top-level `status`; nested attempts use `http_status` for numeric HTTP codes and `status` for SSE verdicts.
- Sentinel acquisition and PoW remain the final operation immediately before the first conversation POST. No network work was inserted between sentinel acquisition and POST.

## Self-test notes

- Python syntax compilation passed for both delivered modules.
- Classifier fixtures passed for `[DONE]`, `[DONE]` without blank SSE separators, finished assistant, truncated stream, malformed stream, empty stream, SSE error event, and error-plus-terminal precedence (8 fixtures).
- Mocked `post_conversation` checks passed for complete, truncated HTTP 200, and explicit-error HTTP 200 responses.
- Mocked `send_message` confirmed HTTP 200 truncated output yields `http_ok=True`, `status=UNCERTAIN_ACCEPTED`, `ok=False`, and exactly one POST attempt.
- Tests used only synthetic data and made no external requests.

UNIT-COMPLETE: e2e-C-sse-terminal