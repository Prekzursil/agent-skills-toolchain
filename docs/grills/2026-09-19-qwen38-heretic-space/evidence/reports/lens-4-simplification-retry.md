<!-- verbatim final report of the simplification lens RETRY (Fable 5.1), saved 2026-09-19 -->

## A. Dead weight

Baseline: 7,075 tracked lines; no test imports `app.py`.

| Dies | Where | Why → replacement | Lines |
|---|---|---|---|
| Draft model + spec-decode | app.py 37, 43, 70-72, 138-163, 441, 485, 696/724/792, `spec` checkbox 979-983; openai_protocol 371-373, 412 | never ran (stateful model); M-2 → nothing | ~50 |
| NF4 export + upload thread | app.py 197-258, 448; secrets `NF4_EXPORT`, `NF4_UPLOAD_TOKEN` | G-15(6) → `jobs/quantize.py` HF Job | 63 |
| bnb quantize-at-load, flash-attn chain, `_generate_kwargs` retry ladder | app.py 82-116, 389-423 | worker does one `from_pretrained` of a prebuilt FP8/GPTQ checkpoint | ~60 net |
| Import-time load, mount probing, lazy-boot remnants, `_wait_models`, `_gpu_xlarge` | app.py 1, 9-17, 36-67, 119-131, 181-194, 522-529 | front is CPU-only → `worker/app.py` + pinned revision in `models.yaml` | ~85 |
| Lease plumbing (`_estimate` 321-336, `_encode_messages` 342-383, `_gpu_impl` 426-514) | app.py | relocates to the worker, not deleted | ~210 moved |
| `api_generate` | app.py 532-573 | 17-kwarg pass-through → `GenerationRequest` | 42 |
| `gpu_size` as caller knob | radio 973-978, six preset keys, `_apply_preset`/`_example_row`/`chat` slots; openai_protocol 361-369, 411 | hardware is a catalog property | ~25 |
| Monkey-patched mount | openai_api.py 55-85 | existed only because ZeroGPU hooks `launch()` (openai-api-6); CPU front owns a FastAPI app and `gr.mount_gradio_app`s the UI | 31 |
| Token-counter hook | app.py 166-177; openai_protocol 25-41 | front has no tokenizer; usage arrives in the backend `Finish` event | ~30 |
| `maintenance/` (keepalive 39, watch 65, updater 209 with broken `bump_within_range`, two .ps1 28) + `deploy_space.py` 52 | | CI health job, Dependabot, CI deploy (G-1a) | 393 |
| Committed junk | idx.json 1206, runlog_tail.txt 378, keepalive.log 2 | delete, extend `.gitignore` | 1,586 |
| Deps/config | front `requirements.txt` drops 7 of 9 lines (transformers, accelerate, bitsandbytes, sentencepiece, protobuf, torchvision, hf_transfer; last two die in the worker too); Space vars `HF_HOME`/`HF_HUB_CACHE`/`HF_HUB_ENABLE_HF_TRANSFER`; README `startup_duration_timeout: 1h`, lines 11-19, 23-29, 81-83, 91 | `space.yaml` per Space; README generated from catalog + test count | ~30 |

**≈2,270 lines deleted outright** (≈690 code/scripts + 1,586 junk; 32% of the tree) plus ≈210 relocated. `app.py`: 1,158 → ~700 before the split → ~20-line composition root after.

## B. Module layout and seams

```
app.py            composition root: load_config → build_engine → build_ui/build_api → mount → uvicorn; nothing at import
core/types.py     GenerationRequest, SamplingParams (defaults once), Message = OpenAI content parts,
                  Event = TextDelta | ReasoningDelta | ToolCall | ToolResult | Finish{reason, usage, timings, error}
core/catalog.py   models.yaml load/validate; resolve(model) → (entry, backend); fallback order
core/prompting.py build_messages, parse_effort, text_of        ← _as_messages, _user_text, normalize_messages
core/parsing.py   tool_parse + incremental StreamParser (markup → events); salvage for hosted output
core/agent.py     run_turn(req, session): rounds, cap, rejection feedback, call/result pairing   ← chat() 705-786
core/session.py   SessionStore(bench, memory, todos), TTL, explicit keys   ← _BENCHES/_STATES
core/engine.py    Engine.generate(req) (one round) · run_turn(req, session); ledger hook
core/tools/       registry.py = specs(families, flags) + execute(); THE python_eval gate; file_bench, web, knowledge, state, sandbox
backends/         base.py Backend.stream(req) → Iterator[Event], health(), BackendError{kind, retryable}; hosted.py; worker.py (gradio_client); fake.py
ui/build.py       build_ui(engine, catalog) factory; render(events → Gradio messages)   ← _render, PRESETS, components 932-1051
api/app.py        build_api(engine): auth, limits, /v1/chat/completions (relay), /v1/models, /healthz(sha), /status, /v1/preflight
api/protocol.py   request → GenerationRequest; events → SSE/JSON   ← response half of openai_protocol
api/mcp.py        ask / poll / status / preflight
worker/app.py     ZeroGPU Space: import-time load, @spaces.GPU, Gradio endpoint — the only file allowed import side effects
worker/encode.py, lease.py   encode, gen-kwargs, estimate/max_time/resume — pure, CPU-testable
```

