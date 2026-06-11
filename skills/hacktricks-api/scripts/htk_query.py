#!/usr/bin/env python3
"""HackTricks AI API client — cached, rate-limit-aware RAG/chat over the HackTricks corpus.

Stdlib only (urllib). API key is read from env HACKTRICKS_API_KEY and is NEVER printed or logged
(redacted from all output, including HTTP error bodies). RAG responses are cached by content hash so
repeat queries cost no quota; a usage guard refuses to spend when the weekly quota is near zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("HACKTRICKS_API_BASE", "https://ai.hacktricks.wiki").rstrip("/")
DEFAULT_CORPUS = os.environ.get("HACKTRICKS_CORPUS", "D:/knowledge/hacktricks")
USAGE_FLOOR = int(os.environ.get("HACKTRICKS_USAGE_FLOOR", "2"))
MAX_QUERY = 2000
TIMEOUT = 30


class HtkError(Exception):
    """Raised for any client-side or API error (always key-redacted)."""


def _key_from_user_env():
    """Windows fallback: read the persisted HKCU\\Environment value (User-scope env var).
    Covers the common case where a parent process was started before the var was set."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
            val, _ = winreg.QueryValueEx(reg, "HACKTRICKS_API_KEY")
            return val or None
    except OSError:
        return None


def _key() -> str:
    k = os.environ.get("HACKTRICKS_API_KEY")
    if not k and sys.platform == "win32":
        k = _key_from_user_env()
    if not k:
        raise HtkError("HACKTRICKS_API_KEY is not set (env or Windows user environment)")
    return k


def _redact(text: str, key: str) -> str:
    return text.replace(key, "***REDACTED***") if key and key in text else text


def _cache_dir() -> str:
    return os.environ.get("HACKTRICKS_CACHE", os.path.join(DEFAULT_CORPUS, ".cache"))


def _canon(body: dict) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def _cache_path(endpoint: str, body: dict) -> str:
    digest = hashlib.sha256((endpoint + "\n" + _canon(body)).encode("utf-8")).hexdigest()
    return os.path.join(_cache_dir(), digest + ".json")


def _http_json(method: str, path: str, body: dict | None = None) -> dict:
    key = _key()
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-API-Key", key)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise HtkError(_redact(f"HTTP {exc.code} on {path}: {detail}".strip(), key)) from None
    except urllib.error.URLError as exc:
        raise HtkError(_redact(f"network error on {path}: {exc.reason}", key)) from None


def usage() -> dict:
    """GET /api/v1/rag/usage -> {used, limit, remaining}. Does not consume quota."""
    return _http_json("GET", "/api/v1/rag/usage")


def rag(query: str, max_results: int = 3, rewrite_query: bool = False) -> tuple[dict, bool]:
    """POST /api/v1/rag. Returns (response, cached). Cache-first; usage-guarded before any spend."""
    query = (query or "").strip()
    if not query:
        raise HtkError("empty query")
    if len(query) > MAX_QUERY:
        query = query[:MAX_QUERY]
    body: dict = {"query": query, "max_results": max(1, min(5, int(max_results)))}
    if rewrite_query:
        body["rewrite_query"] = True

    cache_path = _cache_path("/api/v1/rag", body)
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            return json.load(fh), True

    remaining = int(usage().get("remaining", 0))
    if remaining <= USAGE_FLOOR:
        raise HtkError(
            f"RAG quota low (remaining={remaining} <= floor={USAGE_FLOOR}); refusing to spend. "
            "Use the local 'hacktricks' search skill instead."
        )

    result = _http_json("POST", "/api/v1/rag", body)
    os.makedirs(_cache_dir(), exist_ok=True)
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    os.replace(tmp, cache_path)
    return result, False


def chat(message: str, thread_id: str | None = None, model: str | None = None) -> dict:
    """POST /api/v1/chat[/{thread_id}]. Conversational, not cached; shares the weekly cap."""
    message = (message or "").strip()
    if not message:
        raise HtkError("empty message")
    body: dict = {"message": message[:MAX_QUERY]}
    if model:
        body["model"] = model
    path = f"/api/v1/chat/{thread_id}" if thread_id else "/api/v1/chat"
    return _http_json("POST", path, body)


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="HackTricks AI API client (cached, quota-aware)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("usage")
    p_rag = sub.add_parser("rag")
    p_rag.add_argument("query")
    p_rag.add_argument("--max-results", type=int, default=3)
    p_rag.add_argument("--rewrite", action="store_true")
    p_chat = sub.add_parser("chat")
    p_chat.add_argument("message")
    p_chat.add_argument("--thread")
    p_chat.add_argument("--model")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "usage":
            print(json.dumps(usage(), indent=2))
        elif args.cmd == "rag":
            result, cached = rag(args.query, args.max_results, args.rewrite)
            print(json.dumps({"cached": cached, **result}, indent=2))
        elif args.cmd == "chat":
            print(json.dumps(chat(args.message, args.thread, args.model), indent=2))
    except HtkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
