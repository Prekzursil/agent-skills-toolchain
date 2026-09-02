#!/usr/bin/env python3
"""Client-implementation matrix from captured SDK/inspector source (not from memory)."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"

CHECKS = {
    "pkce": ("PKCE", "code_challenge", "code_verifier"),
    "resource_indicator": ("resource", "RFC 8707", "rfc8707"),
    "prm_discovery": (
        "Protected Resource Metadata",
        "oauth-protected-resource",
        "discoverOAuthProtectedResourceMetadata",
        "www-authenticate",
        "WWW-Authenticate",
        "resource_metadata",
    ),
    "bearer_header": ("Authorization", "Bearer"),
    "token_storage": ("TokenStorage", "tokens", "set_tokens", "saveTokens"),
}


def _read(name: str) -> str:
    path = CAPTURES / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _hits(text: str) -> dict[str, bool]:
    low = text
    return {key: any(tok in low for tok in toks) for key, toks in CHECKS.items()}


def client_matrix() -> dict:
    py = _read("python-oauth2.py")
    ts = _read("ts-auth.ts")
    insp = _read("inspector-cliOAuth.ts")
    py_docs = _read("python-oauth-clients.md")
    ts_docs = _read("ts-oauth.md")
    insp_docs = _read("inspector-README.md")

    def row(name, source_file, text, prose_file, prose, closed_source=False):
        h = _hits(text)
        full = all(
            [
                h["pkce"],
                h["prm_discovery"] or h["resource_indicator"],
                h["bearer_header"] or h["token_storage"],
            ]
        )
        if closed_source:
            verdict = "UNVERIFIED-FROM-SOURCE"
            full = False
        elif not text:
            verdict = "SOURCE-CAPTURE-MISSING"
            full = False
        elif full:
            verdict = "FULL-HTTP-OAUTH-PROFILE-IN-SOURCE"
        else:
            verdict = "PARTIAL-OR-ABSENT"
        return {
            "client": name,
            "source_file": source_file,
            "prose_file": prose_file,
            "source_bytes": len(text),
            "prose_bytes": len(prose),
            "checks": h,
            "full_flow_in_source": full,
            "verdict": verdict,
        }

    return {
        "method": (
            "Grep of captured SDK/inspector source for PKCE, PRM/resource, and "
            "Authorization/TokenStorage. Closed-source hosts are not inferred."
        ),
        "rows": [
            row(
                "python-sdk OAuthClientProvider",
                "captures/python-oauth2.py",
                py,
                "captures/python-oauth-clients.md",
                py_docs,
            ),
            row(
                "typescript-sdk auth.ts",
                "captures/ts-auth.ts",
                ts,
                "captures/ts-oauth.md",
                ts_docs,
            ),
            row(
                "MCP Inspector CLI",
                "captures/inspector-cliOAuth.ts",
                insp,
                "captures/inspector-README.md",
                insp_docs,
            ),
            {
                "client": "this program (ast-integrate worktree)",
                "source_file": "tools/ (census)",
                "prose_file": None,
                "full_flow_in_source": False,
                "verdict": "NO-HTTP-OAUTH-MCP-CLIENT-IN-TOOLS",
                "notes": (
                    "Measured STDIO .mcp.json surface (IMP-0048). Spec: STDIO SHOULD NOT "
                    "follow the HTTP OAuth profile; credentials come from the environment."
                ),
            },
            {
                "client": "Claude Desktop / Cursor / VS Code Copilot (host apps)",
                "source_file": None,
                "full_flow_in_source": False,
                "verdict": "UNVERIFIED-FROM-SOURCE",
                "notes": (
                    "Closed-source or not fetched this run. Not counted as implementing "
                    "the full flow."
                ),
            },
        ],
    }
