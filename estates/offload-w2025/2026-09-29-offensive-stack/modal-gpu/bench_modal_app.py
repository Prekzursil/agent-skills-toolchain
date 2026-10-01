"""Modal GPU bench tier — vLLM OpenAI-compatible server for qwen3:4b (estate).

Instrument I1/I2 executor (grill 2026-10-01: Q1=staged-both, Q2=estate creds).
Deploy:  MODAL_PROFILE=mariusvisalon70 modal deploy bench_modal_app.py
Auth:    vLLM native --api-key (Bearer) from Modal Secret 'estate-bench-key'
         (env ESTATE_BENCH_KEY; user env MODAL_BENCH_KEY mirrors it).
Account: mariusvisalon70 (COMPUTE-LIVE, $42.5 refreshed 2026-10-01); rotate via
         modal_rotation.py pick / MODAL_PROFILE=<name>.
v0.3 2026-10-01: web_server + vllm serve (v0.1/v0.2's build_app path died on
vllm-0.11 API drift: transformers-5 tokenizer attrs, AsyncLLM.disable_fastapi_docs).
"""
import modal

app = modal.App("estate-bench-qwen3-4b")

IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm==0.11.0", "transformers>=4.51,<5", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
vol = modal.Volume.from_name("estate-bench-weights", create_if_missing=True)
BENCH_SECRET = modal.Secret.from_name("estate-bench-key")


@app.function(
    image=IMAGE,
    gpu="L4",
    scaledown_window=300,
    timeout=1800,
    volumes={"/root/.cache/huggingface": vol},
    max_containers=1,
    secrets=[BENCH_SECRET],
)
@modal.web_server(8000, startup_timeout=15 * 60)
def serve():
    import os
    import subprocess

    subprocess.run(
        [
            "vllm", "serve", MODEL_ID,
            "--host", "0.0.0.0", "--port", "8000",
            "--max-model-len", "16384",
            "--gpu-memory-utilization", "0.90",
            "--api-key", os.environ["ESTATE_BENCH_KEY"],
        ],
        check=True,
    )
