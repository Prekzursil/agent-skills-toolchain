#!/usr/bin/env python3
"""T0 OpenRouter chat completion. Prints generation id + usage. Never logs the secret."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
APP_TITLE = "agents-openrouter-sidecar"
APP_REFERER = "https://local.agents.openrouter"


def redact(text: str, secret: str) -> str:
    if not secret or not text:
        return text
    return text.replace(secret, "[REDACTED]")


def request(
    method: str, url: str, secret: str, body: dict | None = None, timeout: int = 90
) -> tuple[int, object]:
    raw_bytes = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + secret,
        "HTTP-Referer": APP_REFERER,
        "X-OpenRouter-Title": APP_TITLE,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=raw_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = int(exc.code)
    except urllib.error.URLError as exc:
        print("ERROR network: " + redact(str(exc.reason), secret), file=sys.stderr)
        return 0, {"error": "network"}
    raw = redact(raw, secret)
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def snippet(text: str, n: int = 120) -> str:
    compact = " ".join(str(text).split())
    return compact if len(compact) <= n else compact[: n - 1] + "..."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="T0 OpenRouter completion (never logs the secret)"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default="Reply with the single word: pong")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--show-limits", action="store_true")
    parser.add_argument("--skip-generation", action="store_true")
    args = parser.parse_args(argv)

    secret = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not secret:
        print(
            "ERROR: environment variable OPENROUTER_API_KEY is missing", file=sys.stderr
        )
        return 2

    if args.show_limits:
        status, payload = request("GET", BASE + "/key", secret)
        print(f"key_http_status={status}")
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(data, dict):
            for field in (
                "is_free_tier",
                "is_management_key",
                "limit",
                "limit_reset",
                "limit_remaining",
                "usage",
                "usage_daily",
                "usage_weekly",
                "usage_monthly",
            ):
                if field in data:
                    print(f"key_{field}={data[field]}")

    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        "temperature": 0,
    }
    status, payload = request("POST", BASE + "/chat/completions", secret, body=body)
    print(f"http_status={status}")
    print(f"model_requested={args.model}")
    if not isinstance(payload, dict):
        print("ERROR non-json response: " + snippet(payload, 200), file=sys.stderr)
        return 3
    if status >= 400:
        err = payload.get("error", payload)
        if isinstance(err, dict):
            if "code" in err:
                print(f"error_code={err['code']}")
            meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
            if "limit_source" in meta:
                print(f"error_limit_source={meta['limit_source']}")
            rendered = json.dumps(err)
        else:
            rendered = str(err)
        print(f"ERROR http {status}: " + snippet(rendered, 240), file=sys.stderr)
        return 3

    model_used = payload.get("model") or args.model
    gen_id = payload.get("id")
    usage = payload.get("usage") or {}
    choices = payload.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        content = str(msg.get("content") or "")
    print(f"model_used={model_used}")
    print(f"generation_id={gen_id or ''}")
    if isinstance(usage, dict):
        print(f"prompt_tokens={usage.get('prompt_tokens', '')}")
        print(f"completion_tokens={usage.get('completion_tokens', '')}")
        print(f"total_tokens={usage.get('total_tokens', '')}")
    print(f"response_snippet={snippet(content)}")

    if gen_id and not args.skip_generation:
        gen_status, gen_payload = 0, {}
        encoded = urllib.parse.quote(str(gen_id), safe="")
        for attempt in range(4):
            if attempt:
                time.sleep(1.5)
            gen_status, gen_payload = request(
                "GET", BASE + "/generation?id=" + encoded, secret
            )
            if (
                gen_status == 200
                and isinstance(gen_payload, dict)
                and gen_payload.get("data")
            ):
                break
        print(f"generation_http_status={gen_status}")
        data = gen_payload.get("data") if isinstance(gen_payload, dict) else {}
        if isinstance(data, dict):
            for field in (
                "total_cost",
                "usage",
                "tokens_prompt",
                "tokens_completion",
                "model",
                "provider_name",
            ):
                if field in data:
                    print(f"generation_{field}={data[field]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
