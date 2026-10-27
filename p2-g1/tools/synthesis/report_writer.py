"""Write a completion report over a gated manifest (SYN-0019)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_completion_report(
    root: Path | str,
    manifest: list[dict[str, Any]] | dict[str, Any] | None = None,
    name: str = "completion-report.json",
    **kwargs: Any,
) -> Path:
    dest = Path(root) / name
    entries = manifest if isinstance(manifest, list) else (manifest or {}).get("entries") or []
    report = {
        "kind": "completion-report",
        "entry_count": len(entries),
        "entries": entries,
        "ok": True,
        **{k: v for k, v in kwargs.items() if k not in {"root", "manifest", "name"}},
    }
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return dest
