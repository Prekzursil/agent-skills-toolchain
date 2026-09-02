"""Disposable-profile fixture for IMP-0474 rollback rehearsal.

The live tree is never touched. A throwaway profile is seeded with:
  * shipped commands present in both N and N-1
  * a command introduced in N (must survive additive rollback)
  * a user-authored command (must survive)
  * a planted user-data file (must survive byte-identical)
  * managed plugin files whose N-1 bytes are restored from the backup
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.rollback_additive import (  # noqa: E402
    RollbackDestroyedProtected,
    rollback,
    sha256_bytes,
)

PLANTED_REL = "user-data/planted-IMP-0474.txt"
PLANTED_BYTES = (
    b"IMP-0474 planted user data; additive rollback must keep these bytes.\n"
)
USER_CMD_REL = "commands/user-authored.md"
USER_CMD_BYTES = b"# user-authored command\nMust survive rollback to N-1.\n"
N_ONLY_CMD_REL = "commands/shipped/new-in-n.md"
N_ONLY_CMD_BYTES = b"# shipped in N only\nAdditive restore must not delete this.\n"
CORE_N = b"# core command\nversion: N\n"
CORE_N1 = b"# core command\nversion: N-1\n"
PLUGIN_N = b'{"name":"fixture-plugin","version":"N"}\n'
PLUGIN_N1 = b'{"name":"fixture-plugin","version":"N-1"}\n'
LIB_N = b"def run():\n    return 'N'\n"
LIB_N1 = b"def run():\n    return 'N-1'\n"


def _write(root: Path, rel: str, data: bytes) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def build_disposable(root: Path) -> dict[str, Any]:
    """Create profile/ (version N + user extras) and backup-n-1/ (managed N-1)."""
    profile = root / "profile"
    backup = root / "backup-n-1"
    _write(profile, "commands/shipped/core.md", CORE_N)
    _write(profile, N_ONLY_CMD_REL, N_ONLY_CMD_BYTES)
    _write(profile, USER_CMD_REL, USER_CMD_BYTES)
    _write(profile, PLANTED_REL, PLANTED_BYTES)
    _write(profile, "user-data/settings.json", b'{"theme":"owner-dark"}\n')
    _write(profile, "plugin/manifest.json", PLUGIN_N)
    _write(profile, "plugin/lib.py", LIB_N)

    _write(backup, "commands/shipped/core.md", CORE_N1)
    _write(backup, "plugin/manifest.json", PLUGIN_N1)
    _write(backup, "plugin/lib.py", LIB_N1)

    planted = profile / PLANTED_REL
    return {
        "profile": profile,
        "backup": backup,
        "planted_rel": PLANTED_REL,
        "planted_sha256": sha256_bytes(PLANTED_BYTES),
        "planted_bytes": len(PLANTED_BYTES),
        "user_cmd_rel": USER_CMD_REL,
        "n_only_cmd_rel": N_ONLY_CMD_REL,
        "protected_must_exist": [
            PLANTED_REL,
            USER_CMD_REL,
            N_ONLY_CMD_REL,
            "user-data/settings.json",
            "commands/shipped/core.md",
        ],
        "managed_restored": [
            "commands/shipped/core.md",
            "plugin/manifest.json",
            "plugin/lib.py",
        ],
        "planted_path": str(planted),
    }


def planted_status(profile: Path) -> dict[str, Any]:
    path = profile / PLANTED_REL
    if not path.is_file():
        return {
            "survived": False,
            "byte_identical": False,
            "present": False,
            "reason": "planted-user-data-absent",
        }
    data = path.read_bytes()
    identical = data == PLANTED_BYTES
    return {
        "survived": identical,
        "byte_identical": identical,
        "present": True,
        "sha256": sha256_bytes(data),
        "expected_sha256": sha256_bytes(PLANTED_BYTES),
        "bytes": len(data),
    }


def managed_restored(profile: Path) -> dict[str, Any]:
    core = (profile / "commands/shipped/core.md").read_bytes()
    manifest = (profile / "plugin/manifest.json").read_bytes()
    lib = (profile / "plugin/lib.py").read_bytes()
    ok = core == CORE_N1 and manifest == PLUGIN_N1 and lib == LIB_N1
    return {
        "ok": ok,
        "core_is_n1": core == CORE_N1,
        "manifest_is_n1": manifest == PLUGIN_N1,
        "lib_is_n1": lib == LIB_N1,
        "core_sha256": sha256_bytes(core) if core else None,
        "expected_core_sha256": sha256_bytes(CORE_N1),
    }


def preservation_holds(report: dict[str, Any], profile: Path) -> bool:
    planted = planted_status(profile)
    diff = report.get("set_difference") or {}
    return bool(diff.get("empty")) and bool(planted.get("survived"))


def rehearse(root: Path, *, mode: str = "additive") -> dict[str, Any]:
    """Build a disposable profile and actually execute rollback.

    A rehearsal that is not executed is NOT-CHECKED. This function always
    calls rollback() against the throwaway tree.
    """
    meta = build_disposable(root)
    profile = meta["profile"]
    backup = meta["backup"]
    try:
        report = rollback(profile, backup, mode=mode, raise_on_loss=False)
        error = None
    except RollbackDestroyedProtected as exc:
        report = exc.report
        error = str(exc)
    planted = planted_status(profile)
    restored = managed_restored(profile) if (profile / "plugin/manifest.json").is_file() else {
        "ok": False,
        "reason": "plugin-manifest-absent",
    }
    holds = preservation_holds(report, profile)
    return {
        **meta,
        "mode": mode,
        "rollback": report,
        "planted": planted,
        "managed_restored": restored,
        "preservation_holds": holds,
        "error": error,
        "rehearsal_executed": True if report.get("rehearsal_executed") else False,
    }
