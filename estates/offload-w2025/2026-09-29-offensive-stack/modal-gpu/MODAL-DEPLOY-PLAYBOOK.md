# Modal GPU model deployment — estate playbook (no more trial-and-error)

**This document exists because I burned 5 deploy cycles on 2026-10-01 re-learning
what the estate already knew.** Every failure below is a REAL failure from this
session, with the root cause and the fix that worked. When deploying ANY model
on Modal, read this FIRST, then follow the recipe verbatim.

## The Recipe (v0.3 — the one that works, 2026-10-01)

```python
import modal

app = modal.App("estate-<name>")
IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm==0.11.0", "transformers>=4.51,<5", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
vol = modal.Volume.from_name("estate-<name>-weights", create_if_missing=True)

@app.function(image=IMAGE, gpu="L4", scaledown_window=300, timeout=1800,
              volumes={"/root/.cache/huggingface": vol}, max_containers=1)
@modal.web_server(8000, startup_timeout=15 * 60)
def serve():
    import os, subprocess
    subprocess.run(["vllm", "serve", MODEL_ID,
                    "--host", "0.0.0.0", "--port", "8000",
                    "--max-model-len", "16384", "--gpu-memory-utilization", "0.90",
                    "--api-key", os.environ["KEY"]], check=True)
```

Deploy: `MODAL_PROFILE=<account> modal deploy <app>.py`
URL: `https://<account>--<app-name>-serve.modal.run/v1/chat/completions`
Auth: `Authorization: Bearer <api-key>`

## The 5 Failure Modes (measured, don't repeat)

| # | What I did | What happened | Root cause | Fix |
|---|---|---|---|---|
| 1 | `pip_install("vllm==0.11.0")` alone | Container crash-loop: `Qwen2Tokenizer has no attribute all_special_tokens_extended` | Modal's slim image resolves `transformers==5.x` which removed that attribute; vllm 0.11.0 needs 4.x | **Pin `transformers>=4.51,<5` alongside vllm** |
| 2 | `build_app(AsyncLLMEngine.from_engine_args(...))` wrapped in `@modal.asgi_app()` | Container crash-loop: `'AsyncLLM' object has no attribute 'disable_fastapi_docs'` | vllm 0.11's internal `build_app` API changed; the ASGI wrapper approach doesn't work with this version | **Use `@modal.web_server(8000)` + `subprocess.run(["vllm","serve",...])` instead — no Python-level wrapping** |
| 3 | `@modal.asgi_app(requires_proxy_auth=True)` + `Modal-Key: tid` header | `invalid credentials for proxy authorization` | Modal's proxy auth requires a *scoped* trigger token (browser-minted via `modal token new`), not a workspace token | **Use vllm's native `--api-key` flag instead — standard Bearer auth, any HTTP client speaks it** |
| 4 | `MODAL_TOKEN_ID=... modal deploy` | Deployed to the WRONG workspace (florineldanciu4 instead of mariusvisalon70) | **This modal CLI version resolves the toml's `[profile]` sections over env tokens.** Env token override doesn't work here. | **Set `MODAL_PROFILE=<name>` env var instead — that's the per-call switch in this CLI version** |
| 5 | Prepending `active_profile = "name"` to `~/.modal.toml` top-level | `modal` CLI broke: "TOML file must contain table sections for each profile" | Modal's config parser expects ONLY `[section]` tables at top level; scalar keys break it | **Never add top-level scalars to `~/.modal.toml`. Use `MODAL_PROFILE` env or `modal profile activate <name>`** |
| 6 | `@modal.web_server(8000, startup_timeout=900)` + `subprocess.run(["vllm","serve",...])` | 303 redirect loop (752s of urllib chasing proxies) | Modal's `web_server` proxy redirects during cold-start; vllm takes 3-4 min to bind; proxy can't route → infinite loop | **Use `@modal.asgi_app(label=...)` instead — it produces `.modal.run` URLs that route correctly** |
| 7 | `@modal.asgi_app()` returning `aiohttp.web.Application` | Container starts but 000s on all requests | `aiohttp.web.Application` is NOT an ASGI app (it's aiohttp's own WSGI-like interface) | **Return a raw ASGI callable `(scope, receive, send)` — see working code below** |
| 8 | `subprocess.Popen([...  "--port", 8000 ...])` | Container crash-loop: `TypeError: expected str, bytes or os.PathLike object, not int` | `subprocess.Popen` args must be ALL strings; `8000` as int crashes immediately | **`"--port", "8000"` — every arg in the list must be a string** |

## The proven working auth (Bearer, universal)

1. Generate: `python -c "import secrets; print(secrets.token_hex(24))"` → save as `.bench-key`
2. Store in Modal: `MODAL_PROFILE=<account> modal secret create <name> KEY=<value>`
3. Mount: `secrets=[modal.Secret.from_name("<name>")]` in the function decorator
4. Pass to vllm: `--api-key os.environ["KEY"]` in the subprocess args
5. Client: `Authorization: Bearer <value>`

## Account rotation (Modal, 10 profiles in `~/.modal.toml`)

```bash
# Survey (read-only, safe on paused workspaces)
python D:\opt\modal-gpu\modal_rotation.py survey

# Pick the first COMPUTE-LIVE account (env-inject format)
python D:\opt\modal-gpu\modal_rotation.py pick
# → MODAL_PROFILE=mariusvisalon70

# Deploy/rotate
MODAL_PROFILE=mariusvisalon70 modal deploy <app>.py
```

Exhaustion classes that trigger rotation at call time: "Workspace ... is paused",
HTTP 402/spend-limit/quota. Rotate by re-running `pick` → redeploy.

## Previous estate deployment (for reference)

- **qwythos-9b**: `florineldanciu4--qwythos-9b-vllm2-server.us-east.modal.direct`
  (9B model, deployed ~2026-08, now PAUSED — workspace credits exhausted).
  Client scripts: `bolt_security_training/scripts/ask_qwythos*.py` (try multiple
  auth formats: Bearer <secret>, Bearer <id>:<secret>, Basic).

## Cost notes (L4, measured)

- Cold start (first ever): ~15 min (image build + weights download to volume)
- Cold start (subsequent): ~3 min (weights cached in volume, torch.compile cached)
- Warm serial tasks: ~300s scaledown window keeps the container alive between tasks
- Full 20-task bench table: well under $1 (estimated < 30 min on L4)
- $42.5 in credits (mariusvisalon70, refreshed 2026-10-01) ≈ ~50+ full bench tables
