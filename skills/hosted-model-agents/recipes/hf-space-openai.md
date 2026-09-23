# Recipe: Hugging Face Space with OpenAI `/v1` (tool proposer)

**Default path since 2026-09-02 is the HF router + `inference-hub`** (`models_list`, then `chat model="glm-5.3"`; see [../environments.md](../environments.md)); this Space recipe is the fallback for a private checkpoint the router does not serve.

**Example only.** Checkpoint today: private Space `Prekzursil/qwen38-27b-heretic-chat` (Qwen3.8-27B Heretic-ARA, ZeroGPU). The same recipe applies to any chat model you mount the same way.

- Code: `C:\Users\Prekzursil\Cowork\tools\hf-space-qwen38-27b-heretic`
- Wire contract: OpenAI `/v1/chat/completions` as below; the old `qwen-space-tool-api/reference.md` is not on this branch (that skill and the `qwen-space` wrapper are tombstones box-side only)
- Wrapper: none in the repo. To use the Space, add it as an endpoint row in `.agents/models.json` (`kind: hosted`, auth by NAME) and call it through `inference-hub`; HTTP only, no tool execution on the Space
- Hub control plane for this Space (create, files, status): **`huggingface` MCP / plugin**, not this `/v1`

## What this recipe is

Gradio app + GPU-free FastAPI `/v1/models`, `/v1/chat/completions`, `/healthz`. Model returns OpenAI `tool_calls`. Local harness executes.

## What this recipe is not

- Not the Hugging Face Hub MCP.
- Not “the Qwen agent skill.”
- Not an `agents.json` MCP server.

## Checkpoint-specific traps (this Space)

- `reasoning_effort: high` → alias to `xhigh` (stock Qwen3.8 template).
- Replay `tool_calls.arguments` as **dicts** for Jinja `|items`.
- ZeroGPU: only `generate` under `@spaces.GPU`.
- Auth: Bearer `HF_TOKEN`; Space is private.

Tests (GPU-free): `python -m unittest discover -s tests -t . -v` in that repo. Coverage: **NOT-CHECKED** (no `.coverage-thresholds.json`).
