# Provenance for `.agents/models.json` (hosted + local model endpoint registry)

The manifest is a closed schema (root `AGENTS.md`: never add a manifest key merely to carry
provenance); the *why* of every row lives here. Validated by
`.agents/scripts/models_control_plane.py` (rules V1-V20, red-proof tests in
`.agents/tests/test_models_control_plane.py`); `.agents/scripts/validate_models_control_plane.py`
must print `SUCCESS:models-registry ...` before any edit is committed. Interfaces the file feeds:
`docs/gem-hunt/2026-09-02-hosted-models/BUILD-CONTRACT.md`. Decisions cited by id:
`docs/gem-hunt/2026-09-02-hosted-models/DECISION-QUEUE.md`.

## Why a sibling file (D2 = A)

A models registry beside `agents.json` (MCP servers) keeps the MCP validator's blast radius and
`lastSyncSourceHash` untouched, while cloning its idioms: credentials by environment-variable NAME
only (V1/V2), closed `x_*` blocks (V9), `locks[]` declared once and referenced by id (V16), a
capability lattice `native > probed{at,version} > declared > emulated > absent` where a model row may
only override an endpoint value downward (V5), `resource.ramBytes` on every local row with a budget
warning (V10), a health probe spec per endpoint. Six lenses converged on this field set (C2).

## Endpoints

- **`hf-router`** (`router.huggingface.co/v1`): the cheapest Hugging Face runtime and the successor
  path for GLM-5.3 (D1). Declares only the inference-scoped token NAME `HUGGINGFACE_TOKEN_INFERENCE`
  (D7: a fine-grained "Make calls to Inference Providers" token, ADDED, never rotated - L6; the Hub
  MCP keeps `HUGGINGFACE_TOKEN`). `issuerHosts` bind that name to `*.huggingface.co` (V19): a profile
  that would send it to a stranger's Space fails validation. `wire.responses` stays `declared` (beta)
  until the D9 probe writes `probed{at,version}`; `features.*` are `declared` until observed (C12).
  Excluded for Cursor/Claude/Agy/Gemini: those runtimes reach it through `inference-hub` (D3).
- **`openrouter`** (`openrouter.ai/api/v1`): the spend-capped CLI/Codex sidecar and nothing else (L1):
  `sidecarOnly: true` (V14), `denyCallers` carries `cursor` + `claude` (V15), `targets.cursor` /
  `targets.claude` are `excluded` (V7). Key NAMES only (D8): `OPENROUTER_API_KEY_CODEX_SIDECAR`
  (`or-codex-sidecar`), `OPENROUTER_API_KEY_CLI_GRUNT` (`or-cli-grunt`), optional
  `OPENROUTER_API_KEY_IDE_OPENCODE` (`or-ide-opencode`), each with a daily `limitReset`; the one
  Guardrail (provider + model allowlist, `dataCollection: deny`, Secrets preset, owner-set
  `limitUsd`) is recorded in `x_openrouter` as a spec the owner applies (`OWNER-CLICKS.md`).
- **`cursor-auth2api`** (`127.0.0.1:8317/v1`): the only Cursor bridge (L3): `singletonKey:
  cursor-bridge` (V6) and `retiresWhen` naming the 7-day clause after an official Cursor `/v1` GA
  (V13). All three wires are `declared` on purpose (D9): renderers floor on `probed`, so no Codex
  block and no `*-cursor` wrapper renders before the M0 probe receipt lands; the routing report marks
  a wrapper `unprobed` now and `broken` if the wire fails. `denyCallers: ["cursor"]` - Cursor never
  calls its own quota through the hub. Port 8317 is allowed for this id only (V8, L4).
