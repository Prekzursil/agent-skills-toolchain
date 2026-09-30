"""model-router front — cost-aware model cascade (added 2026-09-29).

Route table (strict, caller-declared via task_kind — no silent degradation):
  mechanical  scan parsing / summaries / extraction -> LOCAL Ollama
              qwen3:4b via the OpenAI-compatible endpoint
              http://127.0.0.1:11434/v1 (free, loopback-only)
  reasoning   exploit planning / chain analysis -> GLM through the existing
              fronts.zai_keys invoke (call-time dual-key rotation), falling
              back to the OpenAI API ONLY via env OPENAI_API_KEY when the
              Z.AI tier fails. Unconfigured fallback = honest error, never a
              silent reroute.

qwen3 is a thinking model: measured 2026-09-29, small max_tokens get burned
by the reasoning field and content comes back EMPTY, so every local call
gets a "/no_think" system nudge and the response's reasoning field (and any
inline <think> blocks) is stripped before returning.

Measured on this box (CPU-only inference, ~4-10 tok/s, cold model load
30-200s): a structured parse thinks ~1300 tokens (measured 2026-09-29,
reasoning 4717 chars) BEFORE any content. Measured 2026-09-30 (grill
round 1): at max_tokens=3072 one default one-line-summary call burned
the WHOLE budget on reasoning and returned empty content (honest
failure), and the retry only just fit at 2460/3072 completion tokens —
so 3072 sits at the edge of what qwen3:4b consumes before any content.
The local tier therefore defaults to max_tokens=6144 (2x the observed
near-exhaustion point) and a 900s timeout (covers the full 6144 at the
measured ~8.6 tok/s burn rate) - both overridable per call. The /v1
endpoint ignores think:false / reasoning_effort (0.34.4) but DOES honor
keep_alive, which is sent so the model stays loaded between intermittent
gateway calls instead of reloading per call.

Tools (via run(tool, args)):
  route   {"task_kind": "mechanical"|"reasoning", "payload": <str|dict>}
          payload: plain string, or {"prompt": ...} / {"messages": [...]}.
          optional: system, model, max_tokens, temperature, timeout.
  status  cascade table: endpoints, model presence, zai key sha8s, whether
          the OpenAI fallback env var is set (presence only), call counters.

Env overrides (all optional): MODEL_ROUTER_LOCAL_BASE_URL,
MODEL_ROUTER_LOCAL_MODEL, MODEL_ROUTER_REASONING_MODEL,
MODEL_ROUTER_OPENAI_MODEL, OPENAI_BASE_URL (standard OpenAI-compat override).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from . import zai_keys

LOCAL_BASE_URL = os.environ.get("MODEL_ROUTER_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
LOCAL_MODEL = os.environ.get("MODEL_ROUTER_LOCAL_MODEL", "qwen3:4b")
REASONING_MODEL = os.environ.get("MODEL_ROUTER_REASONING_MODEL", "glm-4.6")
OPENAI_MODEL = os.environ.get("MODEL_ROUTER_OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
KEEP_ALIVE = os.environ.get("MODEL_ROUTER_KEEP_ALIVE", "30m")

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

# in-process counters (since gateway start) - passive, no timers
_COUNTS = {"mechanical": 0, "reasoning_glm": 0, "reasoning_openai": 0, "errors": 0}


def _post_json(url: str, body: dict, headers: dict, timeout: float) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:600]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def _messages(payload) -> list[dict] | None:
    """Normalize payload -> OpenAI-style messages, or None if unusable."""
    msgs = None
    if isinstance(payload, str) and payload.strip():
        msgs = [{"role": "user", "content": payload}]
    elif isinstance(payload, dict):
        raw = payload.get("messages")
        if isinstance(raw, list) and raw:
            norm = [{"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
                    for m in raw if isinstance(m, dict)]
            if norm:
                msgs = norm
        elif isinstance(payload.get("prompt"), str) and payload["prompt"].strip():
            msgs = [{"role": "user", "content": payload["prompt"]}]
        elif isinstance(payload.get("text"), str) and payload["text"].strip():
            msgs = [{"role": "user", "content": payload["text"]}]
    if not msgs:
        return None
    return msgs


def _strip_thinking(text: str) -> str:
    text = THINK_RE.sub("", text or "")
    return text.strip()


def _local_chat(messages: list[dict], max_tokens: int, temperature: float | None,
                model: str | None, timeout: float) -> dict:
    """Ollama OpenAI-compat chat. Returns {"ok": ..., ...} - never raises."""
    msgs = [dict(m) for m in messages]
    sys_idx = next((i for i, m in enumerate(msgs) if m["role"] == "system"), None)
    if sys_idx is None:
        msgs.insert(0, {"role": "system", "content": "/no_think"})
    elif "/no_think" not in msgs[sys_idx]["content"]:
        msgs[sys_idx]["content"] = msgs[sys_idx]["content"] + " /no_think"
    body: dict = {"model": model or LOCAL_MODEL, "messages": msgs,
                  "stream": False, "max_tokens": max_tokens,
                  "keep_alive": KEEP_ALIVE}
    if temperature is not None:
        body["temperature"] = temperature
    status, resp = _post_json(f"{LOCAL_BASE_URL}/chat/completions", body, {}, timeout)
    if status != 200 or not isinstance(resp, dict):
        return {"ok": False, "tier": "local-ollama", "status": status, "error": str(resp)[:500]}
    try:
        choice = resp["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "tier": "local-ollama", "error": f"unexpected response shape: {str(resp)[:300]}"}
    content = _strip_thinking(choice.get("content"))
    if not content:
        return {"ok": False, "tier": "local-ollama",
                "error": "local model returned empty content (reasoning consumed the budget)",
                "reasoning_preview": (choice.get("reasoning") or "")[:200]}
    return {"ok": True, "tier": "local-ollama", "model": resp.get("model", body["model"]),
            "content": content,
            "usage": resp.get("usage")}


def _openai_chat(messages: list[dict], max_tokens: int, temperature: float | None,
                 model: str | None, timeout: float) -> dict:
    """OpenAI fallback. Honest failure when OPENAI_API_KEY is absent."""
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "tier": "openai-fallback",
                "error": "OPENAI_API_KEY not set - fallback unconfigured (no silent reroute)"}
    body: dict = {"model": model or OPENAI_MODEL, "messages": messages,
                  "stream": False, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    status, resp = _post_json(f"{OPENAI_BASE}/chat/completions", body,
                              {"Authorization": f"Bearer {key}"}, timeout)
    if status != 200 or not isinstance(resp, dict):
        return {"ok": False, "tier": "openai-fallback", "status": status, "error": str(resp)[:500]}
    try:
        content = _strip_thinking(resp["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "tier": "openai-fallback", "error": f"unexpected response shape: {str(resp)[:300]}"}
    if not content:
        return {"ok": False, "tier": "openai-fallback", "error": "empty content from OpenAI fallback"}
    return {"ok": True, "tier": "openai-fallback", "model": resp.get("model", body["model"]),
            "content": content, "usage": resp.get("usage")}


def _glm_chat(messages: list[dict], max_tokens: int, temperature: float | None,
              model: str | None) -> dict:
    """GLM through the zai-keys front (rotating keys). Returns {"ok": ...}."""
    payload: dict = {"model": model or REASONING_MODEL, "messages": messages,
                     "max_tokens": max_tokens, "stream": False}
    if temperature is not None:
        payload["temperature"] = temperature
    out = zai_keys.run("invoke", {"payload": payload})
    try:
        res = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "tier": "glm-coding-plan", "error": f"zai-keys returned non-JSON: {out[:300]}"}
    if not res.get("ok"):
        return {"ok": False, "tier": "glm-coding-plan", "error": str(res)[:600]}
    try:
        msg = res["response"]["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "tier": "glm-coding-plan", "error": f"unexpected zai response shape: {str(res)[:300]}"}
    content = _strip_thinking(msg.get("content") or "")
    if not content and msg.get("reasoning_content"):
        return {"ok": False, "tier": "glm-coding-plan",
                "error": "GLM returned reasoning only, no content",
                "reasoning_preview": str(msg.get("reasoning_content"))[:200]}
    if not content:
        return {"ok": False, "tier": "glm-coding-plan", "error": "empty content from GLM"}
    return {"ok": True, "tier": "glm-coding-plan", "model": res["response"].get("model", payload["model"]),
            "used_sha8": res.get("used_sha8"), "rotated": res.get("rotated"),
            "content": content, "usage": res["response"].get("usage")}


def _route(task_kind: str, payload, args: dict) -> dict:
    messages = _messages(payload)
    if messages is None:
        return {"ok": False, "error": "payload must be a non-empty string, "
                "{'prompt': ...}, or {'messages': [...]} (no secret ever echoed)"}
    system = args.get("system")
    if isinstance(system, str) and system.strip():
        messages = [{"role": "system", "content": system}] + [
            m for m in messages if m["role"] != "system"]
    max_tokens = int(args.get("max_tokens") or (6144 if task_kind == "mechanical" else 2048))
    temperature = args.get("temperature")
    temperature = float(temperature) if temperature is not None else None
    model = args.get("model") if isinstance(args.get("model"), str) else None
    timeout = float(args.get("timeout") or (900.0 if task_kind == "mechanical" else 150.0))
    started = time.time()

    if task_kind == "mechanical":
        out = _local_chat(messages, max_tokens, temperature, model, timeout)
        if not out.get("ok"):
            _COUNTS["errors"] += 1
        else:
            _COUNTS["mechanical"] += 1
        out["elapsed_s"] = round(time.time() - started, 2)
        return out

    if task_kind == "reasoning":
        out = _glm_chat(messages, max_tokens, temperature, model)
        if out.get("ok"):
            _COUNTS["reasoning_glm"] += 1
            out["elapsed_s"] = round(time.time() - started, 2)
            return out
        glm_err = out.get("error")
        fb = _openai_chat(messages, max_tokens, temperature, model, timeout)
        if fb.get("ok"):
            _COUNTS["reasoning_openai"] += 1
            fb["glm_failure"] = glm_err
            fb["elapsed_s"] = round(time.time() - started, 2)
            return fb
        _COUNTS["errors"] += 1
        return {"ok": False, "error": "reasoning tier failed at both levels",
                "glm": glm_err, "openai_fallback": fb.get("error"),
                "elapsed_s": round(time.time() - started, 2)}

    return {"ok": False, "error": f"unknown task_kind '{task_kind}'",
            "valid": ["mechanical", "reasoning"]}


def _ollama_reachable() -> dict:
    try:
        with urllib.request.urlopen(f"{LOCAL_BASE_URL}/models", timeout=4) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        ids = [m.get("id", "") for m in data.get("data", [])]
        return {"reachable": True, "models": ids,
                "model_present": LOCAL_MODEL in ids}
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "error": f"{type(e).__name__}: {e}"}


def run(tool: str, args: dict) -> str:
    args = args or {}
    if tool == "route":
        task_kind = args.get("task_kind")
        if not isinstance(task_kind, str) or not task_kind.strip():
            return json.dumps({"ok": False, "error": "task_kind required",
                               "valid": ["mechanical", "reasoning"]})
        return json.dumps(_route(task_kind.strip().lower(), args.get("payload"), args))
    if tool == "status":
        openai_set = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
        zai = json.loads(zai_keys.run("status", {}))
        return json.dumps({
            "cascade": [
                {"tier": "mechanical", "target": f"Ollama {LOCAL_MODEL}",
                 "endpoint": LOCAL_BASE_URL, **_ollama_reachable()},
                {"tier": "reasoning", "target": f"GLM {REASONING_MODEL} via zai-keys (rotating)",
                 "keys_sha8": zai.get("keys"), "active_sha8": zai.get("active_sha8"),
                 "state_file": zai.get("state_file")},
                {"tier": "reasoning-fallback", "target": f"OpenAI {OPENAI_MODEL}",
                 "base_url": OPENAI_BASE, "configured": openai_set,
                 "note": None if openai_set else "OPENAI_API_KEY not set - fallback returns an honest error"},
            ],
            "counters_since_gateway_start": dict(_COUNTS),
        }, indent=2)
    return json.dumps({"error": f"unknown tool '{tool}'", "tools": ["route", "status"]})
