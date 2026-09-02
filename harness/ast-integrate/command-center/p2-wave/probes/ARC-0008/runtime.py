"""One-shot A1 load-then-dispatch harness for ARC-0008.

This is test instrumentation, not a resident runtime. DESIGN.json pins
no_resident_runtime=true and no dispatcher generator. The process starts,
loads MANIFEST-listed files, emits a tool inventory and a log, optionally
dispatches/fires, then exits.

Reachability is NOT file existence:
  * tool inventory is built from loaded bodies, not from a glob
  * dispatch writes a process-visible canary only when the id is loaded
  * hooks attach only when the estate plugin overlay says hooks_enabled
    (test-only plugin.json; not part of A1 DESIGN file_set)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SKILL_ID = "skill.council"
HOOK_ID = "hook.pre-tool"
HOOK_EVENT = "pre-tool"
PLUGIN_REL = "plugin.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def listed_files(root: Path) -> list[str]:
    manifest = _read_json(root / "MANIFEST.json")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("MANIFEST.json.files must be a non-empty list")
    return [str(x).replace("\\", "/") for x in files]


def load_plane(root: Path) -> dict[str, Any]:
    """Load listed files. Unlisted on-disk files are omitted with no A1 error."""
    listed = listed_files(root)
    loaded: list[dict[str, Any]] = []
    errors: list[str] = []
    log: list[str] = []
    seen: set[str] = set()
    log.append(f"LOAD MANIFEST files={len(listed)}")
    for rel in listed:
        path = root / rel
        if not path.is_file():
            errors.append(f"listed-missing:{rel}")
            log.append(f"LOAD-MISS {rel}")
            continue
        try:
            body = _read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"listed-unparseable:{rel}:{type(exc).__name__}")
            log.append(f"LOAD-BAD {rel}")
            continue
        cap_id = str(body.get("id") or "")
        if not cap_id:
            errors.append(f"listed-missing-id:{rel}")
            continue
        if cap_id in seen:
            errors.append(f"duplicate-id-FAIL-CLOSED:{cap_id}")
            return {
                "ok": False,
                "errors": errors,
                "warnings": [],
                "loaded": [],
                "loaded_ids": [],
                "tool_inventory": [],
                "hook_inventory": [],
                "log_lines": log + ["FAIL-CLOSED duplicate-id"],
                "plugin": None,
            }
        seen.add(cap_id)
        loaded.append(body)
        log.append(f"LOAD {cap_id} listed=true kind={body.get('kind')}")

    plugin = _estate_plugin(root, log)
    tool_inventory = [
        str(b.get("id"))
        for b in loaded
        if str(b.get("kind") or "") in {"skill", "workflow_blueprint", "council_preset"}
        and b.get("enabled", True) is True
    ]
    hook_inventory: list[str] = []
    for body in loaded:
        if str(body.get("kind") or "") != "hook":
            continue
        hid = str(body.get("id") or "")
        if (
            plugin.get("installed") is True
            and plugin.get("hooks_enabled") is True
            and body.get("enabled", True) is True
        ):
            hook_inventory.append(hid)
            log.append(f"HOOK-ATTACH {hid}")
        else:
            log.append(
                f"HOOK-SKIP {hid} plugin.installed={plugin.get('installed')} "
                f"plugin.hooks_enabled={plugin.get('hooks_enabled')} "
                f"hook.enabled={body.get('enabled', True)}"
            )

    for cid in tool_inventory:
        log.append(f"INVENTORY {cid} REACHABLE")
    for wanted in (SKILL_ID,):
        if wanted not in tool_inventory:
            log.append(f"INVENTORY {wanted} UNREACHABLE")
    if HOOK_ID not in hook_inventory:
        log.append(f"INVENTORY {HOOK_ID} UNREACHABLE")

    log_path = root / ".loader.log"
    log_path.write_text("\n".join(log) + "\n", encoding="utf-8")
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": [],
        "loaded": loaded,
        "loaded_ids": [str(b.get("id")) for b in loaded],
        "tool_inventory": tool_inventory,
        "hook_inventory": hook_inventory,
        "log_lines": log,
        "log_path": log_path.as_posix(),
        "plugin": plugin,
        "listed_files": listed,
    }


def _estate_plugin(root: Path, log: list[str]) -> dict[str, Any]:
    """Test-only overlay for the estate class 'plugin installed but hooks unloaded'.

    Not an A1 DESIGN file_set entry. Absent file means installed=false.
    """
    path = root / PLUGIN_REL
    if not path.is_file():
        log.append("ESTATE-PLUGIN absent installed=false hooks_enabled=false")
        return {"installed": False, "hooks_enabled": False, "id": None}
    body = _read_json(path)
    plugin = {
        "id": body.get("id"),
        "installed": bool(body.get("installed")),
        "hooks_enabled": bool(body.get("hooks_enabled")),
    }
    log.append(
        f"ESTATE-PLUGIN id={plugin['id']} installed={plugin['installed']} "
        f"hooks_enabled={plugin['hooks_enabled']} (test-only; not A1 DESIGN file_set)"
    )
    return plugin


def _by_id(plane: dict[str, Any], cap_id: str) -> dict[str, Any] | None:
    for body in plane.get("loaded") or []:
        if str(body.get("id")) == cap_id:
            return body
    return None


def dispatch_skill(plane: dict[str, Any], scratch: Path, cap_id: str = SKILL_ID) -> dict[str, Any]:
    """Process-visible effect: write a canary iff the skill is in tool inventory."""
    scratch.mkdir(parents=True, exist_ok=True)
    canary = scratch / f"{cap_id}.fired"
    if canary.exists():
        canary.unlink()
    if cap_id not in (plane.get("tool_inventory") or []):
        plane.setdefault("log_lines", []).append(f"DISPATCH {cap_id} UNREACHABLE")
        _flush_log(plane)
        return {
            "id": cap_id,
            "reachable": False,
            "fired": False,
            "canary": canary.as_posix(),
            "token": None,
            "reason": "not-in-tool-inventory",
        }
    body = _by_id(plane, cap_id) or {}
    token = str(body.get("canary_token") or "")
    payload = {
        "id": cap_id,
        "token": token,
        "effect": "FIRED",
        "kind": "process-visible-effect",
    }
    canary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    plane.setdefault("log_lines", []).append(f"DISPATCH {cap_id} FIRED")
    _flush_log(plane)
    return {
        "id": cap_id,
        "reachable": True,
        "fired": True,
        "canary": canary.as_posix(),
        "token": token,
        "reason": "inventory-and-canary",
    }


def fire_hook(plane: dict[str, Any], scratch: Path, event: str = HOOK_EVENT) -> dict[str, Any]:
    """Process-visible effect: write a hook sentinel iff the hook is attached."""
    scratch.mkdir(parents=True, exist_ok=True)
    canary = scratch / f"{HOOK_ID}.fired"
    if canary.exists():
        canary.unlink()
    attached = HOOK_ID in (plane.get("hook_inventory") or [])
    body = _by_id(plane, HOOK_ID) or {}
    if not attached or str(body.get("event") or "") != event:
        plane.setdefault("log_lines", []).append(f"HOOK-FIRE {HOOK_ID} NOT-FIRED")
        _flush_log(plane)
        return {
            "id": HOOK_ID,
            "reachable": False,
            "fired": False,
            "canary": canary.as_posix(),
            "token": None,
            "reason": "not-in-hook-inventory-or-event-mismatch",
        }
    token = str(body.get("canary_token") or "")
    payload = {
        "id": HOOK_ID,
        "event": event,
        "token": token,
        "effect": "FIRED",
        "kind": "process-visible-effect",
    }
    canary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    plane.setdefault("log_lines", []).append(f"HOOK-FIRE {HOOK_ID} FIRED")
    _flush_log(plane)
    return {
        "id": HOOK_ID,
        "reachable": True,
        "fired": True,
        "canary": canary.as_posix(),
        "token": token,
        "reason": "hook-inventory-and-canary",
    }


def _flush_log(plane: dict[str, Any]) -> None:
    path = plane.get("log_path")
    if not path:
        return
    Path(path).write_text("\n".join(plane.get("log_lines") or []) + "\n", encoding="utf-8")


def canary_fired(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    try:
        body = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return body.get("effect") == "FIRED"


def declaration_files_valid(root: Path) -> tuple[bool, list[str]]:
    """Every declaration JSON parses. Used for anti-tautology.

    Declaration = MANIFEST.json, plugin.json, and capabilities/**. Scratch
    canaries and loader logs are not declarations.
    """
    bad: list[str] = []
    candidates: list[Path] = []
    for name in ("MANIFEST.json", "plugin.json"):
        p = root / name
        if p.is_file():
            candidates.append(p)
    cap = root / "capabilities"
    if cap.is_dir():
        candidates.extend(sorted(cap.rglob("*.json")))
    repo = root / "repo"
    if repo.is_dir():
        candidates.extend(sorted(repo.rglob("*.json")))
    live = root / "live"
    if live.is_dir():
        for name in ("MANIFEST.json", "plugin.json"):
            p = live / name
            if p.is_file():
                candidates.append(p)
        live_cap = live / "capabilities"
        if live_cap.is_dir():
            candidates.extend(sorted(live_cap.rglob("*.json")))
    seen: set[str] = set()
    for p in candidates:
        key = p.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            bad.append(f"{p.as_posix()}:{type(exc).__name__}")
    if not seen:
        return False, ["no-declaration-files"]
    return len(bad) == 0, bad
