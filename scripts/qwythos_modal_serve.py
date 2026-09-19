"""Qwythos-9B-Claude-Mythos-5-1M served on Modal via vLLM (@app.server pattern,
mirroring modal-examples/06_gpu_and_ml/llm-serving/vllm_inference.py).

Deploy:  modal deploy qwythos_modal_serve.py
Stop:    modal app stop qwythos-9b-vllm2
Logs:    modal app logs qwythos-9b-vllm2

URL:     printed by deploy, workspace--qwythos-9b-vllm2-server style
Auth:     Authorization: Bearer <key from Modal secret qwythos-vllm-key>
          (the secret sets VLLM_API_KEY in the container env; vLLM enforces
          it on every /v1 endpoint. The key never appears in any file here
          nor in the process command line.)

Costs:   H100 ~$3.95/hr while warm; scales to zero 5 min after last request.
         Cold boot ~2-4 min (weights from persistent Volume).
Context: max_model_len 262144 = native window ("1M" is YaRN extrapolation the
         publisher only smoke-tested to ~137k).
"""

import subprocess

import modal

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("qwythos-9b-vllm2")

# Official-example pattern: CUDA devel base + pip vllm, NOT the vllm docker
# image (its entrypoint/proxy layout wedges Modal's request routing).
image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.28.0")  # first line with transformers>=5.5.3 (TokenizersBackend)
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

hf_cache_vol = modal.Volume.from_name("qwythos-model-cache", create_if_missing=True)


@app.server(
    image=image,
    gpu="H100",
    scaledown_window=5 * MINUTES,
    startup_timeout=15 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache_vol},
    port=VLLM_PORT,
    secrets=[modal.Secret.from_name("qwythos-vllm-key")],  # sets VLLM_API_KEY
    unauthenticated=True,  # open at Modal's proxy; vLLM enforces the Bearer key
)
class Server:
    @modal.enter()
    def start(self):
        # all-literal argv; the API key reaches vLLM via the VLLM_API_KEY
        # environment variable set by the Modal secret, not via this command
        self.process = subprocess.Popen(
            [
                "vllm",
                "serve",
                "empero-ai/Qwythos-9B-Claude-Mythos-5-1M",
                "--served-model-name",
                "qwythos-9b",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--max-model-len",
                "262144",
                "--gpu-memory-utilization",
                "0.92",
                "--enable-auto-tool-choice",
                "--tool-call-parser",
                "qwen3_xml",
                "--reasoning-parser",
                "qwen3",
            ]
        )

    @modal.exit()
    def stop(self):
        self.process.terminate()
