# Hosted-models BUILD WAVE - shared contract (what every work unit codes against)

Status: binding for the build wave on PR #314. Owner answers D1-D13 are in `BUILD-WAVE-STATUS.md`.
This file fixes the interfaces that several work units share so that parallel builders agree.
Nothing here is a runtime artifact; the SSOT data file is `.agents/models.json`.

## 0. Ground rules (estate locks, hard)

- Secrets by environment-variable NAME only (L6). No value ever appears in a registry, rendered config,
  ledger, log, report, test fixture or doc. Literal-secret regex (`hf_`, `sk-`, `ghp_`, `github_pat_`,
  `sk-or-v1-`, `sk-ant-`, `AKIA`, `xox[abp]-`, PEM) fails validation.
- OpenRouter = spend-capped CLI/Codex sidecar only (L1): never Cursor BYOK, never Claude
  `ANTHROPIC_BASE_URL`, never an OpenRouter MCP. Registry rows: `sidecarOnly: true`, `denyCallers`
  contains `cursor` and `claude`.
- No LiteLLM proxy, LangGraph, second orchestration runtime, vector-DB memory (L2).
- auth2api `:8317` is the only Cursor bridge (L3, `singletonKey: cursor-bridge`, `retiresWhen`).
- Owned ports 8765 / 8812 / 8317 / 8770; `inference-hub` is `127.0.0.1:8901` and the ONLY new resident
  process; it idle-exits (default 600 s) (L4).
- Never remove a feature to buy simplicity (L7): `glm-5.3` stays reachable through the hub.
- Cloud workers never: run a renderer `--write` against a real config, probe `:8317` / `:11434` / `:1234`,
  mint tokens, register Scheduled Tasks. Those go to `OWNER-CLICKS.md`.
- Every script is dry-run by default and prints exactly one `SUCCESS:<name> ...` or `FAILED:<name> ...`
  line; `--write` is explicit; idempotent merge semantics (`merge(merge(live)) == merge(live)`).
- Python: stdlib only (CI installs pytest + pytest-cov only), `from __future__ import annotations`,
  ruff 0.15.17 clean (`ruff format --check` + `ruff check`), basedpyright standard clean on source.
  Tests: pytest, 100 % line + branch on the module under test (`--cov-branch --cov-fail-under=100`);
  `# pragma: no cover` only for OS-specific branches, each with a one-line reason.
- Do not touch files outside your work unit's file list. Do not run `git commit` / `git push`; the
  orchestrator commits.

## 1. `.agents/models.json` (registry SSOT) - schema v1

Top level: `schemaVersion` (1), `description`, `policy`, `locks[]`, `endpoints{}`, `models{}`,
`aliases{}`, `slots{}`. Closed schema: unknown top-level keys are errors.

`policy`: `capabilityProbe.ttlHours` (int), `localRamBudgetBytes` (int), `defaultTimeoutMs` (int),
`hub{host, port, idleExitSeconds, maxInFlightTotal, ledgerPath, haltFile, haltEnv}`.

`locks[]`: `{id: "L1".., rule: str, enforcedBy: [str]}`. Every `locks` reference on an endpoint must
name a declared lock id.

### 1.1 Endpoint row (`endpoints.<id>`)

