#!/usr/bin/env python3
"""Credential scanner for RES-0044 artifacts.

Detects credential *material* (values), not location names. A hop that says
the access token lives in process-memory TokenStorage is allowed. A hop that
embeds a JWT, Bearer token, PEM, or vendor secret prefix is not.

Never prints a matching value — only JSON pointer, rule id, and a
zero-entropy prefix of at most 4 characters.
"""
from __future__ import annotations

import json
import re
from typing import Any

# JWT header starts with base64url of {"alg":...} — typically eyJ.
JWT_RE = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}")
BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+=/]{12,}")
PEM_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
ASSIGN_RE = re.compile(
    r"(?i)(?:access_token|refresh_token|id_token|client_secret|api_key|authorization)"
    r"""\s*[:=]\s*['\"]?[A-Za-z0-9._\-+=/]{12,}"""
)
PREFIX_RE = re.compile(
    r"(?:sk-ant-|sk-live-|sk-proj-|ghp_|gho_|ghu_|ghs_|github_pat_|AKIA)[A-Za-z0-9_\-]{8,}"
)
SECRET_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "client_secret_basic",
        "api_key",
        "apikey",
        "authorization",
        "password",
        "private_key",
        "secret",
        "token",
        "credential",
        "credentials",
    }
)
# Values that name a location rather than carry material.
LOCATION_OK = re.compile(
    r"^(none|absent|n/a|not-present|process-memory|os-keychain|env-name-only|"
    r"authorization-header-tls|redirect-uri-ephemeral|idp-not-in-client|"
    r"www-authenticate-header-ephemeral|public-metadata|client-memory-pkce|"
    r"as-client-registry|tls-authorization-header)(:.*)?$",
    re.I,
)


def _prefix(value: str) -> str:
    raw = value[:4]
    return "".join(ch if ch.isalnum() else "." for ch in raw)


def _walk(node: Any, path: str, hits: list[dict]) -> None:
    if isinstance(node, dict):
        for key, val in node.items():
            child = f"{path}/{key}" if path else f"/{key}"
            key_l = str(key).lower()
            if key_l in SECRET_KEYS and isinstance(val, str) and val.strip():
                if not LOCATION_OK.match(val.strip()):
                    hits.append(
                        {
                            "path": child,
                            "rule": "secret-key-non-location-value",
                            "prefix": _prefix(val),
                        }
                    )
            _walk(val, child, hits)
    elif isinstance(node, list):
        for i, val in enumerate(node):
            _walk(val, f"{path}/{i}", hits)
    elif isinstance(node, str):
        for rule, cre in (
            ("jwt", JWT_RE),
            ("bearer", BEARER_RE),
            ("pem-private-key", PEM_RE),
            ("assigned-secret", ASSIGN_RE),
            ("vendor-prefix", PREFIX_RE),
        ):
            if cre.search(node):
                hits.append({"path": path or "/", "rule": rule, "prefix": _prefix(node)})
                break


def scan_obj(doc: Any) -> dict:
    hits: list[dict] = []
    _walk(doc, "", hits)
    return {
        "credential_free": len(hits) == 0,
        "hit_count": len(hits),
        "hits": hits,
    }


def scan_text(text: str, path: str = "/") -> dict:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = text
    result = scan_obj(doc)
    result["scanned_path"] = path
    return result


def scan_path(path) -> dict:
    raw = path.read_text(encoding="utf-8")
    result = scan_text(raw, str(path))
    result["bytes"] = len(raw.encode("utf-8"))
    return result


def plant_jwt(doc: dict, pointer_key: str = "_planted_control") -> dict:
    """In-memory mutant: embed a synthetic JWT. Never write this object to disk."""
    import copy

    mutant = copy.deepcopy(doc)
    header = "eyJhbGciOiJub25lIn0"
    # payload is {"plant":"RES-0044-neg"} — constructed, not a live token.
    payload = "eyJwbGFudCI6IlJFUy0wMDQ0LW5lZyJ9"
    mutant[pointer_key] = f"{header}.{payload}.planted-sig"
    return mutant
