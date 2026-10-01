"""Modal GPU bench tier — vLLM OpenAI-compatible server for qwen3:4b (estate).

v0.5: raw ASGI reverse proxy to vllm subprocess (proper ASGI callable).
Previous failures:
- v0.1/0.2: build_app API incompatible with vllm 0.11
- v0.3: web_server 303 redirect loops (proxy can't route to container)
- v0.4: aiohttp.web.Application is NOT ASGI (returns WSGI-style app from asgi_app)

Deploy:  MODAL_PROFILE=mariusvisalon70 modal deploy bench_modal_app.py
Auth:    vLLM native --api-key (Bearer) from Modal Secret 'estate-bench-key'
"""
import modal

app = modal.App("estate-bench-qwen3-4b")

IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm==0.11.0", "transformers>=4.51,<5", "huggingface_hub[hf_transfer]", "aiohttp")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
vol = modal.Volume.from_name("estate-bench-weights", create_if_missing=True)
BENCH_SECRET = modal.Secret.from_name("estate-bench-key")


@app.function(
    image=IMAGE,
    gpu="L4",
    scaledown_window=600,
    timeout=1800,
    volumes={"/root/.cache/huggingface": vol},
    max_containers=1,
    secrets=[BENCH_SECRET],
)
@modal.asgi_app(label="serve")
def api():
    import asyncio
    import os
    import subprocess

    # Start vllm serve as a subprocess (one per container lifetime)
    _proc = subprocess.Popen(
        [
            "vllm", "serve", MODEL_ID,
            "--host", "127.0.0.1", "--port", "8000",
            "--max-model-len", "16384",
            "--gpu-memory-utilization", "0.90",
            "--api-key", os.environ.get("ESTATE_BENCH_KEY", "estate-no-key"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    UPSTREAM = "http://127.0.0.1:8000"
    import aiohttp

    async def _wait_ready(session):
        """Poll vllm /health until it responds."""
        for _ in range(900):
            try:
                async with session.get(UPSTREAM + "/health",
                                       timeout=aiohttp.ClientTimeout(total=2)):
                    return True
            except Exception:
                await asyncio.sleep(1)
        return False

    async def asgi_app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            return

        if scope["type"] != "http":
            return

        # Read the full request body
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
            elif message["type"] == "http.disconnect":
                return

        # Forward to vllm
        method = scope["method"].encode().decode()
        path = scope["path"]
        query = scope.get("query_string", b"").decode()
        url = UPSTREAM + path + ("?" + query if query else "")

        # Forward headers (skip host/content-length)
        headers = {}
        for k, v in scope.get("headers", []):
            key = k.decode().lower()
            if key not in ("host", "content-length", "transfer-encoding"):
                headers[key] = v.decode()

        async with aiohttp.ClientSession() as session:
            # Ensure vllm is ready before forwarding
            await _wait_ready(session)

            try:
                async with session.request(
                    method, url, data=body if body else None,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=600),
                ) as resp:
                    resp_body = await resp.read()
                    resp_headers = []
                    for k, v in resp.headers.items():
                        if k.lower() not in ("content-length", "transfer-encoding", "content-encoding"):
                            resp_headers.append((k.encode(), v.encode()))

                    await send({
                        "type": "http.response.start",
                        "status": resp.status,
                        "headers": resp_headers,
                    })
                    await send({
                        "type": "http.response.body",
                        "body": resp_body,
                    })
            except aiohttp.ClientError as exc:
                err = f"upstream error: {exc}".encode()
                await send({
                    "type": "http.response.start",
                    "status": 502,
                    "headers": [(b"content-type", b"text/plain")],
                })
                await send({"type": "http.response.body", "body": err})

    return asgi_app
