# Hosted-models hunt - BUILD-WAVE PROPOSAL (work units, tests-first, evals, dependencies, where each runs)

- Status: **proposal only**; nothing here is built. Companion to `CONSOLIDATED-GEM-DECISIONS.md` (ids G/ST/TL/PU/T0)
  and `DECISION-QUEUE.md` (ids D1-D13). Written 2026-09-02 against `origin/main` @ `5fa34fda1`.
- Assumes the recommended option (A) for every decision unless a WU says otherwise; where a different option changes a
  WU, the delta is stated.
- **Nothing in any wave starts until the gate in section 1 is green** (D5).

## 0. Two execution surfaces (who can do what)

| Surface | Can | Cannot | Consequence |
|---|---|---|---|
| **Cloud worker** (Linux, Python 3.12, Node 22, pytest, ruff 0.15.17; no `pwsh`, no `uv`, no Windows paths, no live `:8317` / `:11434` / `:1234`, no secrets) | write code + tests, run pytest against stdlib fakes, edit docs, edit `agents.json` / `models.json` and run the validators, run `ruff`, open PRs | run `validate-all-skills.ps1`, run any renderer with `--write`, probe any loopback port, mint tokens, register Scheduled Tasks, run `uv run --locked` servers, measure RSS | every WU below is split into a **cloud-safe** part (code + fixtures + tests + dry-run) and an **owner-run** part (live probe, `--write`, receipts) |
| **Owner on the Windows box** (`~/source/ast-integrate` edits, `~/source/agent-skills-toolchain` executes; SSOT-WIRE) | everything above plus live probes, `--write` merges, smoke + rollback, token minting, Scheduled Task registration, RSS measurement | - | owner-run steps are listed with the exact command shape and the receipt they must leave |

Rule from `AGENTS.md`: helper scripts default to read-only discovery and document stop rules before any risky workflow.
Every renderer below is dry-run by default and prints one `SUCCESS:<name> ...` line for `sync_shared_state.ps1` to gate on.

## 1. The gate (must be green before wave 1 writes anything live) - D5

