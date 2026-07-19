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

from accounts import AccountPolicy, FileSlot

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
    account: AccountPolicy | None = None

    def child_env(self) -> dict[str, str]:
        """Full child environment: inherit os.environ, then layer overrides.

        Inheriting the parent environment is what carries the credentials each
        backend needs (IG_APP_VERSION, FB_COOKIES_PATH, TIKTOK_MS_TOKEN, HTTP
        proxies, ...) without hard-coding any secret here. The hub then layers
        the ACTIVE account's env on top of this at spawn time (see
        ``hub.RuntimeBackend``), so per-account credentials win.
        """
        merged = dict(os.environ)
        merged.update(self.env)
        return merged


# ---- per-account session/cookie file slots (see accounts.FileSlot) ----------
# Social logins are FILE-based, so each backend declares WHERE it reads its
# session/cookie artifact and whether an env var can redirect it (copy-free) or
# it must be copied onto a fixed path. Verified against each backend's source:
#   * insta-mcp  reads  <INSTA_DATA_DIR or repo/data>/session.json   (env: dir)
#   * fb-mcp     reads  <FB_COOKIES_PATH or repo/data/cookies.json>  (env: file)
#   * whatsapp   reads  <repo>/auth_info/ (Baileys), FIXED -> copy-only
_IG_SESSION = FileSlot(
    key="session", dest=f"{REPOS}/insta-mcp/data", env_var="INSTA_DATA_DIR", is_dir=True
)
_FB_COOKIES = FileSlot(
    key="cookies",
    dest=f"{REPOS}/fb-messenger-mcp/data/cookies.json",
    env_var="FB_COOKIES_PATH",
    is_dir=False,
)
_WA_AUTH = FileSlot(
    key="auth", dest=f"{REPOS}/whatsapp-mcp/auth_info", env_var="", is_dir=True
)


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
            # Multi-account: each account points INSTA_DATA_DIR at its own dir
            # (holding session.json); IG_APP_VERSION etc. ride in the env bundle.
            account=AccountPolicy(
                platform="insta", mode="env", label="Instagram", files=(_IG_SESSION,)
            ),
        ),
        BackendSpec(
            id="tiktok",
            label="tiktok-mcp (public scraper)",
            prefix="tt",
            cmd=(TIKTOK_PY, f"{REPOS}/tiktok-mcp/server.py"),
            cache="tiktok.json",
            note="keyless public read; some tools need TIKTOK_PROXY off home IP",
            # Keyless/no session file; accounts just rotate TIKTOK_MS_TOKEN /
            # TIKTOK_PROXY env bundles (no file slot).
            account=AccountPolicy(platform="tiktok", mode="env", label="TikTok"),
        ),
        BackendSpec(
            id="fb",
            label="fb-messenger-mcp (groups/rooms/pages)",
            prefix="fb",
            cmd=(FB_PY, f"{REPOS}/fb-messenger-mcp/server.py"),
            cache="fb-messenger.json",
            # Explicit default cookies path so the backend reads a KNOWN file
            # even when ~/.mcp.json omits FB_COOKIES_PATH (Instagram's dir
            # override is present but this one was not). A per-account 'cookies'
            # file override still wins at respawn via the account layer's
            # active_env, exactly like INSTA_DATA_DIR. Refresh the file with
            # `python fb_session.py` when whoami starts failing.
            env={"FB_COOKIES_PATH": _FB_COOKIES.dest},
            note="needs data/cookies.json; enumerates offline (no startup auth)",
            # Multi-account: each account points FB_COOKIES_PATH at its own
            # cookies.json; FB_PAGE_ACCESS_TOKEN etc. ride in the env bundle.
            account=AccountPolicy(
                platform="fb",
                mode="env",
                label="Facebook Messenger",
                files=(_FB_COOKIES,),
            ),
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
            # Baileys reads a FIXED auth_info/ dir (no env override) -> switching
            # COPIES the active account's auth_info onto that path before respawn.
            account=AccountPolicy(
                platform="wa", mode="env", label="WhatsApp", files=(_WA_AUTH,)
            ),
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
