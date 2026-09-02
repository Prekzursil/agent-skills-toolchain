# Gem-hunt lens 03 - OpenRouter as the spend-capped sidecar

Date: 2026-09-02. Lens id: `03-openrouter-sidecar`. Branch: `gemhunt/hosted-models-03-openrouter-sidecar`.
Mode: discovery only (research + findings). No code changed. No PR.

## 0. Scope, method and grading key

This lens answers one question: **what is the current OpenRouter API surface, how does each
installed runtime that is ALLOWED to use it consume it today, and what should the estate's
spend-capped sidecar policy be** - without violating any estate lock.

Grading key used on every claim:

- **Tier A** = primary vendor documentation or the vendor's own API response (e.g. `openrouter.ai/docs`,
  a runtime's official docs/README). **Tier B** = vendor blog/changelog, first-party GitHub issues,
  or well-known secondary references. **Tier C** = community posts, third-party summaries.
- **corroborated** = two or more independent sources agree; **UNVERIFIED** = single source or not
  re-checked live in this session.
- Every claim is dated with the date the source was read (all read 2026-09-02 unless stated).
- Labels: `[FACT]` sourced fact, `[INFER]` inference from facts, `[REC]` recommendation.

Estate locks are quoted as constraints in section 1 and are never proposed to be violated.

Sections below are appended incrementally; each push is a checkpoint (runs die at ~12 min).

## 1. Estate constraints this lens must respect (from the task brief and the repo)

These are quoted as hard constraints. Nothing below proposes violating them.

| # | Lock (verbatim intent from the brief) | Where it already lives in the repo | Status |
| --- | --- | --- | --- |
| L1 | OpenRouter is a **spend-capped CLI/Codex sidecar only** - never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | `.agents/skills/openrouter-routing/SKILL.md` ("Never Cursor BYOK", "Claude Code footgun", "Do not add an OpenRouter MCP") | `[FACT]` in-repo, Tier A (repo file), read 2026-09-02 |
| L2 | No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | same skill: "Do not install LiteLLM"; `openrouter-complete-surface_2026-08-27.md` SKIP rows for LiteLLM, Agent SDK, Hermes Agent | `[FACT]` in-repo |
| L3 | `auth2api :8317` stays the ONLY Cursor bridge, retires within 7 days of an official Cursor `/v1` GA | brief (DEDUP-SET item 3) | constraint, not re-examined here |
| L4 | Ports 8765 / 8812 / 8317 are owned (basic-memory, agent-mail, auth2api) | brief | constraint: this lens proposes **no** new listener on any port |
| L5 | `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it) | `.agents/AGENTS.md` "Universal harness share (HARD)" | `[FACT]` in-repo |
| L6 | Never rotate credentials; never mint new secrets from an agent session | `openrouter-routing/SKILL.md` "Do not mint new secrets from an agent session"; brief | `[FACT]` in-repo |
| L7 | Never remove a feature to buy reliability - present trade-offs | brief | method rule for section 4 |

### 1.1 What already exists (so this lens does not re-propose it)

`[FACT]` The repo already carries a full OpenRouter doctrine, all dated 2026-08-27 (Tier A repo files):

- `.agents/skills/openrouter-routing/SKILL.md` - key location by name only (`OPENROUTER_API_KEY` env + `.agents/local.json` pointer), T0/T1/T2 one-way escalation, suffix table (`:floor`, `:nitro`, `:exacto`, `:online` deprecated), Batch API note, Claude footgun, Codex **named non-default** provider (`wire_api = "responses"`), spend-cap checklist (per-key `limit` XOR `limit_reset`, workspace budgets = Enterprise), free/test slugs, Hermes low-refusal lane, probe commands.
- `.agents/skills/openrouter-routing/openrouter-complete-surface_2026-08-27.md` - 38-source audit: OpenAPI 77 paths / 101 ops, live catalog 417 models / 17 `:free` / 348 tool-capable / 103 providers, error-code table, NATIVE-vs-BUILD-vs-SKIP for every official integration, "we would have missed X" list.
- `.agents/skills/openrouter-routing/openrouter-free-models_2026-08-27.md` and `openrouter-apps-hermes-uncensored_2026-08-27.md` - free-slug snapshot and Hermes evidence.
- `.agents/scripts/openrouter-complete.py` / `.ps1` - the thin T0 chat-completions probe with `--show-limits` and generation-id cost readback.
- Live account facts recorded there (2026-08-27): inference key `limit=null` (uncapped), `is_free_tier=false`, credits ~$319.4 purchased vs ~$319.79 used (**slightly overdrawn**, paid T0 returned 402).

`[INFER]` Therefore the gap this lens fills is **not** "what is OpenRouter"; it is (a) what changed in the six days since 2026-08-27 and which of those claims re-verify live today, (b) how the **other allowed runtimes** (Fabric, Aider, OpenCode, Goose, Grok CLI, Gemini CLI) actually bind to OpenRouter per their current docs - the 08-27 audit only covered Codex and one Aider line, and (c) a **per-runtime key-scoping and cap** design that the 08-27 audit deferred to "user clicks".

## 2. OpenRouter API surface as of 2026-09 (sourced)

_(pending)_

## 3. Runtime-by-runtime: how each ALLOWED runtime consumes OpenRouter today

_(pending)_

## 4. Sidecar policy design

_(pending)_

## 5. Model shortlists (T0 / T1) with price/perf evidence

_(pending)_

## 6. Per-find rubric table

_(pending)_

## 7. Ten-line summary

_(pending)_
