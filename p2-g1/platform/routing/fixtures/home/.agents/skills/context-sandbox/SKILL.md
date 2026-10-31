---
name: context-sandbox
description: Use when a command, file read, web fetch, or MCP tool call is about to return a large or noisy payload (logs, JSON dumps, build output, page snapshots, search results) that would otherwise be echoed verbatim into the conversation and rot the context window. Guides the agent to sandbox the raw output, surface only the derived answer, and index reusable bytes into persistent memory for on-demand recall instead of keeping them in-window. Markdown guidance only, not an automated guarantee.
license: ELv2
metadata:
  net-new-after: deep-research, research-ops, verification-loop, context-budget, strategic-compact, content-hash-cache-pattern, knowledge-ops
---

# Context Sandbox: Print Derived Results, Never Raw Payloads

Large tool outputs are the single biggest source of avoidable context rot. A 2,000-line log, a 50KB JSON blob, or a full DOM snapshot poisons every subsequent turn — the model re-reads it, attention is diluted, and quality drops for the rest of the session. This skill is the *discipline* that keeps raw bytes out of the window. It cannot enforce anything (markdown can only guide); it tells you how to behave when a payload is about to land in context.

This is a clean-room re-implementation of the "sandbox the output, surface the answer" idea (inspired by context-mode's `ctx_execute` / `ctx_fetch_and_index` pattern). It deliberately DROPS the dedicated SQLite/FTS5 store — `basic-memory` already provides hybrid semantic + keyword search over a durable vault, so a second store is redundant. No third-party code or text is vendored.

## When to run

Apply this BEFORE issuing the call, whenever the output might be large or noisy:

- Reading a file or directory whose size you do not already know.
- `Bash`/CLI that reads, queries, fetches, lists, logs, tests, builds, diffs, or inspects (gh, docker, kubectl, aws, npm, jest, git log, etc.).
- A `WebFetch` / page fetch / Playwright or browser snapshot / accessibility tree.
- ANY MCP tool whose result may exceed roughly 20 lines (RE disassembly dumps, scholarly metadata, search-result lists, API responses).

If the output is guaranteed small (a single status line, an `echo`, a one-row check), skip this — the overhead is not worth it.

### The core discipline (3 rules)
### On-demand index recipe (basic-memory, ~15 lines)
### Anti-patterns
### Relationship to neighboring skills