| key | type / values | rule |
|---|---|---|
| `label`, `description` | str | required, nonempty |
| `kind` | `hosted` / `local` / `bridge` | required |
| `enabled` | bool | required |
| `baseUrl` | URL | `https://` for hosted; `http://` only for loopback (`127.0.0.1`, `localhost`, `[::1]`); must end in `/v1` when `api` has an `openai-*` value |
| `api[]` | `openai-completions` / `openai-responses` / `anthropic-messages` / `google-generative-ai` / `ollama-native` | nonempty, no duplicates |
| `auth` | `null` or `{env, altEnv[], scheme, header, issuerHosts[]}` | `env`/`altEnv` match `^[A-Z][A-Z0-9_]*$`; `issuerHosts` must cover the `baseUrl` host (credential-to-issuer binding; `*.` prefix wildcard) |
| `wire` | `{completions, responses, messages}` -> lattice | all three keys required |
| `features` | `{streaming, usage, tools, tool_choice, structured_output, vision, reasoning}` -> lattice | all seven keys required |
| `concurrency` | `{maxInFlight: int >= 1}` | required |
| `budget` | `{dailyUsdCap: number or null, costBasis}` | `costBasis` in `provider_reported` / `table_estimate` / `unknown_price` / `local_zero` / `quota` |
| `resource` | `{ramBytes: int >= 0}` | required; local sum rule below |
| `targets` | `{<runtime>: native / fallback / unsupported / excluded}` | all ten runtimes required: `codex grok goose opencode aider fabric cursor claude agy gemini` |
| `discovery` | `{type, timeoutMs, injectV1?}` | `type` in `ollama` / `llama.cpp` / `lm-studio` / `openai-models-list` / `proxy` / `none` |
| `health` | `{kind, path?, timeoutMs}` | `kind` in `openai-models-list` / `http` / `none`; `http` needs `path` |
| `denyCallers[]` | str | required (may be empty except where rules demand entries) |
| `locks[]` | lock ids | required (may be empty) |
| `tags[]` | str | nonempty |
| `sidecarOnly` | bool | required `true` on `openrouter` |
| `singletonKey` | str | optional; two ENABLED endpoints sharing one -> error |
| `retiresWhen` | str | required on `cursor-auth2api` |
| `quirks` | `{openai?: {...}, anthropic?: {...}}` | closed keys: `compat`, `stream_tool_calls`, `thinking_off_for_tools`, `tools_stream` |
| `x_<name>` | object | closed per name (see 1.4); any other key -> error |

### 1.2 Lattice values

A lattice value is either the string `native` / `declared` / `emulated` / `absent`, or the object
`{"state": "probed", "at": "<ISO-8601>", "version": "<str>", "evidence"?: "<str>"}` (both `at` and
`version` required). Rank: `native 4 > probed 3 > declared 2 > emulated 1 > absent 0`. A model row may
override `wire.*` / `features.*` only DOWNWARD (rank <= endpoint rank).

### 1.3 Model row (`models.<id>`)

`endpoint` (existing endpoint id), `remoteId` (what the endpoint expects), `label`, `description`,
`enabled`, `status` (`live` / `eval-gated` / `parked` / `unprobed`), `tier` (`S` / `M` / `L` / `hosted`),
`context` (int), `maxOutput` (int), `modalities{input[], output[]}`, `cost{inputPer1M, outputPer1M,
basis}` (numbers or null; quota-billed rows must be null, never 0), `resource{ramBytes}` (required when
the endpoint is `local`), `quirks` (same closed keys), `denyCallers[]`, `tags[]`, optional `wire` /
`features` downward overrides, optional `modelsDev` pointer, optional `x_<name>`.

Model references accepted everywhere: `<model-id>`, `<model-id>@<endpoint-id>`, or an alias.

`aliases{alias -> model id}`: alias to a disabled or missing model -> error. `slots{large, small,
subagent, web_search, summary, embed}` -> model id or null; exactly these six keys.

### 1.4 Closed extension blocks

- `x_codex`: `env_key`, `wire_api` (only `responses`), `http_headers` (names only), `query_params`.
- `x_grok`: `api_backend`, `context_window`, `models_base_url`.
- `x_goose`: `engine`, `base_path`, `requires_auth`.
- `x_opencode`: `npm`, `provider_id`.
- `x_aider`: `litellm_provider`, `alias`.
- `x_fabric`: `vendor`, `disable_responses_api`.
- `x_hub`: `profile_root`, `max_result_chars`.
- `x_openrouter`: `keys[] {env, label, consumers[], limitReset, optional?}`, `guardrail {providerAllowlist[], modelAllowlist[], dataCollection, secretsPreset, limitUsd}`.
- `x_ollama`: `keepAlive`, `maxLoadedModels`, `numParallel`, `contextLength`, `kvCacheType`, `bind`, `minVersion`.
- `x_lmstudio`: `daemon`, `jit`, `autoEvict`, `idleTtlSeconds`, `bind`.

