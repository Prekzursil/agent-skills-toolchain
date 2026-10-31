---
title: dbx_merge-B-write-sse
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-merge-b-write-sse
---

# CRCP merge report: write path / SSE

## Result

Integrated the existing `sse_contract` terminal classifier into the owned full replacement `write_path.py`. No `sse_api.py` was needed, and no source-tree module was modified.

## Wiring

- `write_path.post_conversation` now calls `sse_contract.classify_sse(status_code, full_response_text)` immediately after the HTTP response body is available.
- Contract verdicts are mapped at that boundary:
  - `COMPLETE` -> `status="SUCCESS"`, `ok=True`
  - `UNCERTAIN_ACCEPTED` -> `status="UNCERTAIN_ACCEPTED"`, `ok=False`
  - `ERROR` -> `status="FAILED"`, `ok=False`
- Transport state is independent of the terminal verdict through `http_ok` and `status_code`. This permits an HTTP 2xx response to remain failed or uncertain when terminal SSE evidence is absent or erroneous.
- `send_message` consumes the normalized result from `post_conversation` and exposes `ok`, `status`, `http_ok`, and `status_code` at the top level and in its attempt/response diagnostics.
- The legacy endpoint fallback is limited to transport-level failure (`http_ok=False`). An accepted-but-uncertain primary request is not reposted, avoiding a possible duplicate user message.
- Existing `success` remains as a compatibility alias of the terminal `ok` outcome.

## Preserved behavior

- Automatic Sentinel acquisition remains the last operation before the conversation POST; no init, conversation lookup, or conduit call was inserted after it.
- All HTTP opens continue through `http_secure.open_url`.
- Existing `sse_contract` imports and behavior remain untouched.
- The full response text is classified before the diagnostic `body_text` field is truncated.

## Validation

- Candidate file compiles with `python -m py_compile`.
- Existing `tests/test_sse_classify.py`: 7/7 passing.
- Direct `post_conversation` outcome matrix passed for complete, truncated, and explicit-error HTTP 200 SSE bodies, including separate transport fields.

## Residual risk

- Callers that previously interpreted `post_conversation()["status"]` as a numeric HTTP code must migrate to `status_code`; `status` now deliberately carries the requested terminal verdict.
- A connection-level exception other than `urllib.error.HTTPError` still propagates as it did before this merge.
- The classifier treats malformed SSE as `FAILED` according to `sse_contract`; this differs from the more tolerant `sse_validate.classify_sse_stream`, which remains available but is not used by the write path.
- No live authenticated POST was performed, so production token expiry, bot-defense behavior, and endpoint-specific stream variations remain operational risks.

UNIT-COMPLETE: merge-B-write-sse