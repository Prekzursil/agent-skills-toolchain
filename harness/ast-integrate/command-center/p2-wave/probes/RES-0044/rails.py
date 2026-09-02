#!/usr/bin/env python3
"""Two-rail live fetches for RES-0044 (05-ECO R1 structured API + R2 prose)."""
from __future__ import annotations

import base64
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
USER_AGENT = "ast-integrate-RES-0044-research/1.0 (two-rail evidence; no credentials)"
SSL_CTX = ssl.create_default_context()

SOURCES = [
    {
        "id": "r1-spec-github-api",
        "rail": "R1-structured-api",
        "origin": "api.github.com",
        "publisher": "GitHub Contents API",
        "organisation": "GitHub / modelcontextprotocol",
        "url": (
            "https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol"
            "/contents/docs/specification/2025-11-25/basic/authorization.mdx"
        ),
        "save": "spec-github-contents.json",
        "accept": "application/vnd.github+json",
        "kind": "github-contents-json",
        "decoded_name": "spec-authorization.mdx",
    },
    {
        "id": "r2-spec-docs-html",
        "rail": "R2-prose",
        "origin": "modelcontextprotocol.io",
        "publisher": "MCP specification site",
        "organisation": "Model Context Protocol project",
        "url": "https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization",
        "save": "spec-docs.html",
        "accept": "text/html",
        "kind": "html-prose",
        "decoded_name": None,
    },
    {
        "id": "r1-py-oauth2-github-api",
        "rail": "R1-structured-api",
        "origin": "api.github.com",
        "publisher": "GitHub Contents API",
        "organisation": "GitHub / modelcontextprotocol",
        "url": (
            "https://api.github.com/repos/modelcontextprotocol/python-sdk"
            "/contents/src/mcp/client/auth/oauth2.py"
        ),
        "save": "python-oauth2-github.json",
        "accept": "application/vnd.github+json",
        "kind": "github-contents-json",
        "decoded_name": "python-oauth2.py",
    },
    {
        "id": "r2-py-sdk-readme",
        "rail": "R2-prose",
        "origin": "raw.githubusercontent.com",
        "publisher": "python-sdk OAuth client guide",
        "organisation": "Model Context Protocol project",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/python-sdk"
            "/main/docs/client/oauth-clients.md"
        ),
        "save": "python-oauth-clients.md",
        "accept": "text/plain",
        "kind": "markdown-prose",
        "decoded_name": None,
    },
    {
        "id": "r1-ts-auth-github-api",
        "rail": "R1-structured-api",
        "origin": "api.github.com",
        "publisher": "GitHub Contents API",
        "organisation": "GitHub / modelcontextprotocol",
        "url": (
            "https://api.github.com/repos/modelcontextprotocol/typescript-sdk"
            "/contents/packages/client/src/client/auth.ts"
        ),
        "save": "ts-auth-github.json",
        "accept": "application/vnd.github+json",
        "kind": "github-contents-json",
        "decoded_name": "ts-auth.ts",
    },
    {
        "id": "r2-ts-oauth-docs",
        "rail": "R2-prose",
        "origin": "raw.githubusercontent.com",
        "publisher": "typescript-sdk OAuth client guide",
        "organisation": "Model Context Protocol project",
        "url": (
            "https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk"
            "/main/docs/clients/oauth.md"
        ),
        "save": "ts-oauth.md",
        "accept": "text/plain",
        "kind": "markdown-prose",
        "decoded_name": None,
    },
    {
        "id": "r1-inspector-cli-github-api",
        "rail": "R1-structured-api",
        "origin": "api.github.com",
        "publisher": "GitHub Contents API",
        "organisation": "GitHub / modelcontextprotocol",
        "url": (
            "https://api.github.com/repos/modelcontextprotocol/inspector"
            "/contents/clients/cli/src/cliOAuth.ts"
        ),
        "save": "inspector-cliOAuth-github.json",
        "accept": "application/vnd.github+json",
        "kind": "github-contents-json",
        "decoded_name": "inspector-cliOAuth.ts",
    },
    {
        "id": "r2-inspector-readme",
        "rail": "R2-prose",
        "origin": "raw.githubusercontent.com",
        "publisher": "inspector README",
        "organisation": "Model Context Protocol project",
        "url": "https://raw.githubusercontent.com/modelcontextprotocol/inspector/main/README.md",
        "save": "inspector-README.md",
        "accept": "text/plain",
        "kind": "markdown-prose",
        "decoded_name": None,
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def record_from_cache(src: dict) -> dict | None:
    """Rebuild a rail record from an on-disk capture. Resume path: do not re-fetch."""
    path = CAPTURES / src["save"]
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    body = path.read_bytes()
    rec = {
        "id": src["id"],
        "rail": src["rail"],
        "origin": src["origin"],
        "publisher": src["publisher"],
        "organisation": src["organisation"],
        "permalink": src["url"],
        "requested_url": src["url"],
        "fetch_status": "ok",
        "http_status": 200,
        "fetched_at": _mtime_utc(path),
        "elapsed_ms": 0,
        "content_type": src["accept"],
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "capture_path": "command-center/p2-wave/probes/RES-0044/captures/" + src["save"],
        "kind": src["kind"],
        "html_url": None,
        "git_blob_sha": None,
        "decoded_sha256": None,
        "decoded_bytes": None,
        "decoded_path": None,
        "from_capture_cache": True,
    }
    if src["kind"] == "github-contents-json":
        try:
            meta = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        rec["html_url"] = meta.get("html_url")
        rec["git_blob_sha"] = meta.get("sha")
        rec["github_size"] = meta.get("size")
        decoded_name = src.get("decoded_name")
        if decoded_name:
            dec_path = CAPTURES / decoded_name
            if not dec_path.is_file() and meta.get("encoding") == "base64" and meta.get("content"):
                dec_path.write_bytes(base64.b64decode(meta["content"]))
            if not dec_path.is_file() or dec_path.stat().st_size <= 0:
                return None
            decoded = dec_path.read_bytes()
            rec["decoded_sha256"] = sha256_bytes(decoded)
            rec["decoded_bytes"] = len(decoded)
            rec["decoded_path"] = (
                "command-center/p2-wave/probes/RES-0044/captures/" + decoded_name
            )
    return rec


def fetch_one(src: dict) -> dict:
    req = urllib.request.Request(
        src["url"],
        headers={"User-Agent": USER_AGENT, "Accept": src["accept"]},
        method="GET",
    )
    fetched_at = utc_now()
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=45) as resp:
            body = resp.read()
            status = int(resp.status)
            final = resp.geturl()
            ctype = resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as exc:
        body = exc.read() or b""
        status = int(exc.code)
        final = src["url"]
        ctype = exc.headers.get("Content-Type") if exc.headers else ""
    except Exception as exc:
        cached = record_from_cache(src)
        if cached:
            cached["live_error"] = f"{type(exc).__name__}: {exc}"
            return cached
        return {
            "id": src["id"],
            "rail": src["rail"],
            "origin": src["origin"],
            "publisher": src["publisher"],
            "organisation": src["organisation"],
            "permalink": src["url"],
            "requested_url": src["url"],
            "fetch_status": "error",
            "http_status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "fetched_at": fetched_at,
            "sha256": None,
            "bytes": 0,
            "kind": src["kind"],
        }
    elapsed_ms = int((time.time() - t0) * 1000)
    if status != 200:
        cached = record_from_cache(src)
        if cached:
            cached["live_http_status"] = status
            return cached
        return {
            "id": src["id"],
            "rail": src["rail"],
            "origin": src["origin"],
            "publisher": src["publisher"],
            "organisation": src["organisation"],
            "permalink": src["url"],
            "requested_url": src["url"],
            "fetch_status": "http-error",
            "http_status": status,
            "fetched_at": fetched_at,
            "elapsed_ms": elapsed_ms,
            "content_type": ctype,
            "sha256": sha256_bytes(body),
            "bytes": len(body),
            "kind": src["kind"],
        }
    CAPTURES.mkdir(parents=True, exist_ok=True)
    (CAPTURES / src["save"]).write_bytes(body)
    rec = {
        "id": src["id"],
        "rail": src["rail"],
        "origin": src["origin"],
        "publisher": src["publisher"],
        "organisation": src["organisation"],
        "permalink": final,
        "requested_url": src["url"],
        "fetch_status": "ok",
        "http_status": status,
        "fetched_at": fetched_at,
        "elapsed_ms": elapsed_ms,
        "content_type": ctype,
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "capture_path": "command-center/p2-wave/probes/RES-0044/captures/" + src["save"],
        "kind": src["kind"],
        "html_url": None,
        "git_blob_sha": None,
        "decoded_sha256": None,
        "decoded_bytes": None,
        "decoded_path": None,
    }
    if src["kind"] == "github-contents-json":
        try:
            meta = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            meta = {}
        rec["html_url"] = meta.get("html_url")
        rec["git_blob_sha"] = meta.get("sha")
        rec["github_size"] = meta.get("size")
        if meta.get("encoding") == "base64" and meta.get("content") and src.get("decoded_name"):
            decoded = base64.b64decode(meta["content"])
            dec_path = CAPTURES / src["decoded_name"]
            dec_path.write_bytes(decoded)
            rec["decoded_sha256"] = sha256_bytes(decoded)
            rec["decoded_bytes"] = len(decoded)
            rec["decoded_path"] = (
                "command-center/p2-wave/probes/RES-0044/captures/" + src["decoded_name"]
            )
    return rec


def fetch_all() -> list[dict]:
    rows = []
    for src in SOURCES:
        cached = record_from_cache(src)
        if cached:
            rows.append(cached)
            continue
        rows.append(fetch_one(src))
    return rows


def load_decoded_spec() -> str:
    return (CAPTURES / "spec-authorization.mdx").read_text(encoding="utf-8")
