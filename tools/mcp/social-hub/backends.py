#!/usr/bin/env python3
"""Backend registry for the social-hub MCP multiplexer.

Each entry describes ONE fronted social MCP server: its short id, the collision
prefix used *only* when a tool name clashes across backends, the exact stdio
launch argv (mirrored from ~/.mcp.json / the repos), the per-backend tool-cache
filename, and any environment overrides layered on top of the inherited
``os.environ`` (so session files, cookies, IG_APP_VERSION and proxies pass
through automatically).

Keeping this as plain data (a frozen dataclass list) makes the planner in
``registry.py`` trivially unit-testable without touching the filesystem or
spawning a single child process.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

# Repo roots (mirrors the exact commands registered in ~/.mcp.json).
REPOS = "C:/Users/Prekzursil/source/repos"
TOOLCHAIN = "C:/Users/Prekzursil/source/agent-skills-toolchain"

# Interpreters. The venv pythons are per-backend; node is on PATH.
TIKTOK_PY = f"{REPOS}/tiktok-mcp/.venv/Scripts/python.exe"
FB_PY = f"{REPOS}/fb-messenger-mcp/.venv/Scripts/python.exe"


@dataclass(frozen=True)
class BackendSpec:
    """Immutable description of one fronted MCP backend."""

    id: str
    label: str
    prefix: str
    cmd: tuple[str, ...]
    cache: str
    env: Mapping[str, str] = field(default_factory=dict)
    can_enumerate_offline: bool = True
    note: str = ""

    def child_env(self) -> dict[str, str]:
        """Full child environment: inherit os.environ, then layer overrides.

        Inheriting the parent environment is what carries the credentials each
        backend needs (IG_APP_VERSION, FB_COOKIES_PATH, TIKTOK_MS_TOKEN, HTTP
        proxies, ...) without hard-coding any secret here.
        """
        merged = dict(os.environ)
        merged.update(self.env)
        return merged


def default_backends() -> list[BackendSpec]:
    """The five social backends fronted by the hub (order = merge order)."""
    return [
        BackendSpec(
            id="insta",
            label="insta-mcp (Instagram)",
            prefix="ig",
            cmd=("node", f"{REPOS}/insta-mcp/dist/index.js"),
            cache="insta.json",
            # Authenticates against Instagram at startup, so it cannot answer
            # tools/list unless the saved session is valid -> ship a static
            # fallback cache; --refresh upgrades it to live schemas when logged in.
            can_enumerate_offline=False,
            note="needs data/session.json + IG_APP_VERSION; auths at startup",
        ),
        BackendSpec(
            id="tiktok",
            label="tiktok-mcp (public scraper)",
            prefix="tt",
            cmd=(TIKTOK_PY, f"{REPOS}/tiktok-mcp/server.py"),
            cache="tiktok.json",
            note="keyless public read; some tools need TIKTOK_PROXY off home IP",
        ),
        BackendSpec(
            id="fb",
            label="fb-messenger-mcp (groups/rooms/pages)",
            prefix="fb",
            cmd=(FB_PY, f"{REPOS}/fb-messenger-mcp/server.py"),
            cache="fb-messenger.json",
            note="needs data/cookies.json; enumerates offline (no startup auth)",
        ),
        BackendSpec(
            id="wa",
            label="whatsapp-mcp (Baileys, parked POC)",
            prefix="wa",
            # Node 24 can strip TS types, but the server connects to WhatsApp
            # (QR) at startup before serving MCP -> it cannot enumerate offline
            # and must fail gracefully.
            cmd=("node", f"{REPOS}/whatsapp-mcp/src/main.ts"),
            cache="whatsapp.json",
            can_enumerate_offline=False,
            note="parked POC; QR pairing at startup; degrades to a clear error",
        ),
        BackendSpec(
            id="fbreels",
            label="fb-reels-uploader (Playwright)",
            prefix="fbr",
            cmd=("node", f"{TOOLCHAIN}/tools/mcp/fb-reels-uploader/fb-reels-mcp.mjs"),
            cache="fb-reels.json",
            note="wraps the Reels upload CLI; persistent FB profile pre-auth once",
        ),
    ]