| # | Condition | Produced by | Evidence |
|---|---|---|---|
| G-a | `tools/mcp/glm53-space/` archived from the box to `archive/glm53-space-2026-09` (or a tarball on `D:\`) | WU-0 (owner) | branch visible on `origin`; `git ls-tree` shows `mcp_server.py`, `glm53_core.py`, `openai_proxy.py`, `uv.lock` |
| G-b | M0 probe receipt committed: for each of auth2api `:8317`, Ollama `:11434`, LM Studio `:1234`, HF router - `GET /v1/models` status + one-line result of `POST /v1/chat/completions`, `POST /v1/responses`, `POST /v1/messages` | WU-0 (owner) | `docs/gem-hunt/2026-09-02-hosted-models/receipts/m0-probe-<date>.json` (no tokens, no bodies) |
| G-c | Fake OpenAI server contract suite green (pass@1 = 1.00) | WU-1 (cloud) | CI step in `quality.yml` |
| G-d | Models registry validator red-proof suite green (13 failing-case tests + seed validates) | WU-2 (cloud) | CI step |
| G-e | Endpoint-eval T1 contract suite green on fakes (pass@1 = 1.00; every error class of the taxonomy hit at least once) | WU-4 (cloud) | second job in `.github/workflows/routing-benchmark.yml` |
| G-f | RAM snapshot: `Get-Process` sum for python / node / ollama and free MB recorded once | WU-0 (owner) | same receipt folder |

If G-b shows auth2api lacks `/v1/responses`, WU-9 (Codex) is **excluded from every wave** until it does, and the routing
report names G1 as the alternative route (L7). If G-b shows it lacks `/v1/messages`, `claude-cursor` is marked `broken`
in the routing report (D9).

## 2. Wave map

| WU | Name | Wave | Depends on | Cloud-safe part | Owner-run part | Decision |
|---|---|---|---|---|---|---|
| WU-0 | Preflight receipts + T0 clicks | 0 | - | - | archive, M0 probe, `OLLAMA_*` env, `mcp-scan`, Space hardware, token + key minting | D1, D7, D8, D9, D10 |
| WU-1 | Stdlib fake OpenAI-compatible server + fault flags | 0 | - | all | - | - |
| WU-2 | Models registry SSOT + validator + seed | 0 | - | all | - | D2 |
| WU-3 | Probe tool (wire + capability, writes the lattice) | 0 | WU-1, WU-2 | code + offline tests | live probes (read-only) | D9 |
| WU-4 | Endpoint eval harness T1 (graders, FakeEndpoint, CI job) | 0 | WU-1 | all | T2/T3 live tiers | D5 |
| WU-5 | Generic inference MCP (`inference`, stdio) | 1 | gate; WU-2, WU-3 | code + tests on fakes; registry entry `enabled:false` | M3 side-by-side run, enable | D3, D6 |
| WU-6 | Tombstone migration of `glm53-space` (+ `qwen-space`) | 1 | WU-5 live-proven | code (registry flip, retired set, tests) | live merges, Cursor reload check, stub in archive | D1 |
| WU-7 | Materializers wave A: Goose, Grok | 2 | gate; WU-2, WU-3 | renderers + golden tests + smoke harness | `--write`, smoke, `E2E_OK` receipts | D4 |
| WU-8 | Materializers wave B: OpenCode, Aider, Fabric, wrapper family + `ai-mode` | 2 | WU-7 pattern | same | same | D4, D6 |
| WU-9 | Codex materializer (last) | 2 | G-b shows `/v1/responses` | renderer + never-chat tests + rollback harness | `--write` against a `CODEX_HOME` copy first | D4, D9 |
| WU-10 | Security controls bundle | 1 (parallel) | WU-2 for the binding rule | all | bind check runs on box | D7 |
| WU-11 | Docs + skill corrections + locks written down | 0 (parallel) | - | edits | `validate-all-skills.ps1`, `sync_shared_state.ps1` | D13 |
| WU-12 | Meta loop: catalog sync, probe ladder, score sidecar, task registration | 3 | WU-2, WU-3 | scripts + tests | task registration, first live sync | D12 |
| WU-13 | Routing policy + PACE + autoresearch dry-run | 3 | WU-4, WU-12 | schema, scorer, dry-run loop on tmp git repo | first capped live run | D11 |
| WU-14 | `hma` hosted-model worker adapter (ACP + agent-mail) | 4 | WU-5, WU-13 | code + fakes | live `:8812` registration, RSS measurement | D13, PU1 |

Parallelism: WU-1, WU-2, WU-4, WU-10, WU-11 are independent and cloud-safe - they can run as 5 concurrent cloud workers
from day one. WU-0 runs on the box at the same time. Waves 1-2 are serialized by the gate and by the L7 rule "nothing is
removed before its replacement has a receipt".

## 3. Work units

Each WU: **scope** (files), **tests first** (what is written before the code), **evals** (capability = what must be observed
true; regression = what must never break; pass@k targets), **dependencies**, **runs where**, **stop rules / rollback**.

### WU-0 - Preflight receipts and TIER-0 clicks (owner, box)

- **Scope (no repo code):** `git -C ~/source/agent-skills-toolchain` push of `tools/mcp/glm53-space/` to `archive/glm53-space-2026-09`
  (T0-1); M0 probe receipt (T0-12) written to `docs/gem-hunt/2026-09-02-hosted-models/receipts/`; user env `OLLAMA_MAX_LOADED_MODELS=1`,
  `OLLAMA_KEEP_ALIVE=2m`, tray restart, LM Studio auto-evict confirmed (T0-8); `uvx mcp-scan@latest scan --local-only --json`
  report filed (T0-9); `Prekzursil/GLM-5.3` Space hardware -> `cpu-basic` after re-checking its status (T0-10); mint
  `HUGGINGFACE_TOKEN_INFERENCE` (D7) and the OpenRouter keys + Guardrail (D8); RAM snapshot (G-f).
- **Tests first:** none (read-only + clicks). The probe script shape is fixed here so WU-3 can reproduce it:
  `GET {base}/models` -> status + id count; `POST {base}/chat/completions` `{"model": <first id>, "messages":[{"role":"user","content":"ping"}], "max_tokens": 1}`;
  `POST {base}/responses` `{"model": ..., "input": "ping", "max_output_tokens": 1}`; `POST {base}/messages` `{"model": ..., "max_tokens": 1, "messages":[...]}`;
  record only `{endpoint, path, http_status, has_expected_shape, latency_ms, server_version_if_any}`.
- **Evals:** capability - the four wire probes answer for all four endpoints (pass@1; a 404/400 is a valid *answer*, not a
  failure); regression - receipt contains no token value and no response body (grep for `hf_`, `sk-`, `Bearer`).
- **Stop rules:** never run the probes while a `cursor-agent` process is alive (G-36); never write `ANTHROPIC_BASE_URL` or
  any global env (G-32); tokens referenced by name only (L6).
- **Rollback:** n/a (read-only); env vars are user-level and reversible.

### WU-1 - Stdlib fake OpenAI-compatible server (`_fake_openai_v1.py`) - TL6

- **Scope:** `tools/mcp/inference/testing/_fake_openai_v1.py` (~250 lines, stdlib `http.server` + `ThreadingHTTPServer`,
  mirrors `tools/mcp/mcp-http-host/_fake_streamable_http_daemon.py`); `tools/mcp/inference/tests/test_fake_openai_v1.py`.
- **Profiles:** `--profile openai` (chat JSON + SSE `data:` / `[DONE]`, `usage` incl. `prompt_tokens_details.cached_tokens`,
  `tool_calls` with string `arguments`, `response_format: json_schema` honoured, `/v1/responses` served); `--profile ollama`
  (rejects `tool_choice`, rejects image URLs, accepts base64 images, `usage` only with `stream_options.include_usage`, 404
  for an unpulled model, `/v1/responses` non-stateful, `/api/show` with `capabilities[]`); `--profile hf-router` (Bearer
  required -> 401, `X-HF-Bill-To` echoed, no cost field, `/v1/models` with `providers[]` carrying `supports_tools`,
  `supports_structured_output`, `pricing`, configurable per provider, model suffix `:provider` parsed); `--profile auth2api`
  (36 fixed `cursor-*` ids, `/v1/responses` and `/v1/messages` **switchable** on/off to reproduce whatever G-b finds);
  `--profile lmstudio` (`/v1/responses` stateful with `previous_response_id`).
- **Fault flags:** `--rate-limit-every N` (429 + `Retry-After`), `--fail-every N` (503), `--slow-first-token S`,
  `--hang-after-tokens N`, `--malformed`, `--echo-secret`, `--restart-every S`, `--drop-tool-calls` (a bridge that flattens
  `tool_calls` into `content` - the `bridge-passthrough` trigger), `--flatten-refusal`.
- **Tests first:** 14 contract tests pin the fake (one per profile behaviour + one per fault flag), request log readable by
  tests (`fake.requests[-1]`).
- **Evals:** regression only - pass@1 = 1.00 (deterministic). Target: 100 % line + branch (house rule for stdlib MCP
  packages in `quality.yml`).
- **Runs:** cloud. **Dependencies:** none. **Rollback:** n/a.

### WU-2 - Models registry SSOT + validator + seed - G2, D2

- **Scope:** `.agents/models.json` (seed rows: `hf-router`, `openrouter` (`sidecarOnly`), `cursor-auth2api` (`retiresWhen`,
  `singletonKey: cursor-bridge`), `ollama`, `lmstudio`, `llamacpp` (disabled), model `glm-5.3@hf-router` with
  `remoteId: zai-org/GLM-5.3`); `.agents/scripts/models_control_plane.py` (clone the idioms of `mcp_control_plane.py`:
  `ENV_REFERENCE_RE`, `LITERAL_SECRET_RE`, closed `x_<runtime>`, `singletonKey`, `atomic_write_text`,
  `assert_exact_target_parity`; new: capability lattice, `api[]`, `discovery{}`, `locks[]`, `resource.ramBytes` warning);
  `.agents/scripts/validate_models_control_plane.py`; `.agents/tests/test_models_control_plane.py`;
  `.provenance/.agents/models.json.md` (why each endpoint exists); `agents.json` gains **no** key for this (the `inference`
  entry in WU-5 carries `x_models.registry` as its only cross-reference).
- **Schema anchors (copied verbatim from the donors named in lens 05/06):** `api[]` values `openai-completions |
  openai-responses | anthropic-messages | google-generative-ai | ollama-native`; `env_key: string | string[]`;
  `auth {command, args, cwd, timeout_ms, refresh_interval_ms}` with the Hermes/Claude stdout contract; `discovery {type:
  ollama | llama.cpp | lm-studio | openai-models-list | proxy, timeoutMs, injectV1}`; model fields `tool_call, reasoning,
  attachment, structured_output, temperature, knowledge, release_date, open_weights, cost.*, limit.*, modalities.*, status`
  (models.dev names) + `models_dev` pointer; `quirks.openai.*` / `quirks.anthropic.*` (Pi `compat` + Grok
  `stream_tool_calls`); `slots {large, small, subagent, web_search, summary, embed}`; `targets {<runtime>: native | fallback
  | unsupported | excluded}`; lattice values `native | probed{at,version} | declared | emulated | absent` for `wire.*` and
  `features.*`, model values may only override downward.
- **Tests first (red-proof, one failing case per rule):** V1 literal `hf_...` anywhere -> error; V2 `auth.env` not
  `^[A-Z][A-Z0-9_]*$`; V3 `http://` non-loopback; V4 OpenAI-compatible `baseUrl` not ending `/v1`; V5 model claims
  `native` above endpoint `absent`; V6 two enabled `cursor-auth2api`; V7 openrouter with `targets.cursor == native` (L1);
  V8 new endpoint on 8765/8812 (L4); V9 unknown `x_codex` key; V10 local `ramBytes` sum over budget -> **warning** (L7);
  V11 `probed` without `{at, version}`; V12 alias to disabled model; V13 `cursor-auth2api` without `retiresWhen` (L3); plus
  V14 `openrouter` row lacking `sidecarOnly`; V15 `deny_callers` missing on `cursor-*` / `openrouter/*` model rows.
- **Evals:** regression pass@1 = 1.00; 100 % branch coverage (mirrors `tools/mcp-manager`'s bar). Capability: the seed
  validates and `select_target_endpoints(registry, "codex")` returns **only** endpoints whose `wire.responses >= probed`
  (so with the seed's `declared` values it returns the empty set until WU-3 writes probes - that emptiness is a test).
- **Runs:** cloud. **Dependencies:** none. **If D2 = B:** the same validator becomes a sub-validator called from
  `mcp_control_plane.validate_registry`, and every V-test moves into `test_mcp_control_plane*.py`; `lastSyncSourceHash`
  churn is accepted. **If D2 = C:** WU-2 shrinks to a JSON-schema for `index.json` and the L1/L3/L4 lock rules move into
  WU-12.

### WU-3 - Probe tool (`models probe`) - ST1, G4

- **Scope:** `.agents/scripts/models_probe.py`: per endpoint L3 (`GET /v1/models` or `discovery.type`-specific path),
  wire probes (`/chat/completions`, `/responses`, `/messages`, one token each), feature probes (`tools=[noop]` with
  `tool_choice: required`, `response_format: json_schema`, base64 image) **only when** the claim is `declared` and never
  observed; writes `probed{at, version}` into `.agents/models.json` via `atomic_write_text`; `--stale-only` honours
  `policy.capabilityProbe.ttlHours`; never prints a token or a body; per-endpoint timeout = `mcp.policy.startupTimeoutMs`.
- **Tests first:** against WU-1 profiles - `ollama` profile -> `wire.responses = probed`, `features.tool_choice = absent`;
  `hf-router` without Bearer -> `BACKEND_AUTH` recorded, lattice untouched; `--drop-tool-calls` bridge -> `features.tools
  = absent` with evidence `tool_calls_in_content`; second run inside TTL is a no-op (byte-identical file); `--restart-every`
  -> no crash. Property test: sample 200 random prompts, none appear in the written registry or stdout.
- **Evals:** regression pass@1 = 1.00 on fakes. Capability (owner, T2/T3): live `probe ollama`, `probe lmstudio`, `probe
  cursor-auth2api`, `probe hf-router` produce the same shape as G-b and write the lattice; pass@3 >= 0.90 for each
  `declared -> probed` flip (a flip that fails 2 of 3 stays `declared` with a `lastError`).
- **Runs:** code + offline tests cloud; live probes owner (read-only on owned ports; token by name). **Dependencies:**
  WU-1, WU-2. **Stop rule:** refuse to run if `INFERENCE_HALT=1` or `.agents/INFERENCE-HALT` exists (C7 kill switch shared
  with WU-5).

### WU-4 - Endpoint eval harness, T1 contract tier - G6, D5

- **Scope:** `tools/endpoint-eval/` (plain Python + pytest; no eval runtime): `graders/tool_fidelity.py` (BFCL-shaped AST
  match: name equal, every emitted arg declared, gold values in accepted list with `""` = optional; `parallel` order-
  independent 1:1; `irrelevance` = zero calls; `schema-strict` via `jsonschema`), `graders/json_axis.py` (`valid_json_rate`,
  `schema_valid_rate`, `strict_honoured`, `refusal_field_rate`), `graders/bridge_passthrough.py` (raw wire diff before /
  after a bridge: `tool_calls` and `tool_call_id` survive; `refusal` not flattened), `graders/latency.py` (TTFT first chunk
  / first reasoning token, tok/s last-80 %, e2e; p50/p95; `insufficient` under n = 20), `graders/cost.py` (provenance
  classes `provider_reported | table_estimate | unknown_price | local_zero`; `cost_usd = null` for quota),
  `graders/passk.py` (Chen et al. pass@k and tau-bench pass^k estimators), `fake_endpoint.py` (replays recorded OpenAI-wire
  fixtures incl. a 429 storm, a stringified-arguments blob, a `refusal` field, a bridge that strips `tool_calls`),
  `fixtures/` (12 house tools sampled from the 42-server registry with gold arg sets; 15 house JSON schemas taken from
  `agents.json` entries, `.autoresearch/log.tsv` rows, `tools/fanout-schema`), `score_policy.py` (later, WU-13),
  `tests/`; CI: a second job `endpoint-eval-fakes` in `.github/workflows/routing-benchmark.yml` + a `quality.yml` step.
- **Tests first:** golden files for every grader; the decision table keep / discard / crash / insufficient (used by
  WU-13); fixture-freshness test (recorded wire still parses under the declared schema); registry-integrity test (every
  policy entry names an existing registry id; no URL / secret in the policy file).
- **Evals (definitions used by every later WU):**
  - **T0 unit** (CI, every push): 100 % line + branch on graders.
  - **T1 contract** (CI, every push, fakes only): every error class of WU-5's taxonomy hit >= 1; `bridge-passthrough` fails
    closed as `capability-absent` on the `--drop-tool-calls` fake; **pass@1 = 1.00**.
  - **T2 local live** (box, nightly / on demand; Ollama on the RTX 4050, LM Studio; $0): capability set for
    `qwen2.5-7b@ollama` - `tools_roundtrip` (5 prompts), `tool_choice_required` (3), `json_schema_native` (5) + `prompted`
    delta, `vision_base64` (2 tiny PNGs), `usage_reported`, `reasoning_effort` low vs high, `context_probe` 8k / 32k with
    multi-key needles on the repo's own docs, `tool_call_id_roundtrip`; **pass@3 >= 0.90** per probe; below that the
    registry row flips to `false` with `as_of` (not CI red). Pre-check: `nvidia-smi` free >= 5 GiB and free RAM >= 4 GB
    or the run is `insufficient`.
  - **T3 hosted live** (box, weekly, opt-in `INFERENCE_LIVE=1`, capped by each endpoint's `daily_usd_cap` and by the
    OpenRouter per-key daily limit): same probe set for `glm-5.3@hf-router` (pin `:fireworks-ai` / `:baseten` for the
    schema probes; `:together` for latency), one OpenRouter T0 slug, `cursor-*` via `:8317` **only** from the box, never
    from CI; **pass@3 >= 0.80**; misses update the registry and tag the ledger line `eval`.
  - **Reliability gates** (anything that routes a task class): **pass^3 = 1.00** on `simple` tool fidelity and
    `schema_valid_rate` for `extract-json`; n >= 4 trials; 429/5xx count as `insufficient`, never as fast.
- **Runs:** cloud (T0, T1); owner (T2, T3). **Dependencies:** WU-1. **Never in CI:** any call to `:8317`, any OpenRouter
  key, any credential rotation.

### WU-5 - Generic inference MCP `inference` (stdio, D3 = A) - G1

- **Scope:** `tools/mcp/inference/` (`mcp_server.py` stdio JSON-RPC, `registry.py` (reads `.agents/models.json`, reloads on
  mtime), `client.py` (OpenAI-compatible HTTP; SSE consumed internally for TTFT + partial results; `timeout_s`; 2 retries
  with jitter on 429 honouring `Retry-After`), `redaction.py` (lift `_is_sensitive_key` / `redact_obj` / `redact_text`
  from `tools/mcp/proxy-mcp/redaction.py` into `tools/mcp/_shared/redaction.py`; add OpenRouter Secrets-preset formats and
  exact-value match of the 18 registry credentials loaded from env at start), `ledger.py` (JSONL, one line per call, daily
  rotation, `cost_basis`, never text; mirrors `_shared/hardening.py`'s bounded sink), `errors.py` (the 17-class taxonomy;
  tool-execution errors, never protocol errors), `compat_glm53.py` (`glm53_chat(user_prompt, system_prompt)` -> `chat`),
  `README.md`, `pyproject.toml` + `uv.lock` (the launcher is `uv run --locked` like glm53-space), `tests/`);
  `.agents/agents.json`: new entry `inference` (stdio, `targets: ["claude","codex"]`, `requiredEnv` = union of `auth.env`
  over enabled endpoints, `credentialNames` equal, `x_models: {"registry": ".agents/models.json"}`, `singletonKey:
  inference`, tags `approved, hosted-inference, owner-requested, stdio`, **`enabled: false`** at landing); `mcp_control_plane.py`
  learns the one new key `x_models` (closed: `registry` only).
- **Tool surface:** `models_list(filter?)`, `chat(model, messages, tools?, tool_choice?, response_schema?, profile?,
  max_tokens?, temperature?, reasoning_effort?, content_class?, allow_redacted_send?, max_result_chars?, timeout_s?,
  idempotency_key?)`, `probe(endpoint | model, checks?)`, `budget_status(endpoint)`, `inference_fetch(result_id, offset)`.
  **Deliberately absent from every schema:** `base_url`, `api_key`, `provider`, `headers` (transcript-exfiltration primitive
  under prompt injection). `profile` resolves to a path under `.agents/skills` (L5). Exactly one model round per call; the
  caller executes `tool_calls` (hard rule 3). `openrouter/*` rows carry `deny_callers: ["cursor", "claude-code"]`;
  `cursor/*` rows (`:8317`) carry `deny_callers: ["cursor"]` and `enabled: false` by default (L1, L3). No shell, file or
  fetch tools. `/healthz`-equivalent for stdio = `probe` on itself.
- **Tests first (all on WU-1 fakes):** every error class has one trigger test; redaction: 12 seeded secrets across
  positions -> `REFUSED_SECRET_IN_PROMPT` with correct indexes, `allow_redacted_send` -> fake receives masked text,
  `--echo-secret` -> `echo_masked: 1`; `content_class: private` x every `data_class`; ledger never contains any prompt
  substring (property test, 200 prompts); `BUDGET_EXCEEDED` fires at the cap and not a cent early; chunking: 60k-char reply
  -> `truncated: true` and `inference_fetch` reassembles byte-identical; `--hang-after-tokens 40` -> `TIMEOUT_PARTIAL` with
  40 tokens; `--slow-first-token 999` -> `TIMEOUT_NO_OUTPUT`; `structured_mode` always present (`native` / `prompted` /
  `unsupported`); `UNSUPPORTED_CAPABILITY` when `tools` sent to `features.tools = absent`; `capabilityReport.tools =
  "emulated"` when the prompt-format loop ran; `CALLER_DENIED` for `clientInfo.name = cursor` + `cursor/*`; **deprecation
  parity**: replay 10 `glm53_chat`-shaped calls through `compat_glm53` against the archived `glm53_core.py` oracle (from
  G-a) and assert equal result schema (`content` string, no `tool_calls`).
- **Evals:** T1 pass@1 = 1.00; 100 % branch; T2/T3 per WU-4 once enabled. **Capability (owner, M3):** with `inference`
  enabled beside `glm53-space`, `claude mcp list` shows both; `chat(model="glm-5.3@hf-router")` returns the same answer
  shape as `glm53_chat` on the 7.2 fixture prompt.
- **Runs:** cloud (code, tests, registry entry `enabled:false`, dry-run of the three MCP merges to prove parity
  assertions still hold); owner (M2 probe, M3 enable + Claude merge `--write`). **Dependencies:** gate; WU-2, WU-3.
  **If D3 = B:** add `transport.py` (Streamable HTTP, sessions lenient per ST11, 403 on bad `Origin`, semaphore 4) and a
  `/v1` face (`GET /v1/models`, `POST /v1/chat/completions` with registry ids; omits `cursor/*` and `openrouter/*`);
  registry entry becomes `transport: http`, `url: http://127.0.0.1:8901/mcp`; supervision via `run_host.ps1` pattern;
  port free-ness checked on the box first. **Rollback:** flip `enabled`; nothing else changes.

### WU-6 - Tombstone migration of `glm53-space` and `qwen-space` - G7, D1

- **Scope (code, cloud-safe):** `.agents/agents.json` `glm53-space`: `enabled: false`, description prefixed `RETIRED
  2026-09-xx - redirect tombstone. Hardcoded router.huggingface.co/v1 + zai-org/GLM-5.3. Use inference.models_list then
  inference.chat with model "glm-5.3@hf-router".`, tags `+= retired, redirect-tombstone`; `merge_generated_codex_mcp.py`
  `RETIRED_MCP_SERVERS = {memory, codex_consult, glm53-space}`; `merge_generated_cursor_mcp.py`
  `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS = CURSOR_DEFAULT_APPROVED_SERVERS | {"inference"}` (the owner-requested default
  adapter slot moves, count stays core six + one); `test_mcp_control_plane_live.py`: retire
  `test_glm53_uses_locked_absolute_uv_and_is_owner_requested_default` and add the same assertion for `inference`; attach-set
  tests updated; `.provenance/.agents/agents.json.md` gains the why + replacement id; `skills/qwen-space-tool-api/SKILL.md`
  (SSOT copy on the box, mirrored per `AGENTS.md`) upgraded to the `codex-consult` form (`RETIRED <date> - redirect
  tombstone`, "Do not follow the old procedure", "Use instead" table -> `hosted-model-agents` + `inference.models_list`,
  "Why a tombstone and not a deletion"); its `reference.md` moved under `hosted-model-agents/recipes/` with a pointer.
- **Owner-run:** in the archive branch, replace `mcp_server.py` body with a stub whose single tool `glm53_chat` returns
  the redirect text and exits 0 (so the registry path keeps resolving during the overlap); run the three merges
  `--write`; `claude mcp list` no longer shows `glm53-space` after M5; Cursor approval store shows no orphan
  `glm53-space-<hex>` prompt; `qwen-space` wrapper prints the "Use instead" table and exits 2; one release later remove
  the registry entry and the stub directory; keep the name in `RETIRED_MCP_SERVERS` forever.
- **Tests first:** golden merge fixtures: a Codex `config.toml` containing `[mcp_servers.glm53-space]` -> removed;
  a Cursor `mcp.json` with the old approval id -> reported as retired, not as unapproved; `merge(merge(live)) ==
  merge(live)`; parity assertion still fails closed when a generated block is deleted before write.
- **Evals:** regression pass@1 = 1.00 on fixtures; acceptance per migration step as in lens 06 §7.5 (M3 same schema;
  M5 `.claude.json` lacks `glm53-space`; M6 wrapper exits 2; M8 `rg glm53-space` hits only tombstones,
  `RETIRED_MCP_SERVERS` and these docs).
- **Runs:** cloud (code + fixtures); owner (live merges, Cursor reload, stub). **Dependencies:** WU-5 proven live (M3).
  **Stop rule:** abort if `inference.chat` cannot reproduce a `glm53_chat` answer for GLM-5.3 (capability loss, L7).
  **Rollback:** flip two booleans and restore the attach set - a two-line diff; both servers stay defined throughout the
  overlap.

### WU-7 - Materializers wave A: Goose, Grok - G3, D4

- **Scope:** `.agents/scripts/merge_generated_goose_models.py` (file-set merge into
  `%APPDATA%\Block\goose\config\custom_providers\<id>.json`: `engine: "openai"`, `base_url`, `base_path:
  "v1/chat/completions"`, `api_key_env`, `models[]`, `requires_auth`; marker `managed-by: .agents/models.json <hash>` in
  `description`; write / delete only marked files; the hand-written `goose-cursor-proxy.json` is untouched unless marked);
  `.agents/scripts/merge_generated_grok_models.py` (block splitter as the Codex MCP merge, header regex `^model\."..."$`;
  one `[model."<model-id>"]` per registry model with `env_key = [auth.env, ...altEnv]`, `api_backend` = best available
  wire, `context_window`; optional `[endpoints] models_base_url` for `cursor-auth2api` **only if G-b proved
  `/v1/models`**; the live `[model."cursor-grok-4.6"]` is imported as a live-only block when not registry-named; never
  `api_key =`); shared `.agents/scripts/models_materialize_common.py` (select, floor, routing report, `SUCCESS:` line,
  pre-write copy, post-write smoke runner, rollback); `.agents/tests/test_merge_generated_{goose,grok}_models.py`.
- **Tests first:** idempotency `merge(merge(live)) == merge(live)`; preservation (unmarked Goose file untouched; Grok
  `[models]` / `[endpoints]` / unmanaged `[model.*]` byte-identical); never `api_key =` in rendered Grok TOML; routing
  report line for every excluded (endpoint, runtime) pair with `reason` and `alternative`; parity fail-closed; smoke
  harness test: inject a bad block into a *copy*, point `GROK_HOME` / `XDG_CONFIG_HOME` at the copy, assert the smoke
  fails and the copy is restored byte-for-byte.
- **Evals:** regression pass@1 = 1.00 on fixtures. Capability (owner): `goose info` and `grok inspect` exit 0 after
  `--write`; `grok -m <alias> "Reply with exactly: E2E_OK"` for one HF-router model and one local model returns `E2E_OK`
  (pass@3 = 1.00 - a config, not a model, is under test); Grok `[endpoints]` gated: abort if `/v1/models` on auth2api is
  absent or returns fewer than the current 36 ids (L7).
- **Runs:** cloud (renderers, fixtures, tests); owner (`--write`, smoke, receipts). **Dependencies:** gate; WU-2; WU-3
  probes for the endpoints rendered. **Stop rule:** never run `--write` while a `cursor-agent` process is alive (G-36).
  **Rollback:** pre-write copy (`config.toml.bak-<date>`, the estate's existing habit) restored by the harness.

### WU-8 - Materializers wave B: OpenCode, Aider, Fabric, wrapper family + `ai-mode` - G3, D4, D6

- **Scope:** `merge_generated_opencode_models.py` (JSON key merge of `provider.<id>` into
  `~/.config/opencode/opencode.json`: `npm: "@ai-sdk/openai-compatible"`, `options.baseURL`, `options.apiKey: "{env:NAME}"`,
  `models{}`; dot-free ids; never `{file:}`; verify current key names via `config/v2-compat` at render time);
  `merge_generated_aider_models.py` (`~/.aider.model.metadata.json` entries `openai/<remoteId>` with per-token costs
  (per-1M / 1e6), `~/.aider.model.settings.yml` list merge by `name` with `# managed` comment, `~/.aider.conf.yml` `alias:`
  merge; `litellm_provider == "openai"` prefix rule); `merge_generated_fabric_models.py` (fenced region `# >>> models.json
  managed >>>` / `# <<< ... <<<` in `~/.config/fabric/.env`: `LM_STUDIO_API_URL`, `OLLAMA_API_URL`, and the one
  `aliases.fabric-default` endpoint as `OPENAI_API_BASE_URL` + `OPENAI_API_KEY=${NAME}` reference; emits
  `disableResponsesAPI: true` into `config.yaml` with a printed global-tradeoff warning when `wire.responses < probed`;
  discovers the installed vendor list from `fabric -L` output instead of hardcoding); `merge_generated_wrappers_models.py`
  (`~/.local/bin/<cli>-on-<upstream>` `.ps1` + `.cmd` shims: read `auth.env` value from `local.json` via `auth.localJsonPath`
  read-only, export it and `OPENAI_API_BASE(_URL)` for one process, `exec` the CLI; header `# managed-by: .agents/models.json
  <hash>`; old names `fabric-cursor`, `claude-cursor`, `codex-cursor`, `grok-mode` become one-line shims; `ai-mode status |
  use <cli> <upstream> | native <cli> | rollback` reads the registry; **`claude-on-*` rendered only for endpoints whose
  `anthropic-messages` probe passed and never for `openrouter`** (L1)); tests per script.
- **Tests first:** as WU-7 plus: wrapper sentinel test (fixture `local.json` with `SENTINEL_NEVER_PRINT`; assert absent
  from every rendered file and from stdout); OpenCode fixture with an unmanaged provider and `$schema` / `model` / `mcp`
  keys preserved; Aider metadata regression (#2928 shape: missing prefix -> validator error); Fabric fence idempotent and
  content outside the fence byte-identical.
- **Evals:** regression pass@1 = 1.00. Capability (owner): `opencode models`, `aider --list-models openai/`, `fabric -L`
  exit 0; each `<cli>-on-<upstream>` completes the `E2E_OK` one-liner (pass@3 = 1.00); `ai-mode status` shows every CLI on
  `native` by default (opt-in stance preserved).
- **Runs:** cloud (code, tests); owner (`--write`, receipts; `.pre-R3` copies of the old scripts kept one release).
  **Dependencies:** WU-7 pattern. **Rollback:** `ai-mode rollback` copies the `.pre-R3` scripts back; fence / key merges
  restored from pre-write copies.

### WU-9 - Codex materializer (last) - G4, D4, D9

- **Scope:** `merge_generated_codex_models.py` extending the Codex MCP merge's block splitter to `model_providers.*` and
  `profiles.<managed-id>`: `[model_providers.<id>]` with `name, base_url, env_key, wire_api = "responses",
  http_headers?, env_http_headers?, query_params?` + optional `[profiles.<id>]`; **never** touches top-level `model` /
  `model_provider` (OpenRouter stays non-default, L1); never shadows built-in ids `openai / ollama / lmstudio`; floor
  `wire.responses >= probed`; post-write smoke `codex --version` and `codex login status` with `CODEX_HOME` pointed at the
  written dir; rollback on non-zero.
- **Tests first:** grep-based invariant - rendered TOML never contains `wire_api = "chat"` for any fixture; a fixture
  registry whose only endpoint is chat-only renders **zero** Codex blocks and one routing-report line
  `codex: excluded <id> reason=wire:responses=absent alternative=inference-mcp`; preservation of unmanaged
  `[model_providers.mine]` and all `[mcp_servers.*]` blocks; local-only sub-table preserved per `is_replaceable_suffix`;
  smoke/rollback test against a deliberately bad copy.
- **Evals:** regression pass@1 = 1.00. Capability (owner): `codex --version` exits 0 after `--write`; `codex --profile hf
  -m zai-org/GLM-5.3:novita "Reply with exactly: E2E_OK"` returns `E2E_OK` (pass@3 = 1.00). The `cursor-auth2api` block is
  rendered only if G-b proved `/v1/responses`.
- **Runs:** cloud (code, tests); owner (`--write` against a copy first, then live). **Dependencies:** G-b; WU-7/8
  pattern. **Stop rule:** any smoke failure -> restore and stop the wave; Codex is a primary rail.

### WU-10 - Security controls bundle - ST7, PU9, TL5, T0-2, T0-5

- **Scope:** (a) L0 path-exists check in `validate_mcp_control_plane.py` (`--check-paths`, report-only, Windows paths
  mapped via a `--root` flag so it can run in cloud against fixtures) and the same rung in `hooks/tool-preflight/preflight.py`;
  (b) credential-to-issuer host binding rule in `models_control_plane.py` (`hf_*` names -> `*.huggingface.co`,
  `OPENROUTER_*` -> `openrouter.ai`; a profile that would send `HUGGINGFACE_TOKEN*` to `*.hf.space` fails validation) and
  `allow_redirects=False` in `client.py`; (c) `stranger-space` tag rule (any `*.hf.space` / Gradio base URL requires it;
  forces `content_class: public` and disables `tool_calls`); (d) local-bind check (PowerShell `Get-NetTCPConnection` for
  `0.0.0.0:11434` / `:1234` / `:8080`, Ollama version >= 0.17.1) as one function in `tools/mcp/mcp-host-supervisor/` or
  the preflight, plus the zombie-runner check (`Get-Process ollama*` vs `/api/ps`); (e) `openrouter-complete.py`:
  `provider.require_parameters = true` when `tools` / `response_format` present, `--deny-data-collection` default on,
  `--rank` mode from `benchmarks.artificial_analysis` skipping `expiration_date` < 30 days; (f) `INFERENCE_HALT` kill-switch
  file + env honoured in-process by WU-3 and WU-5.
- **Tests first:** fixture registries for (a)-(c) with one failing case each; unit tests for the `--rank` scorer and the
  two request fields (assert the JSON body); bind-check tested with a fake `Get-NetTCPConnection` output table.
- **Evals:** regression pass@1 = 1.00; (a) run against the real `agents.json` with `--root` pointing at a fixture tree that
  lacks `tools/mcp/glm53-space` must **report** exactly that entry.
- **Runs:** cloud (all code); owner (bind check live). **Dependencies:** WU-2 for (b)/(c). **Locks:** L6 (values never
  logged; `name+length` only), L1.

### WU-11 - Docs, skill corrections, and the locks written down once - T0-3, T0-4, T0-6, T0-7

- **Scope:** `CLAUDE.md`, `AGENTS.md`, `skills/multi-ai-mingle/{SKILL,MOUNT}.md` (+ `.agents/skills` mirror per `AGENTS.md`):
  one paragraph "as of 2026-08-24 `codex mcp-server` is deprecated upstream; mount kept; migration target app-server / ACP";
  `.agents/skills/openrouter-routing/SKILL.md`: prices -> slugs + "verify with the live GET", promote `z-ai/glm-5.2:free`
  to the smoke slug; `skills/hosted-model-agents/environments.md`: add the **router** row (`router.huggingface.co/v1`,
  chat-only, suffixes, `/v1/models` flags, $2 PRO credits then PAYG), fix Gradio MCP to 4+, ZeroGPU to RTX Pro 6000
  Blackwell 48/96 GB with PRO 40 min/day, 60 s call budget, $1/10 min overage, 10-Space cap; Endpoints row gains the
  scale-to-zero contract (1 h idle, 503 vs `X-Scale-Up-Timeout`, quota counted while at zero); local row states the real
  box (RTX 4050 6 GB, `qwen2.5:7b` fit, Ollama on `D:`); `tool-loop.md`: note the Responses API beta and that remote MCP
  execution on the router side must be opted out (rule 3); `evals.md`: add the Heretic-ARA featherless probe (PU5) and the
  Space wake-latency measurement as open items; **new `docs/plans/estate-locks.md`** (or a section in root `AGENTS.md`,
  owner's choice) writing L1-L7, G-32, G-36 down once with the file each currently lives in, so future hunts cite one place
  (V18 found them distributed); lens 04 header note "PARTIAL; GPU premise corrected".
- **Tests first:** `ssot_wiring_check.py`-style grep test that every path named in the locks file exists; markdown table
  lint (no raw `|` inside code spans in table rows - the bug this synthesis had to fix in itself).
- **Evals:** regression only: `validate-all-skills.ps1` green on the box (cannot run in cloud); `sync_shared_state.ps1`
  green.
- **Runs:** cloud (edits); owner (skill validation + sync). **Dependencies:** none. **Locks:** L5 (edit the SSOT copy;
  never a second diverged copy), L7 (the mount stays).

### WU-12 - Meta loop: catalog sync, probe ladder, score sidecar, task registration - G10, TL1, TL2

- **Scope:** `command-center/ssot/catalog_sync.py` (stdlib; feeds: models.dev `api.json`, OpenRouter `/api/v1/models`,
  HF router `/v1/models`, MCP Registry `/v0.1/servers?updated_since=&version=latest`, loopback `/v1/models` of `:8317` /
  `:11434` / `:1234`, vendor status feeds for providers actually referenced; ETag / `If-Modified-Since` cache; last-known-good
  on failure; output `state/catalog/<feed>.json` + `state/catalog/index.json`; **the diff is the product**: new / vanished
  models, `expiration_date`, `status != live`, upstream version moves, decommissioned hosts such as
  `api-inference.huggingface.co`); `hooks/mcp-liveness/liveness.py` gains `--mode all` running L0 static -> L1 `initialize`
  -> L2 `tools/list` hash pin (`toolDigest` compare, quarantine on drift) -> L3 `/v1/models` -> L4 one-token only when
  `claim_gap != 0` -> L5 `mcp-scan --local-only --json`; `state/capability-scores.json` sidecar (score = 40 availability +
  20 capability match + 15 latency vs own baseline + 10 freshness + 10 security + 5 claim agreement; states `live /
  degraded / quarantined / deprecation-candidate / retired` with hysteresis from `mcp.supervision`); a generated block
  appended to `hooks/capability-catalog/catalog.json` from `index.json`; `scripts/register-catalog-task.ps1` in the
  `register-tasks.ps1` style (`MultipleInstances IgnoreNew`, `Global\` mutex, daily quiet hour, skip when above
  `totalIdlePrivateBytes`); `OPENCODE_MODELS_PATH` pointed at the synced models.dev copy (documented, not forced).
- **Tests first:** fake feeds (recorded JSON) -> normalised index golden file; diff detection for each event kind;
  ETag round-trip (304 -> unchanged file); last-known-good used when a feed 500s; hash-pin drift -> `changed`; score
  arithmetic table-driven; state machine hysteresis (2 consecutive good runs to leave `degraded`); never writes to
  `agents.json` (assert file unchanged).
- **Evals:** regression pass@1 = 1.00. Capability (owner): first live sync produces an index whose `cursor-auth2api`
  row lists 36 ids (or the report says why not); probe ladder finishes inside `startupTimeoutMs` per endpoint; L0 flags the
  dangling `glm53-space` path until WU-6 completes.
- **Runs:** cloud (scripts, tests); owner (task registration, first sync, weekly `mcp-scan`). **Dependencies:** WU-2,
  WU-3. **Locks:** L2 (task + hooks, no daemon), L4, L6, L7 (nothing auto-retires), closed-schema (sidecar).

### WU-13 - Routing policy + PACE + autoresearch dry-run - G9, PU3, PU4, ST8, D11

- **Scope:** `.agents/routing-policy.json` (closed schema; `task_class -> {primary, escalate_to, floors, exponents,
  spend_share, pace: {P, A, C, E, triggers}, justification, pinned_until}`; names only; provenance in
  `.provenance/.agents/routing-policy.json.md`); `tools/endpoint-eval/score_policy.py` (routing score
  `quality^a * speed^b * cost^c` with hard floor; BestSingle null hypothesis; PerfGain / CostSave; bootstrap-CI noise
  margin; `log.tsv` columns incl. `spend_usd`, `spend_cum_usd`, `quota_units`, `n_trials`, `perf_gain`, `cost_save`,
  `p95_worst_ms`, status `keep | discard | crash | insufficient`); PACE validator (each rung a different *means*: at most
  one `cursor-*` rung, at least one non-network rung, E is a procedure step naming `basic-memory :8765` and `agent-mail
  :8812`; OpenRouter rung only in CLI/Codex classes - fails closed); `review-routing` skill (monthly report
  `modified / justified-not-modified` per class, including one shadow-eval against a non-routed endpoint; honours
  `pinned_until`); wrappers from WU-8 read the policy with a loud fallback.
- **Tests first:** schema tests (a variant that deletes a class or endpoint is invalid - L7; a `sunset_on` primary without a
  non-sunset escalation is invalid - L3); PACE distinguishability tests; dry-run autoresearch loop on a throwaway git repo in
  `tmp_path` with a seeded fake scorer proving commit-before-measure, log-before-revert, reflog recoverability, the 3-discard
  stop, the 8-variant plateau, the spend stop and `insufficient` handling.
- **Evals:** regression pass@1 = 1.00. Capability (owner, capped): one real run of <= 8 variants with per-variant spend
  <= cap/40; wrap-up prints baseline-vs-best per axis and PerfGain / CostSave vs BestSingle; if both <= 0 the honest output
  is "route everything to BestSingle".
- **Runs:** cloud (schema, scorer, dry-run); owner (live run). **Dependencies:** WU-4, WU-12. **Locks:** L1 (refuse to
  start without OpenRouter caps set), L3, L5 (review skill in `.agents/skills`), L7.

### WU-14 - `hma` hosted-model worker adapter (ACP + agent-mail) - PU1, PU2, D13

- **Scope:** `tools/hma/` (~400-600 lines): face A ACP agent over the official `agent-client-protocol` Python SDK (v1;
  `protocolVersion: 2` accepted only behind a flag; `initialize / new_session / prompt / session_update /
  request_permission`), face B agent-mail peer reusing `tools/crcp/crcp/bus.py` (`ensure_project -> register_agent
  (program="hma:<profile>", model="<checkpoint>@<runtime>")`, manual `respond_contact` by the human, `fetch_inbox` poll with
  backoff, `file_reservation_paths` around every write, `reply_message`), core = the `tool-loop.md` loop calling WU-5's
  `client.py` (or `inference.chat` directly), face C CLI `hma run --profile --runtime [--acp] [--mail] [--watch]`; extend
  `skills/multi-ai-mingle` `VERIFY_PLAN` probe with a third identity; `commands/multi-ai-mingle.md` one-line pointer.
- **Tests first:** ACP echo-agent conformance (SDK examples as fixtures); a fake agent-mail server (JSON-RPC over loopback,
  stateless) for register / contact / inbox / lease flows; lease conflict surfaces as a tool error, never a force-release;
  eval traffic never uses the mail channel (licence rider) - assert by fake request log.
- **Evals:** regression pass@1 = 1.00. Capability (owner): register one `hma` identity on `:8812`, accept contact from a
  Claude session, round-trip one `ack_required` message and one lease (pass@3 = 1.00); measure RSS per worker
  (`Get-Process -Name python | Measure-Object WorkingSet64 -Sum`) before raising any cap; start at 4 hosted + <= 2 Codex
  under the CODEX_FANOUT cap of 3.
- **Runs:** cloud (code, fakes); owner (live). **Dependencies:** WU-5, WU-13. **Locks:** L2 (official SDK only; no
  `pydantic-acp` / `langchain-acp`), L3 (auth2api only via the G-32 wrapper), L4 (client of `:8812`, never a server), L7.

## 4. Dependency graph (text)

```
WU-0 (owner receipts) ---------+--------------------------------+
WU-1 fake -> WU-3 probe -------+--> GATE (D5 green) --> WU-5 inference MCP --> WU-6 tombstone
WU-2 registry -> WU-3 ---------+                     \-> WU-7 Goose/Grok --> WU-8 OpenCode/Aider/Fabric/wrappers --> WU-9 Codex (if G-b)
WU-4 eval T1 ------------------+                      \-> WU-12 meta loop --> WU-13 policy/PACE/autoresearch --> WU-14 hma
WU-10 security  (parallel from day one; (b)/(c) after WU-2)
WU-11 docs/locks (parallel from day one)
```

## 5. Eval summary (targets in one place)

| Suite | Where | k | Target | On miss |
|---|---|---|---|---|
| Unit (every WU) | CI | - | 100 % line + branch | CI red |
| T1 contract on fakes (WU-1, WU-3, WU-4, WU-5, renderers) | CI | 1 | pass@1 = 1.00 | CI red (a bug in *our* code, never in a model) |
| Capability, local live (T2: Ollama / LM Studio on the RTX 4050) | box, nightly | 3 | pass@3 >= 0.90 | registry row -> `false` with `as_of`; not CI red |
| Capability, hosted live (T3: HF router, OpenRouter T0 slug, `:8317`) | box, weekly, capped | 3 | pass@3 >= 0.80 | same + ledger line tagged `eval` |
| Reliability for anything that routes a task class (`simple` tool fidelity, `schema_valid_rate`) | box | 3 (n >= 4) | pass^3 = 1.00 | class ineligible for that endpoint |
| Renderer receipts (`E2E_OK` one-liners per CLI) | box | 3 | pass@3 = 1.00 | wave stops; rollback |
| Policy loop (WU-13) | box, capped | - | improvement > 1 pp and CI non-overlap; PerfGain or CostSave > 0 vs BestSingle | discard / "route to BestSingle" |

## 6. What the owner must never delegate to a cloud worker

- Any `--write` against a live config on the box; any live probe of `:8317`, `:11434`, `:1234`; token or key minting;
  Scheduled Task registration; skill validation (`pwsh` absent in cloud); RSS / free-RAM measurement; the M3 side-by-side
  enable; anything that touches `~/source/agent-skills-toolchain` directly (SSOT-WIRE: edit in `ast-integrate`, push, pull
  into the executed checkout).

Discovery only. No code changed by this document.
