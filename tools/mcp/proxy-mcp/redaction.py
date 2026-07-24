#!/usr/bin/env python3
"""redaction.py -- credential scrubbing for the proxy-mcp traffic surface.

An intercepting proxy sees EVERYTHING: ``Authorization`` bearers, session
cookies, ``Set-Cookie`` grants, API keys in query strings, and passwords in JSON
bodies. The adopted upstream engine (snapspecter/mitmproxy-mcp) returns all of it
verbatim -- measured, not assumed: a probe with a sentinel bearer token came back
in cleartext through ``inspect_flow``. Every one of those bytes would otherwise
land in an agent transcript, which is a durable and often uploaded artifact.

This module is the scrubbing layer applied to every ``tools/call`` result before
it reaches the MCP client.

Design notes
------------
* **Default ON, opt-out explicit.** The sibling ``_shared/hardening.py``
  ConfirmGate ships SHADOW-by-default because a *blocking* gate that fires
  wrongly breaks a workflow. Redaction is the opposite kind of control: it is a
  confidentiality guarantee, and a confidentiality guarantee that defaults to
  "observe only" provides nothing. So this defaults to ENFORCE and an operator
  must consciously set ``PROXY_MCP_REDACT=off`` to see raw credentials.
* **Name-and-length, never value.** A redacted value becomes
  ``<redacted:sha256=ab12cd34,len=64>``. The short digest lets an operator
  correlate ("same token as that other flow") and diff across requests WITHOUT
  the value being recoverable; the length aids debugging a truncated credential.
  This mirrors the workspace rule that key names and lengths may be reported but
  values never.
* **Fail closed on structure.** If a payload cannot be parsed as JSON, a regex
  pass still scrubs recognisable header and query forms rather than passing the
  blob through untouched.
* Stdlib only, pure functions, no I/O -- matching the house hub modules.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

__all__ = [
    "SENSITIVE_FIELDS",
    "SENSITIVE_HEADERS",
    "mask",
    "redact_obj",
    "redact_text",
    "redaction_enabled",
]

# Header names whose VALUE is a credential. Compared case-insensitively.
SENSITIVE_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "x-authentication",
        "authentication",
        "x-access-token",
        "x-refresh-token",
        "x-session-token",
        "x-csrf-token",
        "x-xsrf-token",
        "x-amz-security-token",
        "x-goog-api-key",
        "private-token",
        "auth-token",
        "session-token",
    }
)

# Body/query keys whose VALUE is a credential. Matched on a normalised key
# (lowercased, ``-``/space -> ``_``) by exact hit or by an unambiguous stem.
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "client_secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "credential",
        "credentials",
        "private_key",
        "session",
        "session_id",
        "sessionid",
        "sid",
        "otp",
        "mfa_code",
        "signature",
        "sig",
        "assertion",
    }
)

# Unambiguous stems: any key CONTAINING one of these is treated as sensitive.
_SENSITIVE_STEMS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "auth_token",
    "session_token",
    "bearer",
)

_PLACEHOLDER_RE = re.compile(r"^<redacted:")

# ``Name: value`` header occurrences inside a text blob -- NOT anchored to the
# start of a line. Upstream renders a reproducible shell command per flow
# (``curl -X GET ... -H 'Authorization: Bearer ...'``), so a line-anchored
# pattern misses the credential entirely: it sits mid-line inside quotes. The
# value runs to the closing quote or end of line.
_HEADER_LINE_RE = re.compile(
    r"(?i)([\"']?\b("
    + "|".join(re.escape(h) for h in sorted(SENSITIVE_HEADERS))
    + r")\b[\"']?\s*[:=]\s*)([^\"'\r\n]+)"
)

# ``?key=value`` / ``&key=value`` query parameters.
_QUERY_PARAM_RE = re.compile(
    r"(?i)([?&](?:"
    + "|".join(re.escape(f) for f in sorted(SENSITIVE_FIELDS))
    + r")=)([^&\s\"']+)"
)

_HEADER_KEYS = {"headers", "header"}


def redaction_enabled() -> bool:
    """Whether scrubbing is active. Default ON; ``PROXY_MCP_REDACT=off`` disables."""
    return os.environ.get("PROXY_MCP_REDACT", "on").strip().lower() not in {
        "off",
        "0",
        "false",
        "no",
    }


def _normalise(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def _is_sensitive_key(key: str, *, header: bool = False) -> bool:
    """True when ``key`` names a credential-bearing header or field."""
    if header and key.strip().lower() in SENSITIVE_HEADERS:
        return True
    norm = _normalise(key)
    if norm in SENSITIVE_FIELDS:
        return True
    return any(stem in norm for stem in _SENSITIVE_STEMS)


def mask(value: Any) -> str:
    """Return a non-reversible descriptor of ``value``: digest + length, no content."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if _PLACEHOLDER_RE.match(text):
        return text  # already redacted; do not double-wrap
    digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:8]
    return f"<redacted:sha256={digest},len={len(text)}>"


