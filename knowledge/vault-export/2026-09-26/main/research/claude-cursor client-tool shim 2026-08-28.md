---
title: claude-cursor client-tool shim 2026-08-28
type: note
permalink: main/research/claude-cursor-client-tool-shim-2026-08-28
status: active
valid_as_of: 2026-08-28
---

- [decision] Claude Code + Cursor models stay on auth2api `:8317` / `claude-cursor`. Tool loop is a text shim (json action → Anthropic `tool_use`), not protobuf MCP, not cursor2api.
- [fact] First-turn docs few-shot works (live: `get_weather` Paris; Claude-Code-shaped `Read` of package.json). Follow-up must NOT re-inject docs framing or XML `<tool_result>` — that caused a Read-loop (model treated results as fake). Fix: natural `Action output` + skip few-shot on tool history + drop repeat calls + drop lecture preamble.
- [fact] Follow-up live 28.08.2026 after patch: `stop_reason: end_turn`, text `The package name is auth2api`, no tool_use. disk-verified.
- [fact] Fable does **not** silently fall back on a bad SKU: `claude-fable-9-does-not-exist-xyz` → HTTP 502 `ERROR_BAD_MODEL_NAME`. Alias `fable` maps to `claude-fable-5-thinking-high` (header `x-auth2api-cursor-sku`). Live fable+weather: `tool_use` get_weather, sku header present. Cursor does not advertise a served-model field in the chat protobuf we decode — overload swap would still be invisible; invalid names fail closed.
- relates_to [[claude-cursor client-tool shim 2026-08-28]]
- relates_to [[auth2api]]
- [fact] 28.08.2026 live FP/SKU probes (`docs/probe-fp-sku_2026-08-28.md`): biology (GABA-B/phenibut, no dosing), defensive security (prompt injection as concept + parameterized queries), and normal (Bucharest) all classified `ok` with `wouldRetry=false` on both fable and sonnet, with and without client tools. Zero shim-retry log lines. Identity: fable self-IDs as Fable family with sku `claude-fable-5-thinking-high`; sonnet self-IDs as Sonnet with `claude-sonnet-5-thinking-high`; both `mismatch=0` and `metaHints=-`. Fable+weather still `tool_use` get_weather Paris. Bogus SKU still HTTP 502 `ERROR_BAD_MODEL_NAME` (fail-closed, no silent family swap).
- [decision] Shim retry fires only on `classifyShimTurn === shim_refusal` (Cursor lecture phrases). Dual-use safety strings are `safety_refusal` and must not retry. Biology/security/normal hedges (`I cannot help with dosing`, `it's just text`, educational prompt injection) stay `ok`. Bare `I must refuse` is not safety (too broad).
- [fact] SKU family mismatch cannot be called 100%: chat protobuf still has no served-model field we decode. Scanner subtracts SKU tokens that appear in assistant text (`scanCursorSkuWire`); live metaHints were empty (`-`) on all 2xx rows. Buffer-all-2xx was reverted because it broke streaming; shim-on still buffers (retry), shim-off taps the stream without delaying first byte. Header `x-auth2api-cursor-sku-mismatch` is 0|1 when the body was already buffered.
- relates_to [[auth2api]]
- [fact] 28.08.2026 live refusal/SKU probes (`docs/probe-refusal-sku_2026-08-28.md`): legitimate keyword-heavy textbook questions (SQL injection concept, malware vs bug, pathogen vs toxin, CVE vs exploit) all **answered** on sonnet; same SQL concept answered on fable. Zero keyword-FP retries needed this run because the model did not refuse. Malicious-intent exploit-payload prompt: model `safety_refusal`, proxy `wouldRetry=false` (no jailbreak retry). Malicious-intent pathogen-synthesis prompt: Cursor/Anthropic **usage-policy 502** (`ERROR_OPENAI` blocked), proxy did not retry; brief 5s account cooldown then 503 on the next two identity calls (retried OK after 8s).
- [decision] Keyword false-positive retry is **benign+keyword+generic-refusal only**, with `[auth2api: conceptual-only retry]` framing (textbook/definition, no payloads). Malicious intent never enters that path. Shim lecture retry unchanged.
- [fact] SKU overload hole still not 100%: live `headerHints=-` `protoFam=-` `metaHints=-` on both fable and sonnet 2xx bodies. Scanner now also walks nested protobuf strings and Cursor response headers. Fail-closed on bad SKU unchanged. Identity retry: sonnet self-IDs Sonnet + sku `claude-sonnet-5-thinking-high`; fable self-IDs Fable + `claude-fable-5-thinking-high`; mismatch=0.
- relates_to [[auth2api]]

