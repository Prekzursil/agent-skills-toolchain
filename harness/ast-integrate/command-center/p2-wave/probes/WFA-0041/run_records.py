"""Independent run-record locator.

A benchmark named in prose is not a benchmark that ran. This module only
accepts a locatable, non-empty file (or a sha256 that matches a file).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

_SHA = re.compile(r"\b[a-fA-F0-9]{64}\b")
_PATHISH = re.compile(
    r"(?:[A-Za-z]:[\\/]|/|\./)?[\w./\\-]+\.(?:json|jsonl|txt|log|receipt)"
)


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(str(k))
            parts.append(_as_text(v))
        return " ".join(parts)
    if isinstance(value, list):
        return " ".join(_as_text(v) for v in value)
    return str(value)


def named_paths(value: Any) -> list[str]:
    text = _as_text(value)
    found: list[str] = []
    for m in _PATHISH.finditer(text.replace("\\", "/")):
        p = m.group(0).replace("\\", "/")
        if p not in found:
            found.append(p)
    if isinstance(value, dict):
        for key in (
            "path",
            "run_record",
            "receipt",
            "benchmark",
            "bench",
            "artifact",
            "run_path",
        ):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                found.append(item.replace("\\", "/").strip())
    return found


def named_digests(value: Any) -> list[str]:
    return [m.group(0).lower() for m in _SHA.finditer(_as_text(value))]


def resolve_path(name: str, roots: list[Path]) -> Path | None:
    raw = name.replace("\\", "/").strip()
    if not raw:
        return None
    direct = Path(raw)
    tries = [direct] if direct.is_absolute() else []
    for root in roots:
        tries.append(root / raw)
        tries.append(root / Path(raw).name)
    seen: set[str] = set()
    for p in tries:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except OSError:
            continue
    return None


def locate(claim: Any, roots: list[Path] | None = None) -> dict[str, Any]:
    """Return the first locatable run record for a claim, or none."""
    search = list(roots or [REPO, HERE])
    hits: list[dict[str, Any]] = []
    for name in named_paths(claim):
        path = resolve_path(name, search)
        if path is None:
            continue
        hits.append(
            {
                "named": name,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": digest_file(path),
            }
        )
    want = named_digests(claim)
    if want and not hits:
        for root in search:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.stat().st_size <= 0:
                    continue
                if path.suffix.lower() not in {".json", ".jsonl", ".txt", ".log"}:
                    continue
                got = digest_file(path)
                if got in want:
                    hits.append(
                        {
                            "named": got,
                            "path": str(path),
                            "bytes": path.stat().st_size,
                            "sha256": got,
                        }
                    )
                    break
    if hits:
        return {"found": True, "record": hits[0], "all": hits}
    return {"found": False, "record": None, "all": []}