**The seam**: `_gpu_generate(gpu_size, **kw)` (app.py:527; called at 709 and 554). Right place, wrong altitude: a raw-markup `str` iterator each caller re-parses, fed template-form messages + PIL + `gpu_size`, carrying no finish reason, usage, error or cancel. Hosted providers return structured deltas, so the seam rises to `Backend.stream(GenerationRequest) → Events`; parsing and media conversion move below it. Three interfaces: Backend protocol (one conformance fixture suite every backend passes), Engine API (the only import surfaces get besides `core.types`), worker wire (same dataclasses, JSON in / NDJSON out, versioned).

**Traps**: app → `openai_protocol.parse_effort/set_token_counter` → `system_prompt` is already a surface→core→surface cycle; rule "surfaces → core → backends/tools, core never imports gradio/fastapi/spaces/torch", enforced by an import-contract test in the gate. `app.py` loads models (119-160), builds components at module scope (932-1051), patches gradio (1157), calls `demo.launch()` unguarded (1158); only `worker/app.py` keeps import-time load (ZeroGPU contract, the f90bb44 outage), `import spaces` first there and nowhere else. The identity trap moves to the worker: a raw FastAPI route there reproduces `token=None` (gpu-lease-6); expose a Gradio endpoint, call it via `gradio_client` with the scoped token, verify the quota bucket with one metered call. `request=gr.Request()` (658) is never injected: sessions are explicit keys.

## C. Duplication to collapse

1. Message assembly: app.py 668-684 vs `normalize_messages` (openai_protocol 164-237); persona keys re-listed in `PERSONA_KEYS` (:27) vs `PERSONAS`; `"red_team"` fallback ×3 → `prompting.build_messages`.
2. Content flattening ×3 (`_flatten_content` :122, `_user_text` 306, inline 297-301) → `text_of`.
3. Image placeholders built above the seam twice (app 679-682; `_content_for_template` :94-119) → worker encoder.
4. Parse/validate policy: UI `parse_model_output(acc)` without `in_think`, notes discarded (737-745) vs `_finalize` (:424-464) vs a third hand-rolled `<tool_call>` scanner in `_iter_sse` (:541-569, quadratic). This divergence *is* chat-loop-ui-4 → one `StreamParser`.
5. Thinking split, four behaviours (UI stream 729, UI final 737, API final 432, API stream none, ad hoc :675-679) → same parser; `/v1` gains `reasoning_content`.
6. Usage block copy-pasted (:635-644 ≡ :695-704, each counting twice) → `Finish.usage`.
7. Error-to-content ×3 (731-735, :570-581, :672-674) → `BackendError` → `Finish(reason)`; UI titled notice, API status.
8. Seventeen sampling kwargs spelled in five places (`_gpu_impl` 426-445, `api_generate` 532-552, call 709-727, `_gen_kwargs` 381-417, PRESETS + sliders); hand-threading is how `images`/`videos` went unbound at HEAD → `SamplingParams`.
9. Stop normalisation ×3 (686, 470, `_normalize_stop` :295) → one validator.
10. Tool dispatch ×4 (`_execute_tool` 600, `execute_agent_tool` 539, `execute_web_tool` 454, `FileBench.execute` 423), `python_eval` gate ×2, three name sets → registry; hardening point (5) needs one choke point.

## D. Thinnest slice and PR order

Thin slice = exactly what the canary needs: CPU Space, `/healthz` with git sha, `/v1/chat/completions` → `HostedBackend` → router, one `models.yaml` entry, a 10-line placeholder chat mounted via `gr.mount_gradio_app`. Its first request doubles as the platform lens's measurement and becomes fixture #1.

