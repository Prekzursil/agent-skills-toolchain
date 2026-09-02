"""Isolated throwaway canary profile. Never the owner's live HOME."""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

LONG_DIR_NAME = "L" * 240
KEEP_REL = "owner/notes/keep-me.txt"
SKILL_REL = "owner/skills/user-skill.md"
RESERVED_REL = "owner/reserved/NUL"
CASE_OWNER_REL = "pkg/hooks/Pre-Tool.json"
CASE_PACKAGE_REL = "pkg/hooks/pre-tool.json"
FIFO_REL = "owner/skipped/pipe.fifo"
LONG_REL = f"owner/long/{LONG_DIR_NAME}/payload.bin"
CANARY_MARK = "owner/.canary-profile"


class IsolationError(RuntimeError):
    """Canary HOME resolved to the owner's real profile."""


def owner_home() -> Path:
    return Path.home().resolve()


def assert_isolated(profile: Path) -> dict[str, Any]:
    home = owner_home()
    prof = Path(profile).resolve()
    if prof == home:
        raise IsolationError(
            "canary HOME equals the owner's live profile; refusing to drill"
        )
    env_home = os.environ.get("REL0008_CANARY_HOME", "")
    if env_home:
        env_res = Path(env_home).expanduser().resolve()
        if env_res == home:
            raise IsolationError(
                "REL0008_CANARY_HOME equals the owner's live profile"
            )
    return {
        "profile": str(prof),
        "owner_home": str(home),
        "isolated": True,
        "owner_home_untouched": True,
        "isolation_assertion": (
            "canary profile is a throwaway directory and is not the owner's live HOME; "
            "no read or write targeted the live profile"
        ),
    }


def _write(profile: Path, rel: str, data: bytes) -> Path:
    dest = profile.joinpath(*rel.split("/"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def seed_hostile(profile: Path) -> dict[str, Any]:
    """Seed owner-authored files including the three adversarial names."""
    keep = _write(profile, KEEP_REL, b"owner-keep-me: do not destroy\n")
    _write(profile, SKILL_REL, b"# user-authored skill\nkeep\n")
    _write(profile, CANARY_MARK, b"REL-0008-canary\n")
    long_path = _write(profile, LONG_REL, b"long-path-payload-v1\n")
    reserved = _write(profile, RESERVED_REL, b"reserved-device-named-file\n")
    _write(
        profile,
        CASE_OWNER_REL,
        b'{"owner": true, "case_sibling_of": "pkg/hooks/pre-tool.json"}\n',
    )
    fifo = profile.joinpath(*FIFO_REL.split("/"))
    fifo.parent.mkdir(parents=True, exist_ok=True)
    if fifo.exists():
        fifo.unlink()
    os.mkfifo(fifo, 0o600)
    abs_chars = len(os.fspath(long_path))
    rel_chars = len(LONG_REL)
    if abs_chars < 260 and rel_chars < 260:
        raise RuntimeError(
            f"long path too short abs={abs_chars} rel={rel_chars}"
        )
    return {
        "keep_rel": KEEP_REL,
        "skill_rel": SKILL_REL,
        "reserved_rel": RESERVED_REL,
        "case_owner_rel": CASE_OWNER_REL,
        "case_package_rel": CASE_PACKAGE_REL,
        "fifo_rel": FIFO_REL,
        "long_rel": LONG_REL,
        "long_abs_chars": abs_chars,
        "long_rel_chars": rel_chars,
        "owner_rels": [
            KEEP_REL,
            SKILL_REL,
            CANARY_MARK,
            LONG_REL,
            RESERVED_REL,
            CASE_OWNER_REL,
        ],
        "seeded_abs": {
            "keep": str(keep),
            "reserved": str(reserved),
            "long": str(long_path),
        },
    }


@contextmanager
def fresh_profile() -> Iterator[tuple[Path, dict[str, Any], dict[str, Any]]]:
    """Retry policy: every attempt destroys and recreates the profile."""
    tmp = tempfile.mkdtemp(prefix="rel0008-canary-")
    root = Path(tmp)
    os.environ["REL0008_CANARY_HOME"] = str(root)
    try:
        info = assert_isolated(root)
        seed = seed_hostile(root)
        yield root, info, seed
    finally:
        os.environ.pop("REL0008_CANARY_HOME", None)
        shutil.rmtree(root, ignore_errors=True)
