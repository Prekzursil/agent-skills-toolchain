---
title: Context / token-reduction discipline
scope: common
loads: on-demand (referenced from AGENTS-RUNTIME §12); read before workflow/fleet
  work, when a session feels bloated, or when tuning the harness
verified: 2026-09-25 against code.claude.com/docs (context-window, costs, model-config)
  + platform.claude.com (prompt-caching, context-editing)
paths:
- '**/.claude/**'
- '**/.agents/**'
- '**/*.jsonl'
permalink: dqverify-repo-20261013/rules/common/context-reduction
---

# Context / token-reduction discipline

**Doctrine: the real levers are NATIVE and mostly already on. Codify habits + fix a few gaps. Adopt NOTHING heavy/external.** A big skill/MCP surface hurts BOTH cost AND quality (tool-mispick, lost-in-the-middle, latency, earlier autocompaction) — so this is a quality lever, not just a bill. Justify effort on *dilution + earlier autocompaction*, since prompt caching already mutes raw cost.

## Native levers — MANDATE (trust them)
1. **Native compaction** (3 tiers: microcompaction v1.0.68+, auto-compact ~83% window, manual `/compact`). Trust it; do NOT bolt on external compaction proxies.
2. **Steer compaction:** keep a `# Compact instructions` block in CLAUDE.md so auto/manual compaction deterministically preserves **decisions, diffs, and OPEN-LOOPS** (makes §1c "nothing is abandoned" survive compaction). Ad-hoc: `/compact <focus>`.
3. **`/clear` between UNRELATED tasks** (free, resets session cost + cache) vs **`/compact` to CONTINUE the same task** (itself a large request — reads the whole convo). The `strategic-compact` skill adds only the *when* judgment; the primitives are native.
4. **`/context` (+ `/context all`)** to inspect the real footprint (system/tools/memory/skills/MCP/history) before blaming the model. The custom `context-budget` command mostly wraps this — MEASURE before keeping.
5. **Tool Search** (deferred MCP schemas) is the #1 lever and is ON (`ENABLE_TOOL_SEARCH`). Keep it. **Two silent KILLERS** (→ mcp-process-hygiene.md + the SessionStart guard): a custom `ANTHROPIC_BASE_URL` **disables** Tool Search (whole surface loads upfront) — your gateway/GLM/529-failover sessions are the risk; and `auto:N` is window-relative (`auto:5` = 5% of 1M ≈ 50K) so prefer explicit `=true`.
6. **MCP hub multiplex** (first-party cloud/search/social-hub = ~3 slots for ~30 providers). Prefer the hub over individual servers. Orphan reaping → mcp-process-hygiene.md.
7. **Subagent isolation** = biggest native reducer: put verbose reads/tests/research in a subagent; only its summary returns. Treat each subagent as a **COLD cache** — keep spawn prompts minimal (everything in the prompt is fixed context for that teammate). Owner directive stands: **Opus for substantive subagents, quality > cost** — down-routing is MEASURE-only.

## Habits — codify
8. **Thin always-loaded docs.** CLAUDE.md < 200 lines; keep aggregate always-on governance under a token budget; topical detail lives in skills / path-scoped `rules/`, NOT in the contract. A new rule must **replace bulk, not add**. (Current violation: ~14.7k always-on tokens; `AGENTS-RUNTIME.md` 273L — see OPEN-LOOPS "thin-docs diet".)
9. **Command-OUTPUT filtering.** Verbose Bash (test/build/lint/git) is the biggest silent cost — filter before it enters context (native PreToolUse rewrite to grep failures; the Bash tool already auto-persists big output to a file; the `context-sandbox` skill). Never echo a raw dump you don't need.
10. **Cache hygiene — don't thrash mid-session.** Changing tool defs or their ORDER invalidates the ENTIRE cache; `/model` or `/effort`/thinking swaps invalidate the message cache; mid-session CLAUDE.md/MCP-config edits invalidate the system cache. Avoid these mid-task. Don't idle past the cache TTL (1h subscription / 5min API) — the next message reprocesses full context. Watch `/usage` "Prompt cache (main)".

## SKIP — verified over-engineering for a single owner
awecompress · billion-context · TokenPruner (no such tool) · Token-Diet · CompactPrompt (lossy, RAG-only) · **Token Optimizer MCP** (self-asserted losslessness per its own issue #415; injects 61 tools = worsens the surface it claims to cut) · briefd (team tool; basic-memory already covers) · CMV/gist/prompt-distillation (papers / need model training). Also SKIP blanket terse/caveman mode (collides with owner "full rigor"; use the native *Concise* output-style only if the owner opts in). **Adopt nothing external — native + light estate glue only.**

Evidence: `knowledge/analyses/2026-09-23-context-budget-cost-vs-quality.md` + the verified 2026-09-25 research fan-out. Sibling: `rules/common/mcp-process-hygiene.md`.