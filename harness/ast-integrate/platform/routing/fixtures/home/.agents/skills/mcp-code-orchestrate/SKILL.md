---
name: mcp-code-orchestrate
description: Use when one task needs the SAME tool-call shape repeated across MANY items - an xref-walk over dozens of functions, a descriptor sweep over many SMILES, batch-resolving or screening a list of papers, or aggregating one query across several MCP servers. Write ONE script (Python via the Bash tool) that calls the underlying provider CLIs, native libraries, or MCP stdio, filters and aggregates IN-CODE, and returns ONLY the distilled result, instead of N model round-trips that each bloat context with raw tool output. This is Anthropic's code-execution-with-MCP pattern (up to ~98.7% fewer tokens on fan-out work). Decision rule - reach for it once you would otherwise make more than about 5 same-shape tool calls. Not for a single tool call.
license: MIT
---

# MCP Code Orchestrate

> **The 98.7% fan-out token-cut.** When you would otherwise call the same MCP
> tool N times and let every raw result land in the context window, write **one
> script** that does the loop, filters/aggregates **in code**, and returns only
> the distilled answer. Anthropic's "Code execution with MCP" reports a single
> example dropping from ~150,000 tokens of tool chatter to ~2,000 (≈98.7% fewer)
> by moving the fan-out into code instead of the model loop.

## The pattern in one breath

Direct tool-calling is right for **one** call: ask, get the answer, done. It is
*pathological* for **fan-out** — "enumerate-then-filter" across the 39-server MCP
fleet — because:

1. Every tool *definition* you load is paid for on every turn (catalogue tax).
2. Every tool *result* (a 4 KB JSON blob × N functions / molecules / papers)
   is dumped verbatim into context, and the model re-reads all of it each turn.
3. The model is doing a mechanical loop (iterate, test a predicate, collect hits)
   that a `for` loop does for free, deterministically, off-context.

The fix: the agent writes **one Python script** (run via the **Bash** tool) that
calls the *underlying* provider — its native CLI/library when one exists, else
the MCP server over stdio/HTTP — loops over all the items, applies the filter in
code, and **prints only the distilled result** (a shortlist, a count, the 12
hits out of 4,000). Raw payloads stay on disk / in process memory; only the
answer enters the conversation.

### Decision rule (use this / don't)
### How a script reaches a provider — three access modes
### 1. Native CLI or Python library (best — zero MCP overhead)
### 2. MCP server over stdio (one session, many calls)
### Example: spawn once, loop many.
### sess = MCPSession(["npx", "-y", "mcp-searxng@1.8.0"],
### env={**os.environ, "SEARXNG_URL": "http://127.0.0.1:8890"})
### hits = [sess.call("searxng_web_search", {"query": q}) for q in queries]
### sess.close()
### 3. MCP server over HTTP (already-running servers)
### Concrete recipes
### (a) RE xref-walk — find the hot functions across a whole binary