### 1.5 Validator rules (red-proof test ids; one failing fixture per rule)

V1 literal secret anywhere in the file -> error. V2 `auth.env` / `altEnv` not an env name -> error.
V3 `http://` non-loopback `baseUrl` -> error. V4 OpenAI-compatible `baseUrl` not ending `/v1` -> error.
V5 model lattice above endpoint -> error. V6 two enabled endpoints with the same `singletonKey` -> error.
V7 `openrouter` with `targets.cursor` or `targets.claude` == `native`/`fallback` -> error (L1).
V8 endpoint `baseUrl` on port 8765 / 8812 / 8770, or 8317 on any id but `cursor-auth2api`, or 8901 -> error (L4).
V9 unknown key in any `x_*` block or unknown `x_*` block -> error. V10 local RAM: sum of enabled local
endpoints' `resource.ramBytes` + the largest enabled local model `resource.ramBytes` > `policy.localRamBudgetBytes`
-> WARNING (returned, not raised). V11 `probed` without `at` + `version` -> error. V12 alias -> disabled or
missing model -> error. V13 `cursor-auth2api` without `retiresWhen` -> error (L3). V14 `openrouter` without
`sidecarOnly: true` -> error. V15 `denyCallers` lacking `cursor` on `openrouter` / `cursor-*` endpoints and
their models -> error. V16 lock reference to an undeclared lock -> error. V17 model naming a missing
endpoint -> error. V18 unknown runtime key or value in `targets` -> error. V19 `auth.issuerHosts` not
covering the `baseUrl` host -> error. V20 unknown top-level / endpoint / model key -> error.

## 2. `.agents/scripts/models_control_plane.py` - public API (all renderers, hub, probe, policy use it)

```
ModelsRegistryError(ValueError)
RUNTIMES = ("codex","grok","goose","opencode","aider","fabric","cursor","claude","agy","gemini")
NATIVE_RUNTIMES = ("codex","grok","goose","opencode","aider","fabric")   # take a provider natively
MCP_ONLY_RUNTIMES = ("cursor","claude","agy","gemini")                      # reach models via inference-hub
LATTICE_STATES = ("native","probed","declared","emulated","absent"); LATTICE_RANK = {...}
RUNTIME_FLOORS = {"codex": {"wire.responses": "probed"}, ...others: {}}
DEFAULT_REGISTRY_PATH = <repo>/.agents/models.json
load_registry(path) -> dict
validate_registry(config) -> list[str]            # warnings; raises ModelsRegistryError on the first error
lattice_state(value) -> str ; lattice_rank(value) -> int ; lattice_at_least(value, floor_state) -> bool
effective_capabilities(config, model_id) -> {"wire": {...}, "features": {...}}   # endpoint + downward overrides
resolve_model(config, ref) -> (model_id, model, endpoint_id, endpoint)          # id | id@endpoint | alias
select_target_endpoints(config, runtime) -> dict[endpoint_id, endpoint]  # enabled, targets[runtime] in
        {native, fallback}, every RUNTIME_FLOORS[runtime] floor met; MCP_ONLY_RUNTIMES -> {}
select_target_models(config, runtime) -> dict[model_id, model]           # enabled models on selected endpoints
routing_report(config, runtime) -> list[dict]   # one row per (endpoint, runtime):
        {"endpoint","runtime","decision": "included"|"excluded","reason","alternative","wrappers": "ok"|"unprobed"|"broken"}
        reasons look like "wire:responses=declared<probed", "targets:excluded", "enabled:false", "runtime:mcp-only";
        alternative is "inference-hub" for MCP-only runtimes and for excluded endpoints that the hub serves
credential_names(config) -> list[str]          # union of auth.env + altEnv over ENABLED endpoints, sorted
registry_hash(config) -> str                    # sha256 of the canonical JSON, first 16 hex; the managed-by marker
```

Import idiom (scripts are flat files, not a package): tests and sibling scripts `sys.path.insert(0,
str(SCRIPTS_DIR))` then `import models_control_plane as models`. The module itself imports
`mcp_control_plane` (same directory) for `atomic_write_text`, `atomic_write_json`, `ENV_NAME_RE`,
`LITERAL_SECRET_RE`, `is_credential_name`.

