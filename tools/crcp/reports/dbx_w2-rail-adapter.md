---
title: dbx_w2-rail-adapter
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-w2-rail-adapter
---

# W2 rail adapter

## Summary

Implemented a production-oriented rail facade for ChatGPT without changing the
read-only CRCP source tree. The adapter provides a stable structural protocol,
normalizes conversation listings into rail events, preserves complete source
payloads on fetch, delegates explicit writes to the existing owner-authorized
write path, and returns bounded metadata-only health results.

The default ChatGPT bridge is created lazily. A missing or expired local auth
file therefore makes `health()` return `UNAVAILABLE` instead of preventing the
adapter registry from loading. Health errors report only the exception class;
exception text and HTTP response bodies are not exposed.

## File list

- `rails/base.py` — runtime-checkable `RailAdapter` protocol with
  `list_events`, `fetch`, optional-capability `send`, and `health`.
- `rails/chatgpt.py` — `ChatGPTRail` facade with input validation, normalized
  read results, lossless fetch payloads, lazy dependencies, injectable fixture
  seams, explicit write delegation, and secret-safe health handling.
- `rails/__init__.py` — package exports for `RailAdapter` and `ChatGPTRail`.
- `w2-rail-adapter.md` — implementation and verification report.

## Wiring into existing modules

Install the `rails` directory as `crcp/rails`. Its relative imports then bind
to the existing modules without modifying them:

- `ChatGPTRail.list_events()` calls
  `crcp.bridge.ChatGPTBridge.list_conversations()` and returns a generic
  `events` page.
- `ChatGPTRail.fetch()` calls
  `crcp.bridge.ChatGPTBridge.get_conversation()` and wraps the untouched
  conversation object in `payload`.
- `ChatGPTRail.send()` lazily imports and delegates to
  `crcp.write_path.send_message()`. The adapter does not call this path from
  polling or health checks; the existing private-web write remains manual and
  experimental.
- `ChatGPTRail.health()` calls `ChatGPTBridge.me()` as a live read/auth probe.
  It does not expose identity content, credentials, local paths, exception
  messages, or HTTP bodies.
- `crcp.live_bridge` is intentionally unchanged. It can adopt this facade in a
  later wiring change while its current bridge behavior remains intact.

Read-only rail implementations can conform to the unified protocol by raising
`NotImplementedError` from `send()` and returning `writable: false` from
`health()`.

## Self-tests

Executed on the Linux Databricks job node using the unpacked CRCP package plus
the result directory as the `crcp` package extension path:

- `python -m py_compile` succeeded for all three Python modules.
- Verified `ChatGPTRail` satisfies the runtime-checkable `RailAdapter` protocol.
- Verified paging arguments and normalized event fields.
- Verified fetch trims/forwards the event ID and retains the complete payload.
- Verified send delegates only the documented non-secret arguments.
- Verified ready health output and unavailable health output.
- Verified an exception message containing sensitive diagnostic text is absent
  from the health result.
- Verified invalid limit, event ID, and message text fail before any rail call.

Fixture run result: 13 assertions passed. No live authenticated read or write
was attempted, so the test did not consume credentials or send a conversation.

UNIT-COMPLETE: w2-rail-adapter