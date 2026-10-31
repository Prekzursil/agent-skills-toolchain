---
name: context-sandbox
description: Use when a command, file read, web fetch, or MCP tool call is about to
  return a large or noisy payload (logs, JSON dumps, build output, page snapshots,
  search results) that would otherwise be echoed verbatim into the conversation and
  rot the context window. Guides the agent to sandbox the raw output, surface only
  the derived answer, and index reusable bytes into persistent memory for on-demand
  recall instead of keeping them in-window. Markdown guidance only, not an automated
  guarantee.
license: ELv2
metadata:
  net-new-after: deep-research, research-ops, verification-loop, context-budget, strategic-compact,
    content-hash-cache-pattern, knowledge-ops
permalink: dqverify-repo-20261013/agent-self/skills/context-sandbox/skill
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

## The core discipline (3 rules)

1. **Sandbox the raw payload.** Route the bytes somewhere other than your reply. Prefer writing the raw output to a file (`cmd > out.txt`, the tool's own `filename` parameter for Playwright/snapshots, or `Read` with `offset`/`limit` to take only the slice you need). The raw bytes live on disk, not in the conversation.
2. **Print ONLY the derived result.** Your message contains the answer you extracted — the error line, the failing test name, the one field, the count, the verdict — plus a pointer to where the full payload lives (the file path). Never paste the whole payload "for completeness." If the user needs more, they have the path.
3. **Index reusable bytes on demand.** When a payload holds knowledge you will likely need again across turns or after a compaction (a docs page, a schema, a long investigation result), write a distilled note to persistent memory now, then recall it later instead of re-fetching. This is what survives compaction.

## On-demand index recipe (basic-memory, ~15 lines)

Capture the distilled signal — not the raw dump — into the durable vault, then pull it back when needed instead of re-reading the source.

Index (push) right after deriving the result, while it is fresh:

```text
mcp__basic-memory__write_note(
  title: "<short, searchable title>",
  folder: "context-sandbox",
  content: "Derived facts only: the answer, the key fields, the path to the raw payload on disk. NOT the raw bytes."
)
```

Recall (pull) before re-running an expensive fetch or after a compaction:

```text
mcp__basic-memory__search_notes(query: "<2-4 technical terms>")
# then read_note / build_context on the best hit to bring the distilled facts back into context
```

Rules for the note body: store derived facts plus the on-disk path to the raw payload, never the raw payload itself. Re-fetching the source is cheap; re-rotting the context is not. If `basic-memory` is unavailable, fall back to a scratch file under the working tree and grep it — same principle, weaker recall.

## Anti-patterns

- Pasting a full log/JSON/snapshot into the reply "so it is on record" — that is exactly the rot this prevents; the file path is the record.
- Re-reading the same large file every turn instead of indexing the distilled facts once and recalling them.
- Writing the *raw* payload into `basic-memory` — that just moves the rot into the vault and pollutes future searches. Distill first.
- Sandboxing a guaranteed-tiny output — needless ceremony.

## Relationship to neighboring skills

- `context-budget` (built-in): measures where context is being spent. This skill prevents the largest single source of that spend.
- `strategic-compact`: compacts the window at phase boundaries. This skill keeps bytes out so there is less to compact.
- `content-hash-cache-pattern`: caches expensive *processing* results by content hash. This skill governs what enters the conversation in the first place.
- `knowledge-ops` / `research-ops`: own durable knowledge capture broadly. This skill is the narrow, per-tool-call discipline that feeds them clean signal.