`.agents/scripts/validate_models_control_plane.py`: CLI, exit 0 + `SUCCESS:models-registry ...`, exit 2 +
`FAILED:models-registry <reason>`; `--json` prints the routing report for every runtime; `--registry`.

## 3. Renderers (`.agents/scripts/merge_generated_<runtime>_models.py`)

Shared module `.agents/scripts/models_materialize_common.py`: `RenderResult`, `load_inputs(argv)`,
`managed_marker(config) -> "managed-by: .agents/models.json <hash>"`, `write_with_backup(path, content,
*, backup=True)`, `print_success(name, **counts)`, `print_routing_report(rows)`, `smoke_and_rollback(cmd,
paths, backups)`. Every renderer: `--registry`, `--live <path>`, `--write`, `--no-backup`, `--check`
(drift, exit 1), `--routing-report` (default on; `--quiet` hides it); default = dry run. Idempotent; only
managed blocks/files/keys are touched; unmanaged content byte-identical; never `api_key =` / a literal
value; secrets rendered as the runtime's own env-reference syntax. Codex renderer: never `wire_api =
"chat"`, never touches top-level `model` / `model_provider`, floors `wire.responses >= probed`, smoke
`codex --version` with `CODEX_HOME` at the written copy, rollback on failure.

## 4. `tools/mcp/inference-hub/` (resident concurrent hub, `127.0.0.1:8901`)

Layout: `hub/` package (`registry.py`, `errors.py`, `redaction.py`, `ledger.py`, `budget.py`,
`client.py`, `core.py`, `mcp_face.py`, `v1_face.py`, `server.py`), `testing/fake_openai_v1.py`,
`inference_client.py` (the TUI client), `tests/`, `README.md`, `.coverage-thresholds.json`,
`pyrightconfig.json`. The registry path comes from `INFERENCE_HUB_REGISTRY` or `<repo>/.agents/models.json`;
`hub/registry.py` imports `models_control_plane` by path (`<repo>/.agents/scripts`).

Core (`HubCore`, asyncio): `models_list(filter=None)`, `chat(request)`, `chat_many(requests)`
(asyncio.gather; per-endpoint `asyncio.Semaphore(concurrency.maxInFlight)`; per-call independent
timeouts; one slow call never delays another - tested), `probe(target, checks=None)`,
`budget_status(endpoint=None)`. Outbound HTTP = `urllib` inside `loop.run_in_executor` with a bounded
pool of `policy.hub.maxInFlightTotal` threads; 2 retries with jitter on 429 honouring `Retry-After`;
credentials read from `os.environ[auth.env]` (then `altEnv`) at call time; missing -> `CREDENTIAL_MISSING`.
`INFERENCE_HALT=1` env or the `.agents/INFERENCE-HALT` file -> `HALTED` on every chat.

Error taxonomy (tool-execution errors, never protocol errors): `REGISTRY_UNAVAILABLE, UNKNOWN_MODEL,
MODEL_DISABLED, ENDPOINT_DISABLED, CALLER_DENIED, CREDENTIAL_MISSING, REFUSED_SECRET_IN_PROMPT,
UNSUPPORTED_CAPABILITY, INVALID_ARGUMENT, BACKEND_AUTH, BACKEND_RATE_LIMITED, BACKEND_UNAVAILABLE,
BACKEND_ERROR, MALFORMED_RESPONSE, TIMEOUT_NO_OUTPUT, TIMEOUT_PARTIAL, BUDGET_EXCEEDED,
CONCURRENCY_SATURATED, HALTED`. Every error result carries `{"error": {"class", "message", "retryable",
"endpoint", "model"}}`; messages never contain prompt text or secret values.

Chat request: `{model, messages[], tools?, tool_choice?, response_schema?, max_tokens?, temperature?,
reasoning_effort?, timeout_s?, content_class?: "public"|"private", allow_redacted_send?: bool,
idempotency_key?}`. DELIBERATELY ABSENT (never accepted): `base_url`, `api_key`, `provider`, `headers`.
Chat result: `{model, endpoint, remote_id, content, tool_calls[], finish_reason, usage{prompt_tokens,
completion_tokens, total_tokens}, latency_ms, ttft_ms, structured_mode: "native"|"prompted"|"unsupported",
capability_report{tools, structured_output, streaming}, cost{usd: number|null, basis}, ledger_id}`.
Exactly one model round per call; the caller executes `tool_calls`.

`chat_many`: `{requests: [chat request...]}` OR `{prompt, models: [...], n?: int}` (fan-out of one prompt
to several models or `n` instances of one model). Result `{results: [chat result or error], wall_ms,
max_item_ms, sum_item_ms}`; `wall_ms` must be close to `max_item_ms`, not `sum_item_ms` (the no-HOL test).

Redaction (`hub/redaction.py`): outbound scan of every message for (a) exact values of every credential
env named in the registry that is set in the hub's environment, (b) the literal-secret patterns above ->
`REFUSED_SECRET_IN_PROMPT` with message indexes, unless `allow_redacted_send` (then the masked text is
sent and the result carries `redacted: n`). Logs/ledger: `name+length` only, never values; never prompt
text (sha256 prefix of the prompt instead).

Ledger (`hub/ledger.py`): JSONL under `policy.hub.ledgerPath` (overridable `INFERENCE_HUB_LEDGER`), daily
files `YYYY-MM-DD.jsonl`, one line per call: `{ts, ledger_id, endpoint, model, remote_id, caller,
prompt_sha256_16, prompt_tokens, completion_tokens, latency_ms, status, error_class, cost_usd, cost_basis,
tags[]}`. `budget_status(endpoint)` sums today's `cost_usd` against `budget.dailyUsdCap`;
`BUDGET_EXCEEDED` at the cap, never before; quota rows report `cost_usd: null` and never block on USD.

MCP face (`POST /mcp`, Streamable HTTP, JSON responses; `GET /mcp` -> 405; `DELETE /mcp` -> 200; `Origin`
header present and not loopback -> 403): `initialize` (issues `Mcp-Session-Id`; stale/unknown ids are
accepted leniently and re-initialised, never `-32600`), `notifications/initialized` -> 202, `ping`,
`tools/list`, `tools/call` for `models_list`, `chat`, `chat_many`, `probe`, `budget_status`.
`clientInfo.name` is the caller identity for `denyCallers`. Tool errors -> `isError: true` content.

`/v1` face: `GET /v1/models` (registry model ids; omits `cursor-*` and `openrouter` rows, which are not for
this face), `POST /v1/chat/completions` (OpenAI shape in and out; `stream: true` -> SSE `data:` chunks +
`[DONE]`, emulated from the full result, header `X-Inference-Hub-Stream: emulated`), errors as OpenAI
`{"error": {"message", "type", "code"}}` with the taxonomy class in `code`. `GET /healthz` -> `{ok, pid,
started_at, idle_seconds, in_flight, registry_hash, idle_exit_seconds}`.

Server (`hub/server.py`): `ThreadingHTTPServer` on `127.0.0.1:<port>` (default 8901), one asyncio loop in
a background thread running `HubCore`; bind failure = another hub owns the port -> print
`FAILED:inference-hub port-owned` and exit 3 (the bind IS the single-instance mutex). Idle-exit watchdog:
exit 0 when `idle_seconds >= idleExitSeconds` and `in_flight == 0`; `--idle-exit-seconds 0` disables.
CLI: `--port --host --registry --idle-exit-seconds --ledger --log-level`; prints
`SUCCESS:inference-hub listening=127.0.0.1:8901 pid=<pid> registry_hash=<hash>`.

Stdio shim `.agents/scripts/inference_hub_stdio.py`: reuses `bm_cursor_http_session.py` (`BmHttpSession`,
`StdioBridge`, `DiscoveryCache`) unchanged; `--url` default `http://127.0.0.1:8901/mcp`; on
`TransportUnavailable` at startup or on a call it lazy-starts the hub once (`subprocess.Popen([sys.executable,
<hub server.py>, ...], detached, stdio to DEVNULL)`), waits for `/healthz` up to `--start-timeout` (20 s),
then continues; `--no-autostart` disables; `--health` and `--call TOOL JSON` one-shots as the bm shim.

