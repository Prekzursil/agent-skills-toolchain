"""A1 config-first loader implementing DESIGN.json precedence.unlisted_file.

A file absent from MANIFEST.json is not loaded, even if it sits in a
capabilities directory. The skip is silent: no error, no warning, no
FAIL-CLOSED. Duplicate-in-one-file is FAIL-CLOSED (DESIGN contrast).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def listed_files(root: Path) -> list[str]:
    manifest = _read_json(root / "MANIFEST.json")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("MANIFEST.json.files must be a non-empty list")
    return [str(x).replace("\\", "/") for x in files]


def disk_capability_files(root: Path) -> list[str]:
    cap = root / "capabilities"
    if not cap.is_dir():
        return []
    out: list[str] = []
    for p in sorted(cap.rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out


def load_a1(root: Path) -> dict[str, Any]:
    """Load only MANIFEST-listed files. Unlisted on-disk files are dropped silently."""
    listed = listed_files(root)
    loaded: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for rel in listed:
        path = root / rel
        if not path.is_file():
            errors.append(f"listed-missing:{rel}")
            continue
        try:
            body = _read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"listed-unparseable:{rel}:{type(exc).__name__}")
            continue
        cap_id = str(body.get("id") or "")
        if not cap_id:
            errors.append(f"listed-missing-id:{rel}")
            continue
        if cap_id in seen_ids:
            errors.append(f"duplicate-id-FAIL-CLOSED:{cap_id}")
            return {
                "ok": False,
                "errors": errors,
                "loaded_ids": [],
                "unlisted_on_disk": [],
                "silent_omission_ids": [],
                "warnings": [],
            }
        seen_ids.add(cap_id)
        loaded.append(body)

    on_disk = disk_capability_files(root)
    unlisted = [rel for rel in on_disk if rel not in listed]
    silent_ids: list[str] = []
    for rel in unlisted:
        try:
            body = _read_json(root / rel)
            cid = str(body.get("id") or rel)
        except (OSError, json.JSONDecodeError):
            cid = rel
        silent_ids.append(cid)

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": [],
        "loaded_ids": [str(x.get("id")) for x in loaded],
        "loaded": loaded,
        "unlisted_on_disk": unlisted,
        "silent_omission_ids": silent_ids,
        "listed_files": listed,
    }
