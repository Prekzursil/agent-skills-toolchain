#!/usr/bin/env python3
"""Hop-by-hop token-location trace derived from the captured MCP authorization spec.

Storage locations are named. Token values are never attached.
"""
from __future__ import annotations

import re
from typing import Any

SPEC_MARKERS = {
    "stdio_exempt": r"STDIO transport \*\*SHOULD NOT\*\*",
    "prm": r"Protected Resource Metadata",
    "rfc9728": r"RFC\s*9728",
    "authorization_servers": r"authorization_servers",
    "www_authenticate": r"WWW-Authenticate",
    "bearer": r"Authorization: Bearer",
    "pkce": r"PKCE",
    "resource_param": r"resource parameter",
    "rfc8707": r"RFC\s*8707",
    "query_forbidden": r"MUST NOT\*\* be included in the URI query string",
}

FLOW_BEATS = [
    "MCP request without token",
    "HTTP 401 Unauthorized with WWW-Authenticate header",
    "Generate PKCE parameters",
    "Redirect to callback with authorization code",
    "Token request + code_verifier + resource",
    "MCP request with access token",
]


def marker_hits(spec_text: str) -> dict[str, bool]:
    return {name: re.search(pat, spec_text) is not None for name, pat in SPEC_MARKERS.items()}


def missing_markers(spec_text: str) -> list[str]:
    return [name for name, ok in marker_hits(spec_text).items() if not ok]


def missing_beats(spec_text: str) -> list[str]:
    return [beat for beat in FLOW_BEATS if beat not in spec_text]


def build_hop_trace(spec_text: str) -> dict[str, Any]:
    missing = missing_markers(spec_text) + [f"beat:{b}" for b in missing_beats(spec_text)]
    hops = [
        {
            "hop": 1,
            "beat": "MCP request without token",
            "token_kind": "none",
            "storage_location": "none",
            "notes": "Unauthenticated probe; no credential exists yet.",
        },
        {
            "hop": 2,
            "beat": "HTTP 401 Unauthorized with WWW-Authenticate header",
            "token_kind": "none",
            "storage_location": "www-authenticate-header-ephemeral",
            "notes": "Carries resource_metadata URL only, not a token.",
        },
        {
            "hop": 3,
            "beat": "GET Protected Resource Metadata (RFC 9728)",
            "token_kind": "none",
            "storage_location": "public-metadata",
            "notes": "authorization_servers is public metadata.",
        },
        {
            "hop": 4,
            "beat": "GET authorization-server metadata (RFC 8414 / OIDC)",
            "token_kind": "none",
            "storage_location": "public-metadata",
            "notes": "token_endpoint and authorization_endpoint are public.",
        },
        {
            "hop": 5,
            "beat": "Client registration (CIMD / DCR / preregistered)",
            "token_kind": "client_id",
            "storage_location": "as-client-registry",
            "notes": (
                "client_id is an identifier. A confidential client_secret, if issued, "
                "stays in the client confidential store and is never copied into this artifact."
            ),
        },
        {
            "hop": 6,
            "beat": "Generate PKCE parameters + resource + scope",
            "token_kind": "code_verifier",
            "storage_location": "client-memory-pkce",
            "notes": "code_challenge is public in the authorize URL; the verifier stays in client memory.",
        },
        {
            "hop": 7,
            "beat": "Resource-owner authentication at the authorization server",
            "token_kind": "user_password_or_session",
            "storage_location": "idp-not-in-client",
            "notes": "User credentials never transit the MCP client or this program's artifacts.",
        },
        {
            "hop": 8,
            "beat": "Redirect to callback with authorization code",
            "token_kind": "authorization_code",
            "storage_location": "redirect-uri-ephemeral",
            "notes": "Short-lived code in the local callback URL; exchanged immediately.",
        },
        {
            "hop": 9,
            "beat": "Token request + code_verifier + resource",
            "token_kind": "access_token+refresh_token",
            "storage_location": "process-memory:TokenStorage",
            "notes": (
                "Python SDK TokenStorage is a Protocol (get_tokens/set_tokens). "
                "Default implementations keep values in process memory. Values are not copied here."
            ),
        },
        {
            "hop": 10,
            "beat": "MCP request with access token",
            "token_kind": "access_token",
            "storage_location": "tls-authorization-header",
            "notes": (
                "Authorization: Bearer <access-token> on every HTTP request. "
                "Spec: access tokens MUST NOT be placed in the URI query string. "
                "The header value is omitted from this artifact."
            ),
        },
        {
            "hop": 11,
            "beat": "Captured research artifact from the flow",
            "token_kind": "none",
            "storage_location": "none",
            "notes": "This JSON names locations only. The credential scan is the control.",
        },
    ]
    return {
        "derived_from": "captured MCP authorization spec markdown (GitHub blob, decoded)",
        "spec_markers_present": marker_hits(spec_text),
        "missing": missing,
        "complete": not missing,
        "hops": hops,
        "stdio_profile": {
            "applies_to_http_profile": False,
            "spec": (
                "Implementations using an STDIO transport SHOULD NOT follow this "
                "authorization specification; they retrieve credentials from the environment."
            ),
            "token_kind": "env-var-value",
            "storage_location": "env-name-only",
            "notes": (
                "Config may name an environment variable. The value must stay in the "
                "process environment, not in .mcp.json or research artifacts."
            ),
        },
    }