## Reliability pass 28.08.2026 (classifyCursorRetry + Fable stick)

- [decision] `classifyCursorRetry` stays `none` | `shim_refusal` | `keyword_fp`. Malicious reverse-shell / exploit-payload / pathogen-synthesis intent is `none` (no retry). `conceptualReframe` does not rewrite those strings.
- [decision] Folded system uses `## Session configuration (binding)` + `## Task`. Do not use `[system]` / `[INST]` — Cursor-hosted Claude treated those as injection (live).
- [decision] Sticky Cursor `conversationId` = uuidv5(`auth2api-cursor:` + model + first user text). New UUID per request was the multi-step Fable → Opus/Sonnet bounce.
- [fact] Live 28.08.2026 `scripts/probe-fable-multistep.mjs`: T1 Fable `get_weather` Paris (SKU `claude-fable-5-thinking-high`, mismatch=0); T2 after tool_result self-id **Fable**, mismatch=0. Receipt: `Cowork/tools/auth2api/docs/probe-fable-multistep_2026-08-28.md`.
- [fact] Shim retry now says `Yes, proceed. Output only the JSON action.` Permission-asks/hedges retry as `shim_refusal`; hedge-then-comply with a parsed tool is `none`. NL `I would use the Read tool to open …` recovers to JSON. Coverage: **NOT-CHECKED** (auth2api has no `.coverage-thresholds.json`).
- relates_to [[auth2api]]

## Reliability overhaul 28.08.2026 (modules)

- [decision] Graduated protocol retries (levels 1–3) for `shim_refusal` / `permission_ask` / `soft_refusal` / `omission` / `keyword_fp` only. Malicious intent still `classifyCursorRetry=none` and is never reframed.
- [decision] No local-uncensored **answer** fallback. `local-rewriter` is optional (`LOCAL_MODEL_ENDPOINT`), 5s timeout, regex fallback, keyword_fp level 2+ only. Do not hardcode an abliterated SKU.
- [fact] New files: `output-contract.ts`, `model-framing.ts`, `conceptual-reframe.ts`, `prompt-intent.ts`, `refusal-recovery.ts`, `retry-framing.ts`, `compliance-classifier.ts`, `local-rewriter.ts`. `encodeCursorChatRequest(body, opts)` and `classifyCursorRetry(decoded, body)` signatures kept; return union expanded.
- [fact] Tests 297 pass. Coverage NOT-CHECKED (no `.coverage-thresholds.json`). Live Fable stick from earlier today still stands; this overhaul is unit-tested, not re-probed live.
- relates_to [[auth2api]]

## Conservative extra tests 28.08.2026 (afternoon)

- [decision] Default `MAX_RETRY_LEVELS=1` (one extra Cursor turn). 2–3 is opt-in. Mocked transport proves permission-ask is capped; 502 and malicious intent are not retried. Do not re-run `probe-refusal-sku.mjs` (pathogen-synthesis 502 + account cooldown).
- [fact] Live `scripts/probe-safe-live.mjs`: 3 sequential calls, 8s gap, no dual-use prompts. Sonnet capital=Bucharest; Fable `get_weather` Paris; Sonnet package-name answered. All HTTP 200, no 429/503. Receipt: `Cowork/tools/auth2api/docs/probe-safe-live_2026-08-28.md`. Tests **304 pass**. Coverage NOT-CHECKED.
- relates_to [[auth2api]]

