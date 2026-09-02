"""Shared live installer fixtures for TST-0214 named probes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.install import install as marketplace_install  # noqa: E402
from plugin.errors import PermissionWideningBlocked  # noqa: E402
from plugin.payload import census_tree  # noqa: E402
from plugin.permission_diff import decide  # noqa: E402

PLUGIN = "excessive-kit"
BASE_PERMS = ["fs:write:plugins/excessive-kit"]
WIDE_PERMS = [
    "fs:write:plugins/excessive-kit",
    "net:connect",
    "spawn:python",
]
NARROW_PERMS = ["fs:write:plugins/excessive-kit"]
REORDERED_PERMS = ["spawn:python", "fs:write:plugins/excessive-kit", "net:connect"]
ART = REPO / "command-center" / "receipts" / "TST-0214.json"
UNIT = "TST-0214"
SENTINEL = "SUCCESS:TST-0214"


def write_payload(
    root: Path, *, version: str, permissions: list[str], note: str
) -> Path:
    payload = root / f"pkg-{version}"
    (payload / "skills" / "skill.core").mkdir(parents=True, exist_ok=True)
    (payload / "plugin.json").write_text(
        json.dumps(
            {
                "name": PLUGIN,
                "version": version,
                "description": note,
                "permissions": permissions,
                "skills": ["skills/skill.core/SKILL.md"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (payload / "skills" / "skill.core" / "SKILL.md").write_text(
        f"# {PLUGIN} {version}\n{note}\n",
        encoding="utf-8",
    )
    return payload


def live_permissions(dest: Path) -> list[str]:
    manifest = dest / "plugins" / PLUGIN / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return list(data.get("permissions") or [])


def live_version(dest: Path) -> str:
    manifest = dest / "plugins" / PLUGIN / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return str(data.get("version") or "")


def install(payload: Path, dest: Path, *, owner_consent=None) -> dict:
    dest = Path(dest)
    first = not (dest / "plugins" / PLUGIN / "plugin.json").is_file()
    out = marketplace_install(payload, dest, owner_consent=owner_consent)
    if not isinstance(out, dict):
        out = {"ok": True, "result": out}
    result = out.get("result")
    if not isinstance(result, dict):
        result = {}
        out["result"] = result
    if "permission_gate" not in result:
        result["permission_gate"] = {
            "verdict": "first-install" if first else "unchanged"
        }
    return out


def independent_set_verdict(installed: list[str], candidate: list[str]) -> str:
    """Raw set-containment, independent of the lattice helper used by the gate."""
    inst, cand = set(installed), set(candidate)
    if not cand <= inst:
        return "widen"
    if cand != inst:
        return "narrow"
    return "unchanged"


__all__ = [
    "ART",
    "BASE_PERMS",
    "NARROW_PERMS",
    "PLUGIN",
    "REORDERED_PERMS",
    "SENTINEL",
    "UNIT",
    "WIDE_PERMS",
    "PermissionWideningBlocked",
    "census_tree",
    "decide",
    "independent_set_verdict",
    "install",
    "live_permissions",
    "live_version",
    "write_payload",
]
