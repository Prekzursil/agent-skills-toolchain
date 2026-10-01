"""Modal GPU bench tier — deployed vLLM OpenAI-compatible server for qwen3:4b.

Estate instrument I1/I2 executor (grill 2026-10-01: Q1=staged-both, Q2=estate-
standard creds). Deploy once:  modal deploy bench_modal_app.py
The printed URL (…modal.direct/v1) goes into providers/modal-qwen3-4b.json.

Credential-ready: deploy/invoke requires MODAL_TOKEN_ID + MODAL_TOKEN_SECRET
(user env, per estate SSOT). Values live in home's git-crypt store
(advver-m14-chk tools/mcp/cloud-hub/accounts.json) pending home wake; the
fallback env names MODAL_TOKEN_ID_474a0e / MODAL_TOKEN_SECRET_3d3c42 follow
the estate's existing account naming (bolt_security_training scripts pattern).
"""
import modal

app = modal.App("estate-bench-qwen3-4b")

IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm==0.11.0", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"

# ~5GB weights cached in a Modal Volume so cold starts after the first are
# container-boot only (~40-70s on L4), not a weights download.
vol = modal.Volume.from_name("estate-bench-weights", create_if_missing=True)


@app.function(
    image=IMAGE,
    gpu="L4",
    scaledown_window=300,
    timeout=1800,
    volumes={"/root/.cache/huggingface": vol},
    max_containers=1,
)
@modal.asgi_app()
def bench_server():
    from vllm.entrypoints.openai.api_server import build_app
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine

    engine = AsyncLLmEngine = AsyncLLMEngine.from_engine_args(
        AsyncEngineArgs(
            model=MODEL_ID,
            dtype="auto",
            max_model_len=16384,
            gpu_memory_utilization=0.90,
            enforce_eager=False,
        )
    )
    return build_app(engine)