1. **platform** Repo + gate: import, delete A's junk, `eol=lf`, ruff F821 + 73 tests (fix persona-archive test) + claim-vs-diff, Python 3.12. Proof: red on f88b120, green on the cleaned tree; a deliberately broken staging deploy rolls back.
2. **platform** Lift-and-pin: move app.py's pure functions verbatim into `core/` (`--color-moved` shows moves only), then F. Proof: F green, known-bads marked.
3. **platform** Thin slice + `core/types`, `backends/hosted`, `backends/fake`, FakeEngine. Proof: recorded-router contract test; staging canary (running sha == pushed sha, 16 tokens). Product is unblocked here, not after 5.
4. **platform** StreamParser, typed events, error taxonomy, `reasoning_content`. Proof: known-bad pins flip; golden SSE parsed with the `openai` SDK models.
5. **platform** Registry + `core/agent` + `SessionStore`; `python_eval` flag-gated, absent from API/MCP toolsets. Proof: scripted backend: cap, one rejection round, pairing, session isolation; no request shape enables `python_eval`.
6. **product** `build_ui(FakeEngine)`: selector, presets, personas, render, history replay (chat-loop-ui-1). Proof: builds offline; events → message snapshot; transcript survives a turn.
7. **platform** Gateway hardening: API key, size/role/range validation, threadpool, 429, ledger + `/v1/preflight` + `/status`. Proof: TestClient table; over-budget refused with backend call count 0.
8. **platform** Worker Space + `backends/worker` + fallback order. Proof: CPU tests for estimator (9 tok/s row), gen-kwargs, encode ladder; conformance suite on fake worker; staging canary on a local entry; forced hosted failure → fallback. Product's loading experiments run in parallel from 3.
9. **platform** Hardened `python_eval` + SSRF/regex/calculator timeouts. Proof: red-proof per spec point (env allowlist, `/proc/<ppid>/environ` unreadable, rlimits trip, no orphans, off on every surface).
10. **product** Vision/video as OpenAI parts end-to-end. Proof: data-URI reaches the fake backend unchanged; caps; `vision: false` → 400 with zero backend calls.
11. **platform** MCP `ask/poll/status/preflight`, `chat` hidden. Proof: listing snapshot = 4 typed tools; clamps.
12. **platform** Eval harness + catalog admission in CI. Proof: schema test; dry-run on fake; evidence JSON per entry.
13. **product** Catalog fill, persona wiring, README generated. Proof: README table == models.yaml; test count computed.
14. **platform** Promotion: sha + per-backend canary + rollback armed; scheduled health job replaces keepalive.

## E. Ship but flag

- **Automatic hosted→worker fallback** (off): overage ≈$185/1M output tokens, SDK retries ×2 = three leases, cold lease re-uploads 22-30 GB, FP8/GPTQ on ZeroGPU unverified. Local entries stay explicitly selectable.
- **Server-side tools for `/v1`/MCP** (off): each round is another generation (gpu-lease-4), injection with nobody watching (security-tools-4); harnesses bring their own tools.
- **`http_request` POST + third-party reader mode** (off): outbound channel, every "readable" URL sent to r.jina.ai, Firecrawl key replay (security-tools-3/9); 483 lines around a brittle DDG parser.
- **Video** (off; images on): 25 s/video lease overhead, torchvision + video processor in the worker, provider support unverified; HEAD's three undefined names came from this commit.
- **Automatic lease chaining** (off; `length` + explicit Continue on): greedy-only equality, control-dict interception, fallback-path-only benefit (gpu-lease-3).
- **Cross-turn `preserve_thinking`** (off, chat-loop-ui-5). `python_eval`: already decided, gate it in the registry only. `xlarge`: operator config, never a request field.

## F. Characterisation tests first

Get importability by lifting verbatim (step 2), not by stubbing torch. Pin:
1. `_as_messages` 264-303: tuples, title-skip, list flattening, `bench_turn` replay (xfail: Gradio strips it).
2. `chat()` with an injected scripted generator: cap 8, stop on no valid call, exact assistant/tool shapes, silent drops, error text appended then parsed (known-bad), final parse ignoring `in_think` (known-bad).
3. `_render` shapes/titles, the contract product builds on.
4. `_estimate` table incl. cap/floor/media (recalibration becomes a visible diff).
5. Gen-kwargs 458-484: greedy drops samplers, `min_p` only >0, ≤4 stops + tokenizer, pad fallback, seed; `presence_penalty` not forwarded.
6. `_encode_messages` drop ladder 358-379 with a fake template raising TypeError per kwarg (known-bad: ValueError escapes).
7. The 19 positional inputs kept in sync by hand across `chat()` 636-659, `_apply_preset` 909-922, `_ADDL` 1053-1072, `_example_row` 1079-1100: assert they agree.
8. Golden `/v1` transcripts: thinking on, tool call, error, notes, `[DONE]` without `\n\n`, usage.
9. tool_parse known-bads as xfail (string→dict, enum/unknown args, literal `</parameter>`, truncated-call leak).
10. Import smoke in the new tree: `import app` with no stubs, no network, under 5 s.

## Biggest risk in the plan

The seam gets shaped by whichever backend is built first: around the worker it stays a raw-text iterator and hosted's structured deltas get shoehorned through it, so parsing stays in both surfaces; around hosted, the worker grows its own parser and today's UI/API duplication reappears one level down as two backends × three surfaces, and a single production reveal hides the divergence until launch. Cheapest guard: spend the cents first. One metered streamed request through the router with a tool and thinking on, recorded as fixture #1, settles whether the provider returns structured `tool_calls`/`reasoning_content` or raw `<tool_call>` markup, which decides where the parser lives; that recording becomes the first case of the conformance suite the fake, hosted and worker backends must all pass before step 4 merges.