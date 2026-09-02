"""Throwaway canary profile. Never the owner's login HOME."""
from __future__ import annotations

import os
import pwd
import shutil
import tempfile
from pathlib import Path

MARKER = ".rel0022-canary"
OWNER_FILE = "owner-authored.txt"
OWNER_BYTES = "OWNER-UNIQUE-BYTES-REL0022\n"
SETTINGS = "settings.json"


class IsolationError(RuntimeError):
    pass


def login_home() -> Path:
    return Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()


def assert_isolated(home: Path) -> None:
    home = Path(home).resolve()
    real = login_home()
    if home == real:
        raise IsolationError(f"canary HOME equals login home: {real}")
    if real in home.parents and not str(home).startswith("/tmp/"):
        raise IsolationError(f"canary HOME sits under login home: {home}")
    marker = home / MARKER
    if not marker.is_file():
        raise IsolationError(f"missing canary marker {marker}")
    env_home = Path(os.environ.get("HOME", "")).expanduser().resolve()
    if env_home != home:
        raise IsolationError(f"$HOME={env_home} is not canary {home}")


def create() -> Path:
    root = Path(tempfile.mkdtemp(prefix="rel0022-canary-", dir="/tmp"))
    (root / MARKER).write_text("rel-0022-canary\n", encoding="utf-8")
    (root / OWNER_FILE).write_text(OWNER_BYTES, encoding="utf-8")
    (root / SETTINGS).write_text('{"owner.theme": "dark"}\n', encoding="utf-8")
    return root


def destroy(home: Path) -> None:
    home = Path(home).resolve()
    if home == login_home():
        raise IsolationError("refusing to destroy login home")
    if not (home / MARKER).is_file():
        raise IsolationError(f"refusing to destroy unmarked path {home}")
    shutil.rmtree(home, ignore_errors=True)


def env_for(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(Path(home).resolve())
    env["USERPROFILE"] = env["HOME"]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONHOME", None)
    return env
