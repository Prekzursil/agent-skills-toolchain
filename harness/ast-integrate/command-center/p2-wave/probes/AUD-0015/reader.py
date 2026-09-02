"""Field-scoped MCP reader. Never serialises env/credential values."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PLANTED_SECRET = "AUD0015-PLANTED-SECRET-NOT-A-REAL-KEY-9f3c2a17"

MCP_ROOT_KEYS = frozenset(
    {
        "mcpServers",
        "disabledMcpServers",
        "enabledMcpServers",
        "enabledMcpjsonServers",
        "enableAllProjectMcpServers",
        "projects",
    }
)
PROJECT_KEYS = frozenset(
    {
        "mcpServers",
        "disabledMcpServers",
        "enabledMcpServers",
    }
)
SERVER_KEEP = frozenset({"command", "args", "type", "url", "serverUrl"})
DROP_KEYS = frozenset(
    {
        "env",
        "headers",
        "envFile",
        "authorization",
        "apiKey",
        "api_key",
        "token",
        "oauth",
        "apiKeyHelper",
    }
)
CRED_ARG_NEEDLES = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")


def redact_arg(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if "=" in value:
        key, _, rest = value.partition("=")
        if any(n in key.upper() for n in CRED_ARG_NEEDLES):
            return f"{key}=<redacted len={len(rest)}>"
    prefixes = ("sk-", "ghp_", "github_pat_", "xox", "glpat-", "crv1_")
    if value.startswith(prefixes):
        return f"<redacted prefix={value[:4]} len={len(value)}>"
    return value


def redact_url(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    parts = urlsplit(value)
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        netloc = host
        return urlunsplit((parts.scheme, netloc, parts.path, "", parts.fragment))
    if parts.query:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "<redacted-query>", parts.fragment))
    return value


def sanitize_server(cfg: Any) -> dict:
    if not isinstance(cfg, dict):
        return {"_shape": type(cfg).__name__}
    out: dict[str, Any] = {}
    dropped = []
    for key, val in cfg.items():
        if key in DROP_KEYS or str(key).lower() in {k.lower() for k in DROP_KEYS}:
            dropped.append(str(key))
            continue
        if key == "args" and isinstance(val, list):
            out[key] = [redact_arg(x) for x in val]
        elif key in {"url", "serverUrl"}:
            out[key] = redact_url(val)
        elif key in SERVER_KEEP:
            out[key] = redact_arg(val) if isinstance(val, str) else val
    if dropped:
        out["_dropped_keys"] = sorted(dropped)
        out["_dropped_count"] = len(dropped)
    return out


def sanitize_server_map(value: Any) -> dict[str, dict]:
    if not isinstance(value, dict):
        return {}
    return {str(name): sanitize_server(cfg) for name, cfg in value.items()}


def _extract_object(doc: dict, allowed: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in sorted(doc):
        if key not in allowed:
            continue
        val = doc[key]
        if key == "mcpServers":
            out[key] = sanitize_server_map(val)
        elif key == "projects" and isinstance(val, dict):
            projects = {}
            for proj, body in val.items():
                if not isinstance(body, dict):
                    continue
                sliced = _extract_object(body, PROJECT_KEYS)
                if sliced:
                    projects[str(proj)] = sliced
            out[key] = projects
        else:
            out[key] = val
    return out


def extract_mcp_fields(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {}
    return _extract_object(doc, MCP_ROOT_KEYS)


def load_json_scoped(path: Path) -> dict[str, Any]:
    """Read a JSON file and return only MCP-relevant fields.

    The raw document is never returned. Credential-bearing keys are dropped
    before the result is built.
    """
    rec: dict[str, Any] = {
        "path": str(path),
        "status": "ABSENT",
        "bytes": 0,
        "mcp_keys": [],
        "payload": {},
        "parse_error": None,
    }
    if not path.is_file():
        return rec
    rec["bytes"] = path.stat().st_size
    rec["status"] = "PRESENT"
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        rec["status"] = "UNPARSEABLE"
        rec["parse_error"] = type(exc).__name__
        return rec
    payload = extract_mcp_fields(doc)
    rec["payload"] = payload
    rec["mcp_keys"] = sorted(payload)
    if not payload:
        rec["status"] = "PRESENT_NO_MCP_KEYS"
    return rec


def leak_hits(text: str, extra: list[str] | None = None) -> list[str]:
    """Return labels of secrets found in text. Never returns secret values."""
    hits: list[str] = []
    needles = list(extra or [])
    if PLANTED_SECRET not in needles:
        needles.append(PLANTED_SECRET)
    for item in needles:
        if item and item in text:
            hits.append("planted-synthetic" if item == PLANTED_SECRET else "extra")
    return hits