TUI client `tools/mcp/inference-hub/inference_client.py` (stdlib): `InferenceClient(base_url=
"http://127.0.0.1:8901", registry_path=None)` with `models()`, `chat(model, messages, **kw)`,
`chat_many(...)`, `budget_status()`, `health()`, `ensure_running(start_cmd=None)`; reads
`.agents/models.json` and `.agents/routing-policy.json` read-only for `route(task_class)`.

## 5. Fake server `tools/mcp/inference-hub/testing/fake_openai_v1.py`

Stdlib `ThreadingHTTPServer`, importable (`FakeOpenAIServer(profile=..., **faults)` with `.start()`,
`.stop()`, `.base_url`, `.requests` list) and CLI (`--port --profile --<fault flags>`). Profiles: `openai`
(chat JSON + SSE, `usage`, `tool_calls` with string `arguments`, `response_format` json_schema honoured,
`/v1/responses`), `ollama` (rejects `tool_choice` with 400, `usage` only with `stream_options.include_usage`,
404 unpulled model, `/api/tags`, `/api/show` with `capabilities[]`, `/api/version`), `hf-router` (401 without
Bearer, `/v1/models` entries carry `providers[] {provider, supports_tools, supports_structured_output,
pricing}`, `:provider` suffix parsed and echoed), `auth2api` (36 `cursor-*` ids; `/v1/responses` and
`/v1/messages` switchable via `responses=True/False`, `messages=True/False`), `lmstudio` (`/api/v0/models`,
stateful `/v1/responses` with `previous_response_id`). Fault flags: `rate_limit_every=N` (429 +
`Retry-After: 1`), `fail_every=N` (503), `slow_first_token=S`, `hang_after_tokens=N`, `malformed=True`,
`echo_secret=True` (reflects the request's Authorization value into content - the redaction canary),
`drop_tool_calls=True` (flattens tool_calls into content: the bridge-passthrough trigger),
`flatten_refusal=True`, `latency_s=S` (fixed per-request delay, for the no-HOL test). Deterministic reply:
`"echo:" + last user content` unless a `tools` list is present (then one `tool_call` naming the first tool
with `{"nonce": <from prompt or "0">}`).

## 6. Eval harness `tools/endpoint-eval/`

`graders/` (`tool_fidelity.py`, `json_axis.py`, `bridge_passthrough.py`, `latency.py`, `cost.py`,
`passk.py`), `fake_endpoint.py` (fixture replay), `fixtures/`, `score_policy.py`, `contract_suite.py`
(the T1 suite: runs against the fake server and the hub `/v1` face, `pass@1` must be 1.00, prints
`SUCCESS:endpoint-eval-t1 ...`), `capability_suite.py` (T2/T3 definitions: `pass@3 >= 0.90`,
`pass^k n >= 4`; runnable against fakes with `--fake`; live runs are owner-run behind `INFERENCE_LIVE=1`),
`tests/`. CI: second job `endpoint-eval-fakes` in `.github/workflows/routing-benchmark.yml` + a
`gate-tests-coverage` step in `quality.yml` (added by the orchestrator).

## 7. `.agents/routing-policy.json`

Closed schema, names only: `{schemaVersion: 1, classes: {<task_class>: {primary, escalate_to[], floors{},
exponents{quality, speed, cost}, spend_share, pace: {P, A, C, E, triggers[]}, justification, pinned_until?}},
review: {cadence, last_review, owner}}`. Every model/endpoint name must exist in `.agents/models.json`;
PACE rungs must be distinguishable means (at most one `cursor-*` rung, at least one non-network rung,
`E` names `basic-memory :8765` + `agent-mail :8812` handoff); OpenRouter rungs only in CLI/Codex task
classes. Validator `.agents/scripts/routing_policy.py` (`validate_policy`, `route(policy, registry,
task_class) -> ordered rungs`, loud fallback when the file is missing or invalid).