## Fable Read loop + workweave/router 28.08.2026

- [fact] Live Fable Read tool-loop: T1 `Read` package.json (SKU `claude-fable-5-thinking-high`, mismatch=0); T2 after tool_result named **auth2api** 1.0.0, no repeat Read. Receipt: `Cowork/tools/auth2api/docs/probe-read-loop_2026-08-28.md`.
- [fact] [workweave/router](https://github.com/workweave/router) is a Go model router (ELv2, :8080, per-**action** Avengers-Pro scorer, BYOK/OpenRouter). Different job from auth2api Cursor cloaking. Notes: `Cowork/tools/auth2api/docs/workweave-router_2026-08-28.md`.
- [decision] Do not run `npx @workweave/router` on this estate without an explicit install task — it patches Claude Code/Codex config and fights auth2api `ANTHROPIC_BASE_URL`.
- relates_to [[auth2api]]

## OpenRouter apps vs Claude Code (28.08.2026)

- [fact] `/effort ultracode` is a Claude Code session mode (xhigh + auto workflow fan-out), not a third-party CLI. No OpenRouter app ships it.
- [decision] Do not replace Claude Code+auth2api with Hermes or OpenClaw for the Cursor-billing repo loop. Hermes/OpenClaw are persistent personal agents (memory, Telegram, cron). Complementary later; RAM-hostile as always-on on this box.
- [decision] Best OpenRouter-catalog *coding* alternate if Anthropic Messages stays painful: **Kilo CLI** (OpenAI-compatible `baseURL` → `:8317/v1`) or Cline/Roo. Token rank ≠ quality. OpenRouter remains spend-capped sidecar, not Cursor BYOK.
- [fact] Notes: `Cowork/tools/auth2api/docs/openrouter-apps-cli-replacement_2026-08-28.md`. Catalog: https://openrouter.ai/apps
- relates_to [[auth2api]]

## Corrected goal (28.08.2026, owner)

- [decision] Product is the **TUI**, not `/effort ultracode`. Owner keeps session effort on **max**. Workflows are created by asking the agent; per-agent `model`/`effort`/`agentType` live in the workflow script and the native `/workflows` window.
- [decision] Cursor GUI is rejected (RAM, missing native workflow/subagent UX). Daily drivers: **Claude Code TUI** and **Grok Build TUI** (already configured: hooks imported, `codex` plugin, `claude_compat`).
- [decision] Mixed **Codex workers as rows in the same native workflow window** is must-keep (`agentType: 'codex'` in Claude). A TUI that cannot do that is a downgrade. wfmon is the improved monitor and should stay cross-tool, with compatibility work if Grok journals differ.
- [decision] OpenRouter apps catalog (Hermes/OpenClaw/Kilo) was the wrong problem. No third TUI currently beats Claude+Grok on native `/workflows` + mixed Codex + already-wired harness.
- relates_to [[auth2api]]

## Hermes dynamic-workflows plugin (corrected 28.08.2026)

- [fact] Third-party plugin `lingjiuu/hermes-dynamic-workflows` (~114★) adds Claude-like `agent()/parallel()/pipeline()`, `/workflows`, optional separate `hermes-workflows` dashboard. Python sandbox, not Claude JS. `agentType` is Hermes explore/plan/verification — not Claude `agentType: 'codex'` (Codex CLI row).
- [fact] Hermes **does not** accept Cursor browser login on current main. Official providers: Nous Portal, ChatGPT/Codex OAuth, Copilot OAuth, OpenRouter keys, Anthropic OAuth, xAI, custom OpenAI-compat. Cursor as first-class provider is **open PRs** (#88212 CURSOR_API_KEY, #70140 plugin) labeled needs-decision. Closed RFC #30640: Cursor sells a harness, not a raw model.
- [decision] Plugin is a real workflow engine I missed by treating Hermes as chat-only. It is still not a drop-in for this estate vs already-wired Claude/Grok TUIs unless owner wants a third harness + unofficial Cursor path.
