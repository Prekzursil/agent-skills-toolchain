"""Place payload files from a projection map into dest_root."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def place_payload_files(dest_root: Path, projection_map: Any, payload_path: Path) -> list[str]:
    dest_root = Path(dest_root)
    payload_path = Path(payload_path)
    dest_root.mkdir(parents=True, exist_ok=True)
    if isinstance(projection_map, dict):
        entries = projection_map.get("entries") or []
    else:
        entries = list(projection_map or [])
    placed: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        dest = str(entry.get("dest") or "")
        if not source or not dest:
            continue
        src = payload_path / source
        out = (dest_root / dest).resolve()
        root = dest_root.resolve()
        try:
            out.relative_to(root)
        except ValueError as exc:
            from plugin.errors import ProjectionError

            raise ProjectionError(f"projection dest escapes dest_root: {dest}") from exc
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src.read_bytes())
        placed.append(dest.replace("\\", "/"))
    return placed
