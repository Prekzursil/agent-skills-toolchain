# Hosted-models BUILD WAVE - STATUS (PR #314, branch `gemhunt/hosted-models-00-consolidated`)

Orchestrated build wave, 2026-09-02, cloud worker (Linux, Python 3.12, no `pwsh`, no `uv`, no live
loopback ports, no secrets). Method: one orchestrator, parallel builder subagents on disjoint file sets,
one fresh adversarial reviewer per work unit, TDD (failing tests first), checkpoint-first pushes.
Companion files: `BUILD-CONTRACT.md` (interfaces), `OWNER-CLICKS.md` (box-only steps),
`DECISION-QUEUE.md` / `BUILD-WAVE-PROPOSAL.md` (the plan this wave executed).

## 0. Owner decisions as recorded (override the queue's recommendations where they differ)

| id | answer | what it meant for the wave |
|---|---|---|
| D1 | **B - HARD DELETE** | `tools/mcp/glm53-space` (never in the repo; box-only) and its `agents.json` row are gone in this PR; `inference-hub` registered first and took the Cursor safe-default adapter slot; `archive/glm53-space-2026-09` pushed as git safety (owner adds the box copy); capability preserved as model `glm-5.3` (`hf-router`, `zai-org/GLM-5.3:zai-org`); every test that pinned glm53-space (repo suite + live-lineage suite) re-pinned to the successor |
| D2 | **A** | sibling `.agents/models.json` + `.agents/scripts/models_control_plane.py` cloned from the MCP validator idioms: env-NAME credentials only, closed `x_*`, `locks[]`, capability lattice `native/probed/declared/emulated/absent`, per-endpoint `api[]`, `resource.ramBytes`, health probe spec |
| D3 + D6 | **resident concurrent HUB** | `tools/mcp/inference-hub` on `127.0.0.1:8901`: MCP Streamable-HTTP face (`models_list`, `chat`, `chat_many`, `probe`, `budget_status`) + OpenAI `/v1` face; async core, per-endpoint concurrency limits, no head-of-line blocking; lazy start by a stdio shim + idle-exit (default 10 min); one resident process max; no other new ports; secrets by env NAME; truthful degradation; per-call cost ledger; redaction |
| D4 | **ALL runtimes** | Goose -> Grok -> OpenCode -> Aider(+wrappers) -> Fabric -> Codex LAST; dry-run + routing report default, `--write` per runtime, idempotent merges; MCP-only runtimes (Claude Code, Cursor, Agy, Gemini CLI) reach models through the hub MCP; client contract for the future TUI (schemas, `/v1`, `inference_client.py`) |
| D5 | **A** | eval gate: probe receipt (owner) + archive branch pushed + contract suite on a stdlib fake at pass@1 = 1.00 as a second job of `routing-benchmark.yml` + validator red-proof tests; pass@3 >= 0.90 and pass^k n >= 4 defined and runnable against fakes in CI; live-key runs documented as owner-run |
| D7 | **A** | `HUGGINGFACE_TOKEN_INFERENCE` as a NAME only; the hub declares only that name; Hub MCP keeps `HUGGINGFACE_TOKEN` |
| D8 | **A** | 2-3 labelled OpenRouter key NAMES (`OPENROUTER_API_KEY_CODEX_SIDECAR`, `OPENROUTER_API_KEY_CLI_GRUNT`, optional `OPENROUTER_API_KEY_IDE_OPENCODE`) + Guardrail spec, names only |
| D9 | **A** | probe `:8317` `/v1/responses` and `/v1/messages`; wrappers marked `broken` in the routing report if the wire fails; no Codex block for `:8317` until the probe passes (renderers floor on `probed`) |
| D10 | **A** | Ollama primary rows with KEEP_ALIVE / MAX_LOADED_MODELS / NUM_PARALLEL guidance, Tier S Qwen3-4B / Tier M Qwen3-8B thinking-off, LM Studio via `llmster` daemon JIT + auto-evict + idle TTL, `resource.ramBytes` on every local row; "no GPU" premise corrected everywhere (RTX 4050 6 GB) |
| D11 | **A** | `.agents/routing-policy.json`, names only, closed schema, `pace` block per task class, wrappers read it with a loud fallback |
| D12 | **A** | daily `catalog_sync.py` Scheduled Task spec (`register-tasks.ps1` style, mutex + IgnoreNew), probe ladder L0-L5 as `--mode all` of `hooks/mcp-liveness`, capability score sidecar, retire = human write-back |
| D13 | **A + B** | doc note in CLAUDE.md / AGENTS.md / multi-ai-mingle that `codex mcp-server` is deprecated upstream 2026-08-24, mount kept, AND the codex-plugin-cc slash-command path documented and registered alongside |

## 1. Work-unit ledger

(filled in by the orchestrator as each unit lands; SHAs are on this branch)

| WU | status | files | tests | eval | reviewer verdict | commits |
|---|---|---|---|---|---|---|
| WU-0 preflight: PR green | SUCCESS | `docs/.../08-eval-harness-and-autoresearch.md` (published-command marker); merge of `origin/main` (gitleaks HEAD-scoped fix #313 + PR #308) | gate scripts run locally as CI does | - | n/a | `3830dd9d7`, `e6b3d0152` |

## 2. Deferred / not done (with reasons)

(filled in at the end)