- **`ollama`** (`127.0.0.1:11434/v1`): the local primary (D10). The box HAS an NVIDIA GeForce RTX
  4050 Laptop GPU (6 GB VRAM), so the Tier S/M weights fit GPU-full - the earlier "no GPU" premise was
  wrong (V17). Residency discipline is user env, recorded in `x_ollama` for the renderers and the
  owner: `OLLAMA_KEEP_ALIVE=2m`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`,
  `OLLAMA_CONTEXT_LENGTH=65536` (bumped from 8192 on 2026-09-03, grill Q2: bench receipts show 64K
  held under full desktop load - 21 GB mapped, stable, 8-12 tok/s; see OWNER-CLICKS.md D10-1),
  `OLLAMA_KV_CACHE_TYPE=q8_0`, loopback bind, version >= 0.17.1.
  `features.tool_choice` is `absent` (Ollama rejects it); `/api/show` capabilities are the discovery
  source. `resource.ramBytes` is the idle server footprint; models carry their own working sets.
- **`lmstudio`** (`127.0.0.1:1234/v1`): run as the `llmster` daemon, not the GUI server (T0-13), JIT
  loading + auto-evict ON, idle TTL 600 s (the app default of 60 min was the largest idle-RAM hazard
  found, C13); `x_lmstudio` records it. Never `lms load` without `--ttl`.
- **`llamacpp`** (`127.0.0.1:8080/v1`, `enabled: false`): llama-server with `--sleep-idle-seconds` and
  router mode - the cleanest primitives but one more resident thing (D10 option C, recorded, not
  chosen). Enable only through the eval gate.
- **`hf-router-featherless`** (`router.huggingface.co/featherless-ai/v1`, added 2026-09-03): the same
  HF router account pinned to the featherless-ai provider path that serves the abliterated/WRN offsec
  checkpoints; a separate row (not models under `hf-router`) because consult-offsec and the ZCode v2
  provider stanza address the pinned route by URL, and a separate row lets its budget be stated
  (grill Q3). `budget.dailyUsdCap: 1.0` and the matching cut of `hf-router` to 1.0 make the family sum
  2.0 USD/day; the cap is SHARED account billing and the registry cannot enforce a cross-endpoint sum —
  the consult-offsec server's v1.2 dollar meter (`CONSULT_USD_CEILING`, default 1.0 — its lane share;
  raise to 2.0 only if you accept starving the plain `hf-router` lane) is the enforcement,
  the registry documents. `auth.altEnv` adds `HF_TOKEN` (the consult-offsec env passthrough) beside the
  inference-scoped primary. All wire/features `declared` (nothing probed; grill Q4 — rows enter
  unprobed/declared and probe receipts flip them to live/probed during PR review). Sources:
  pr-lane-plan.md 3.4(a), grill decision log Q3/Q4 (2026-09-03 wave).

## Models

- **`glm-5.3`** (`hf-router`, `zai-org/GLM-5.3:zai-org`): the D1 capability receipt. The
  `glm53-space` MCP lane was hard-deleted; the same model on the same router is reachable through
  `inference-hub` `chat` (L7: nothing the owner could do before is lost). Test
  `test_glm53_capability_preserved` pins this row.
- **`glm-5.2-free`** (`openrouter`, `z-ai/glm-5.2:free`): the OpenRouter T0 smoke slug; inherits the
  sidecar `denyCallers`.
- **`cursor-grok-4.6`** (`cursor-auth2api`): one of the 36 `cursor-*` ids auth2api exposes; `status:
  unprobed` until D9; quota-billed so `cost.*` is `null`, never 0 (C20).
- **`qwen2.5-7b`** (`ollama`, `qwen2.5:7b`): already on disk and proven (local-models audit
  2026-08-27); the Tier M reference until the Qwen3 picks pass the T2 lane; `slots.small/subagent/
  summary` and alias `local-default`.
- **`qwen3-4b-instruct`** (`ollama`, Tier S, ~4.3 GB at 8k ctx, thinking off on tool turns) and
  **`qwen3-8b`** (`ollama`, Tier M, ~7 GB, thinking off): D10 picks, `status: eval-gated` - promoted to
  `live` only after T2 `pass@3 >= 0.90` (PU10). `quirks.openai.thinking_off_for_tools` drives the
  hub's `think: false` adapter.
- **`huihui-cyberstrike-35b` / `wrn-2.5-coder-7b` / `huihui-qwen3.8-27b-abliterated`**
  (`hf-router-featherless`, added 2026-09-03): the three abliterated/WRN checkpoints from the ZCode v2
  "HF Featherless" provider stanza, registered at the stanza's 32K caps. `huihui-cyberstrike-35b` is
  the consult-offsec default cloud model (alias `offsec-cloud`); abliterated rows pair ONLY with the
  authorized-scope reporter persona (profiles.md). All `status: unprobed`, no probe receipts yet
  (grill Q4: receipts land as review-time amendments; a DevFleet probe mission is spec'd in the PR).
- **`qwen3.6-35b-a3b` / `hermes-3-70b`** (`hf-router`, added 2026-09-03): the two models of the ZCode
  v2 "HuggingFaces" stanza. NO new endpoint: its baseURL `https://router.huggingface.co/v1` is
  byte-identical to `hf-router`, and a second endpoint with the same URL would duplicate auth/billing
  rows (pr-lane-plan 3.4(b)). `unprobed` per grill Q4.
