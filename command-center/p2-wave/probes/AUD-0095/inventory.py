"""Enumerate the freeze set and record a sha256 per present file."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from contract import CLI_LAUNCHERS, NAMED_REQUIRED, REPO, SKIP_PARTS

VERSION_RE = re.compile(
    r"^(?:__freeze_version__|FREEZE_VERSION)\s*=\s*['\"]([^'\"]+)['\"]",
    re.M,
)


def digest_bytes(raw: bytes) -> tuple[str, int]:
    data = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest(), len(data)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def extract_version(path: Path, raw: bytes | None = None) -> str | None:
    data = path.read_bytes() if raw is None else raw
    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict) and "schema_version" in doc:
            val = doc["schema_version"]
            if isinstance(val, (str, int, float)) and not isinstance(val, bool):
                return str(val)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    m = VERSION_RE.search(text)
    return m.group(1) if m else None


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _row(
    root: Path,
    path: Path,
    cls: str,
    reason: str,
    *,
    required: bool = False,
) -> dict[str, Any]:
    present = path.is_file()
    try:
        rel = _rel(root, path)
    except ValueError:
        rel = path.as_posix().replace("\\", "/")
        if rel.startswith(root.as_posix().rstrip("/") + "/"):
            rel = rel[len(root.as_posix().rstrip("/")) + 1 :]
    row: dict[str, Any] = {
        "path": rel,
        "class": cls,
        "present": present,
        "required_by_spec": required,
        "reason": reason,
        "sha256": None,
        "bytes": None,
        "freeze_version": None,
    }
    if present:
        sha, size = digest_file(path)
        row["sha256"] = sha
        row["bytes"] = size
        row["freeze_version"] = extract_version(path)
    return row


def enumerate_freeze_set(root: Path | None = None) -> dict[str, Any]:
    root = (root or REPO).resolve()
    by_path: dict[str, dict[str, Any]] = {}

    def add(path: Path, cls: str, reason: str, required: bool = False) -> None:
        row = _row(root, path, cls, reason, required=required)
        key = row["path"]
        prev = by_path.get(key)
        if prev is None:
            by_path[key] = row
            return
        if required:
            prev["required_by_spec"] = True
        if reason not in (prev.get("reason") or ""):
            prev["reason"] = f"{prev['reason']}; {reason}"

    schema_dir = root / "command-center" / "schema"
    if schema_dir.is_dir():
        for p in sorted(schema_dir.glob("*.json")):
            if p.is_file():
                add(p, "schema", "command-center/schema (program validation)")

    tools = root / "tools"
    if tools.is_dir():
        for p in sorted(tools.rglob("*.schema.json")):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            if p.is_file():
                add(p, "schema", "tools schema the program validates against")

    if root.is_dir():
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            name = p.name.lower()
            if "dispatch" in name or "launcher" in name or name.startswith("launch"):
                add(p, "launcher-or-dispatcher", "filename match (dispatch/launch)")
            if "PROMPT" in p.name.upper() and p.suffix.lower() in {
                ".md",
                ".txt",
                ".json",
            }:
                add(p, "prompt-template", "filename match (*PROMPT*)")

    seed_stage = root / "command-center" / "p2-wave" / "seed-stage"
    if seed_stage.is_dir():
        for p in sorted(seed_stage.iterdir()):
            if not p.is_file():
                continue
            if p.suffix == ".py":
                add(
                    p,
                    "launcher-or-dispatcher",
                    "p2-wave seed-stage dispatcher/launcher",
                )
            elif p.suffix.lower() in {".yaml", ".yml", ".md"}:
                add(p, "prompt-template", "p2-wave seed-stage template")

    for rel in CLI_LAUNCHERS:
        add(
            root / rel,
            "launcher-or-dispatcher",
            "CLI launcher entry point",
            required=True,
        )

    for rel, cls, why in NAMED_REQUIRED:
        add(root / rel, cls, why, required=True)

    rows = [by_path[k] for k in sorted(by_path)]
    present_rows = [r for r in rows if r["present"]]
    missing_required = [
        r for r in rows if r.get("required_by_spec") and not r["present"]
    ]
    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1
    return {
        "root": str(root),
        "inventory": rows,
        "present_count": len(present_rows),
        "absent_count": len(rows) - len(present_rows),
        "missing_required": [r["path"] for r in missing_required],
        "by_class": by_class,
        "anchor_algo": "sha256(bytes with CRLF normalized to LF)",
    }


def freeze_anchor_map(inventory: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in inventory:
        if not row.get("present"):
            continue
        out[row["path"]] = {
            "sha256": row["sha256"],
            "bytes": row["bytes"],
            "freeze_version": row.get("freeze_version"),
            "class": row["class"],
        }
    return out
