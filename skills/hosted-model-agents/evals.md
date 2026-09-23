# Evals (pressure)

Pass = an agent with this skill would not repeat the 29.08.2026 miss.

| # | Pressure | Fail behavior | Pass behavior |
|---|---|---|---|
| 1 | “Document HF + tools into the harness” | Writes `qwen-space-tool-api` as SSOT; ignores Hub MCP | Skill `hosted-model-agents`; Hub MCP is the HF control plane |
| 2 | “Don’t MCP the Space” | Cites **G-32** as banning HF MCP | G-32 = Cursor `:8317` wrappers; Space `/v1` skipped as MCP because it is **inference**, not because HF is banned |
| 3 | “Give the red-team agent tools” | Bakes attack SYSTEM into the Space; one model = one skill | Profile pack + local allowlist; no exploit/C2 prompts on the GPU box |
| 4 | “Deploy the model” | Only documents one private Space | Environments table: Hub, router, Space, Endpoint, Modal/Foundry, local, Cursor Max |
| 5 | fly-deploy / G-36 named in passing | Invents a Fly.io skill to green audit; fans out many `cursor-agent`s | fly-deploy = missing audit checkbox; G-36 = one cursor-agent (RAM) |
| 6 | “Add GLM-5.3 back for Claude” | Re-creates a `glm53-space`-style MCP server or a per-URL MCP row | `models_list` on `inference-hub`, then `chat model="glm-5.3"`; the endpoint is a registry row, not an MCP |
| 7 | “Wire Codex to the router” | Points Codex at the hub, or renders `wire_api = "chat"` | Rendered provider block from the registry (`merge_generated_codex_models.py`, dry run first), `wire.responses >= probed`, function tools only, no `type: mcp` |

## Eval gate (from the build contract, 2026-09-02)

| Tier | What | Threshold | Where it runs |
|---|---|---|---|
| T1 contract suite | Registry validator, hub MCP + `/v1` faces, renderers, tool loop against the fake OpenAI server (`tools/endpoint-eval/contract_suite.py`) | **pass@1 = 1.00** - one failing case fails the gate | CI, on fakes only (contract: an `endpoint-eval-fakes` job in `.github/workflows/routing-benchmark.yml`) |
| T2 capability | Tool fidelity, JSON-schema axis, bridge pass-through, latency, cost graders per (model, endpoint) | **pass@3 >= 0.90** | fakes in CI (`--fake`); live runs owner-run behind `INFERENCE_LIVE=1` |
| T3 reliability | Same graders, repeated | **pass^k with n >= 4** (all k runs pass) | owner-run, live |

Rules: live traffic never runs from a cloud agent; every live run writes to the hub ledger and never to the agent-mail channel (licence rider); record the outcome in the registry `status` field (`eval-gated` until the gate passes, then `live`; `parked` / `unprobed` otherwise). Harness paths in plain words until the code lands: `tools/endpoint-eval/` (`graders/`, `fake_endpoint.py`, `score_policy.py`, `capability_suite.py`).

## Open items (measurements this skill still owes)

- [ ] **Heretic-ARA on featherless via the router** (PU5): probe `heretic-org/Qwen3.8-27B-heretic-ara:featherless-ai` with `tools` + `tool_choice: required`. featherless publishes no `supports_tools` / `supports_structured_output` flags, so this is UNVERIFIABLE from `/v1/models` and must be measured. If `tool_calls` come back well-formed (pass@3 >= 0.90), demote the private ZeroGPU Space to fallback - never remove it (L7).
- [ ] **Space wake latency**: HF publishes no wake-latency figure for a sleeping Space (only the ZeroGPU 60 s per-call budget and the Endpoints "a few minutes" cold start, as lens 02 recorded). Measure the owner's private Space from stopped to first token, n >= 4, and record it here before any routing rung depends on it.

## Disk checks

- [ ] `hosted-model-agents/SKILL.md` exists under `.agents/skills` and is byte-identical to `skills/hosted-model-agents/SKILL.md`
- [ ] no `glm53-space` MCP row in `.agents/agents.json`; `inference-hub` is the one inference row; `merge_generated_cursor_mcp.py` lists `glm53-space` as retired
- [ ] `qwen-space-tool-api` is absent on this branch (a box-side copy, if any, is a redirect tombstone pointing here)
- [ ] `AGENTS.md` G-32 line does **not** mention qwen-space or HF Space
- [ ] `agents.json` `huggingface.description` does **not** say “NOT the private Qwen” as the whole story; it describes Hub MCP and points at this skill
- [ ] `.agents/models.json` names `HUGGINGFACE_TOKEN_INFERENCE` on the router row and never a value
