---
title: Workflow zombie agents starve the concurrency cap
type: reference
permalink: main/reference/harness/workflow-zombie-agents-starve-the-concurrency-cap
tags:
- workflow
- orchestration
- mcp
- concurrency
- rescue
- verification
---

# Workflow rescue: a hung agent holds its slot forever

**Measured 2026-07-26, run `wf_b8040742-6c9`** (a 138-unit UI/UX audit fan-out).

## Symptom that looks like rate-limiting but isn't

Throughput collapsed to ~7 completed agents / 40 min. I first attributed it to API
rate-limiting. Wrong. **9 agents had hung hours earlier and were still holding their
concurrency slots.** Cap is `min(16, cores-2)` = 14 on this 16-core box, so 9 zombies left
**5 usable slots — 64 % of capacity lost**. After the rescue the run immediately launched
14 again, and verifier results went from frozen-at-121 to climbing within minutes.

## Diagnose from the on-disk journal, no framework introspection

`journal.jsonl` carries one `{"type":"started"|"result","agentId","key"}` per event:

```python
started = {d["agentId"]: d["key"] for d in recs if d["type"] == "started"}
resulted = {d["agentId"] for d in recs if d["type"] == "result"}
zombies = {a: k for a, k in started.items() if a not in resulted}
```

Then split dead from working by **transcript mtime**: a live agent's `agent-<id>.jsonl` is
seconds old; the zombies were untouched for 2.5 h while siblings wrote 20 min ago. Two
zombies sharing one `key` = the same unit retried (the "stuck in a loop" shape).

## Root cause to check FIRST: a disconnected MCP server

The largest zombie (503 KB) was calling `mcp__playwright__browser_evaluate`/`_navigate`
when the Playwright MCP disconnected mid-session (the harness announced all 22 tools gone).
**A tool call to a dead MCP never returns, so the agent hangs forever and never frees its
slot.** Find it by counting repeated `tool_use` names in the zombie transcript.

Corollary: read-only audit agents told they "may read `build/`" will escalate to spinning
up `python -m http.server <fixed port>` and driving a SHARED MCP browser. One fixed port +
one browser across 14 parallel agents is a contention/hang factory, and those stray servers
later held a Windows lock on `build/` that broke a build with `EBUSY`.

## Rescue WITHOUT losing completed work

1. `TaskStop <task_id>` — the Workflow tool's task id, not the run id. Agents in flight at
   that moment are lost, but they have no cached result, so resume simply re-runs them.
   **No completed work is discarded.**
2. `Workflow({scriptPath, resumeFromRunId})` with the script **byte-identical**.

**DO NOT EDIT THE SCRIPT to "fix" the hang.** The cache is prefix-based: resume caches the
longest unchanged prefix of `agent()` calls, and the first changed call plus everything
after runs live. Shared prompt constants (a HONESTY/CONTEXT block interpolated into every
prompt) are part of every call's cache key, so touching one character there invalidates
**all** cached results and silently turns a rescue into a full restart.

**Verify the cache actually hit — count transcripts, don't trust the log line:** 269 → 283
is `+14` (one fresh batch = the cap) and proves replay; a jump toward +260 means everything
re-ran.

## Also worth knowing

- The audit *phase* can be complete while the run looks stalled — here 138/138 audit units
  had finished and only verifiers were queued, so **harvesting `journal.jsonl` mid-flight
  yielded all 469 findings immediately** instead of waiting ~11 h for the tool to return.
  Parse `type=="result"` payloads and split by shape: `{findings:[]}` vs `{verdicts:[]}`.
- `TaskList` does **not** list workflow runs — keep the `Task ID` from the launch result.
- A process exit stops the run with no completion marker; resume is the same operation.

Relations: [[PrimariRo atlas — option A confirmed, /e2e green, deploy blocked on GitHub Actions billing (2026-07-29)]]