- **`wrn-coder-7b` / `qwythos-9b`** (`ollama`, added 2026-09-03, `enabled: true`) and
  **`huihui-offsec` / `gptoss-20b-abliterated`** (`ollama`, added 2026-09-03, `enabled: false`): the
  four ZCode v2 "Ollama Local" models at 64K context. The two large rows are registered disabled: at
  ~22 GB / ~13.5 GB (Q4 parameter-count ESTIMATES — owner-verify with `ollama show`) they would trip
  the non-fatal 8 GiB `localRamBudgetBytes` warning, and the seed test
  `test_seed_validates_with_zero_warnings` requires a warning-clean registry (pr-lane-plan 5.5's
  "quiet registry" option); flip `enabled` after RAM planning. `wrn-coder-7b` is the consult-offsec
  default local model (alias `offsec-local`). Estate context: `OLLAMA_CONTEXT_LENGTH` bumped
  8192 → 65536 (grill Q2 — bench receipts 2026-09-03: 64K held under full desktop load, 21 GB mapped,
  stable, 8-12 tok/s); recorded in the `ollama` endpoint description, `x_ollama.contextLength`, and
  OWNER-CLICKS.md. The three pre-existing ollama rows stay at their registered 8192 contexts — their
  remoteIds were registered under the old pin and per-model re-registration is a separate decision.

## Aliases and slots

`glm53 -> glm-5.3` keeps the old name resolvable for muscle memory; `fabric-default -> glm-5.3` is the
one endpoint the Fabric renderer exports as `OPENAI_API_BASE_URL`; `local-default -> qwen2.5-7b`.
Added 2026-09-03 (consult-offsec wave): `offsec-cloud -> huihui-cyberstrike-35b` and
`offsec-local -> wrn-coder-7b` name the consult-offsec default routes so drivers can ask for the role
instead of the checkpoint. `slots{}` untouched — slot assignment stays an owner routing decision.
Slots (`large`, `small`, `subagent`, `web_search`, `summary`, `embed`) mirror the models.dev /
OpenCode slot names so a consumer can ask for a role instead of an id; `web_search` and `embed` are
`null` until a row earns them. An alias to a disabled or missing model is a validator error (V12).

## Rules that this file keeps, and where they are tested

- Names only, never values (L6): V1 literal-secret scan of the whole file, V2 env-name regex; the
  `gate-secrets` gitleaks job over the committed tree.
- Owned ports (L4): V8 refuses 8765 / 8812 / 8770 for any endpoint, 8317 for any id but
  `cursor-auth2api`, and 8901 (the hub's own port) for any endpoint.
- Truthful capabilities (C12): lattice values validated (V11 `probed` needs `at` + `version`),
  downward-only model overrides (V5); renderers select by floor (`RUNTIME_FLOORS`), the hub reports
  `structured_mode` and a `capability_report` on every call.
- Local RAM (D10): V10 warns when the resident local endpoints plus the largest enabled local model
  exceed `policy.localRamBudgetBytes` (8 GiB), matching `OLLAMA_MAX_LOADED_MODELS=1`.
- Edits: only through the validator; `models_probe.py` writes `probed{at,version}` via
  `atomic_write_text`; `catalog_sync.py` and the score sidecar never write this file (asserted by their
  tests).