def redact_obj(node: Any, *, in_headers: bool = False) -> Any:
    """Recursively return a scrubbed copy of a decoded JSON structure.

    ``in_headers`` marks that the current mapping is an HTTP header block, which
    widens matching to the header vocabulary (``cookie``, ``set-cookie``, ...).
    """
    if isinstance(node, dict):
        # HAR 1.2 (and many wire formats) model headers, cookies and query
        # parameters as name/value PAIR objects rather than mappings:
        #   {"name": "Authorization", "value": "Bearer ..."}
        # Key-based matching alone never sees those -- the sensitive token is in
        # the *value* of a key literally called "value" -- so a HAR export would
        # ship credentials in cleartext. Handle the pair shape explicitly.
        name = node.get("name")
        if (
            isinstance(name, str)
            and "value" in node
            and _is_sensitive_key(name, header=True)
        ):
            out_pair = dict(node)
            out_pair["value"] = mask(node["value"])
            return out_pair
        out: dict[Any, Any] = {}
        for key, val in node.items():
            key_str = key if isinstance(key, str) else str(key)
            # A nested "headers" mapping switches its children into header mode.
            child_headers = in_headers or _normalise(key_str) in _HEADER_KEYS
            if _is_sensitive_key(key_str, header=in_headers) and not isinstance(
                val, (dict, list)
            ):
                out[key] = mask(val)
            else:
                out[key] = redact_obj(val, in_headers=child_headers)
        return out
    if isinstance(node, list):
        return [redact_obj(item, in_headers=in_headers) for item in node]
    if isinstance(node, str):
        return _redact_str(node)
    return node


def _redact_str(text: str) -> str:
    """Scrub a string leaf, including any credential material *inside* it.

    A response body arrives as an opaque string, but bodies routinely carry
    credentials: an OAuth token endpoint returns ``access_token`` in its JSON
    body, and many echo/debug endpoints reflect the request's ``Authorization``
    header straight back. Treating a body as an opaque scalar therefore leaks
    exactly the highest-value secrets, so embedded JSON is parsed and scrubbed
    recursively, and raw ``Name: value`` header blocks are caught by regex.
    """
    stripped = text.lstrip()
    if stripped[:1] in {"{", "["}:
        try:
            decoded = json.loads(text)
        except ValueError:
            pass
        else:
            if isinstance(decoded, (dict, list)):
                return json.dumps(redact_obj(decoded), default=str)
    scrubbed = _HEADER_LINE_RE.sub(lambda m: m.group(1) + mask(m.group(3)), text)
    return _QUERY_PARAM_RE.sub(lambda m: m.group(1) + mask(m.group(2)), scrubbed)


def redact_text(payload: str) -> str:
    """Scrub a tool-result payload.

    Parses ``payload`` as JSON when possible (the upstream engine returns JSON
    text) and walks it; otherwise falls back to line/query regex scrubbing so an
    unparseable blob is never passed through untouched.
    """
    if not payload:
        return payload
    try:
        decoded = json.loads(payload)
    except (ValueError, TypeError):
        return _redact_str(payload)
    return json.dumps(redact_obj(decoded), indent=2, default=str)
