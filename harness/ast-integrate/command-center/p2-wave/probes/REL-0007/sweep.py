"""Orphan sweep: query each registration surface; never infer from a missing payload dir."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from surfaces import (
    CHECKED_SURFACE_IDS,
    DETECTOR_HOOK_ID,
    INPUT_SURFACES,
    NOT_CHECKED_SURFACES,
    PACKAGE_HOOK_ID,
    PACKAGE_ID,
    PACKAGE_MIRROR,
    PACKAGE_SETTING,
    PACKAGE_SHIM,
    PACKAGE_SKILL,
    PACKAGE_TASK,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INV_PATH = "an inverse may never remove a path the installer did not create"
INV_PREDATE = (
    "an inverse may never remove a command, skill or setting that pre-dated "
    "the install"
)


class DetectorBlind(RuntimeError):
    """Zeros are untrusted because a known-present registration was not found."""


def _read_json(path: Path) -> tuple[str, Any | None]:
    if not path.is_file():
        return "absent", None
    try:
        return "ok", json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"parse-error:{exc.__class__.__name__}", None
    except OSError as exc:
        return f"io-error:{exc.__class__.__name__}", None


def _row(sid: str, query: str, status: str, orphans: list, reason: str | None = None) -> dict:
    rec: dict[str, Any] = {
        "id": sid,
        "query": query,
        "status": status,
        "orphans": orphans,
    }
    if reason:
        rec["reason"] = reason
    return rec


def query_checked(root: Path) -> list[dict]:
    rows: list[dict] = []

    q = f"read {root.as_posix()}/hooks.json ; select hooks[i].id containing {PACKAGE_ID}"
    st, data = _read_json(root / "hooks.json")
    if st != "ok":
        rows.append(_row("hooks", q, "NOT-CHECKED", [], f"hooks.json {st}"))
    else:
        hits = [h.get("id") for h in (data or {}).get("hooks") or [] if PACKAGE_ID in str(h.get("id"))]
        rows.append(_row("hooks", q, "CHECKED", hits))

    q = f"read {root.as_posix()}/.mcp.json ; select mcpServers keys containing {PACKAGE_ID}"
    st, data = _read_json(root / ".mcp.json")
    if st != "ok":
        rows.append(_row("mcp", q, "NOT-CHECKED", [], f".mcp.json {st}"))
    else:
        hits = [k for k in ((data or {}).get("mcpServers") or {}) if PACKAGE_ID in str(k)]
        rows.append(_row("mcp", q, "CHECKED", hits))

    q = (
        f"read {root.as_posix()}/settings.json ; select key {PACKAGE_SETTING} "
        f"and enabledPlugins[{PACKAGE_ID}]"
    )
    st, data = _read_json(root / "settings.json")
    if st != "ok":
        rows.append(_row("settings", q, "NOT-CHECKED", [], f"settings.json {st}"))
    else:
        hits = []
        if PACKAGE_SETTING in (data or {}):
            hits.append(PACKAGE_SETTING)
        plugins = (data or {}).get("enabledPlugins") or {}
        if PACKAGE_ID in plugins:
            hits.append(f"enabledPlugins.{PACKAGE_ID}")
        rows.append(_row("settings", q, "CHECKED", hits))

    skill_dir = root / "skills" / PACKAGE_SKILL
    q = f"stat {skill_dir.as_posix()} (live skill tree entry {PACKAGE_SKILL})"
    if skill_dir.is_dir() and any(skill_dir.iterdir()):
        rows.append(_row("live_skill_tree", q, "CHECKED", [PACKAGE_SKILL]))
    else:
        rows.append(_row("live_skill_tree", q, "CHECKED", []))

    shim = root / "bin" / PACKAGE_SHIM
    path_env = root / "path.env"
    q = f"stat {shim.as_posix()} and read {path_env.as_posix()} for fixture PATH"
    hits = []
    if shim.is_file():
        hits.append(PACKAGE_SHIM)
    rows.append(_row("path_shim", q, "CHECKED", hits))

    q = f"read {root.as_posix()}/mirror/index.json ; select entries[i].id == {PACKAGE_MIRROR}"
    st, data = _read_json(root / "mirror" / "index.json")
    if st != "ok":
        rows.append(_row("mirror", q, "NOT-CHECKED", [], f"mirror/index.json {st}"))
    else:
        hits = [e.get("id") for e in (data or {}).get("entries") or [] if e.get("id") == PACKAGE_MIRROR]
        rows.append(_row("mirror", q, "CHECKED", hits))

    q = f"read {root.as_posix()}/scheduled-tasks.json ; select tasks[i].name == {PACKAGE_TASK}"
    st, data = _read_json(root / "scheduled-tasks.json")
    if st != "ok":
        rows.append(
            _row("scheduled_tasks_fixture", q, "NOT-CHECKED", [], f"scheduled-tasks.json {st}")
        )
    else:
        hits = [t.get("name") for t in (data or {}).get("tasks") or [] if t.get("name") == PACKAGE_TASK]
        rows.append(_row("scheduled_tasks_fixture", q, "CHECKED", hits))

    return rows


def not_checked_rows() -> list[dict]:
    return [
        _row(s["id"], s["query"], "NOT-CHECKED", [], s["reason"]) for s in NOT_CHECKED_SURFACES
    ]


def query_rel0002() -> dict:
    """REL-0002 is an input (typed inverses), not a package registration surface."""
    meta = INPUT_SURFACES[0]
    rel = "command-center/receipts/REL-0002.json"
    path = REPO / rel
    q = meta["query"]
    if not path.is_file():
        return _row(meta["id"], q, "NOT-CHECKED", [], meta["reason"])
    try:
        text = path.read_text(encoding="utf-8")
        json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _row(
            meta["id"],
            q,
            "NOT-CHECKED",
            [],
            f"REL-0002 receipt unreadable: {type(exc).__name__}",
        )
    missing = []
    hay = text.lower()
    if INV_PATH.lower() not in hay:
        missing.append("INV-PATH")
    if INV_PREDATE.lower() not in hay:
        missing.append("INV-PREDATE")
    if missing:
        return _row(
            meta["id"],
            q,
            "NOT-CHECKED",
            [],
            f"REL-0002 receipt present but missing invariant text: {missing}",
        )
    return _row(meta["id"], q, "CHECKED", [])


def payload_present(root: Path) -> bool:
    return (root / "opt" / PACKAGE_ID).exists()


def sweep(root: Path, *, require_detector: bool = False) -> dict:
    """Query every enumerated surface. Payload absence is recorded, never the verdict."""
    checked = query_checked(root)
    input_rows = [query_rel0002()]
    skipped = not_checked_rows()
    enumerated = checked + input_rows + skipped
    orphans = []
    for row in checked:
        if row["status"] == "CHECKED":
            orphans.extend(row["orphans"])
    detector_hits = [o for o in orphans if o == DETECTOR_HOOK_ID or o == PACKAGE_HOOK_ID]
    nc_rows = [r for r in input_rows + skipped if r["status"] == "NOT-CHECKED"]
    result = {
        "package_id": PACKAGE_ID,
        "payload_present": payload_present(root),
        "payload_used_as_orphan_verdict": False,
        "enumerated": enumerated,
        "checked_surface_ids": [r["id"] for r in checked],
        "not_checked": [
            {"id": r["id"], "reason": r.get("reason", ""), "query": r["query"]} for r in nc_rows
        ],
        "orphan_ids": orphans,
        "orphan_count": len(orphans),
        "zero_orphans_on_checked_surfaces": len(orphans) == 0,
        "detector_hits": detector_hits,
        "required_checked_ids": list(CHECKED_SURFACE_IDS),
    }
    if require_detector:
        if DETECTOR_HOOK_ID not in orphans and PACKAGE_HOOK_ID not in orphans:
            raise DetectorBlind(
                "known-present registration not found; refusing to trust a zero-orphan result"
            )
        result["detector_control"] = {"required": True, "found": True}
    return result


def trusted_zero_sweep(root: Path, profile_mod) -> dict:
    """Plant a known hook, require the sweep to see it, remove it, then sweep for zeros."""
    profile_mod.plant_detector_hook(root)
    seen = sweep(root, require_detector=True)
    profile_mod.unplant_detector_hook(root)
    final = sweep(root, require_detector=False)
    final["detector_control"] = {
        "required": True,
        "planted": DETECTOR_HOOK_ID,
        "found_before_zero": True,
        "planted_orphan_ids": seen["orphan_ids"],
        "zeros_trusted": True,
    }
    return final


def liar_payload_dir_as_zero(root: Path) -> dict:
    """Forbidden inference: missing payload directory => no orphans."""
    return {
        "payload_present": payload_present(root),
        "payload_used_as_orphan_verdict": True,
        "orphan_count": 0 if not payload_present(root) else 1,
        "zero_orphans_on_checked_surfaces": not payload_present(root),
        "lie": "inferred emptiness from missing install directory",
    }
