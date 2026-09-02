"""Discover live event-ledger / basic-memory trees and load fixture stores."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
LEDGER_FIX = FIX / "ledger"
MEMORY_FIX = FIX / "memory"
PINS_FIX = FIX / "pinned-ground-truth.json"

LEDGER_CANDIDATES = [
    Path.home() / ".claude" / "event-ledger",
    Path("/root/.claude/event-ledger"),
    Path("/home/ubuntu/.claude/event-ledger"),
    Path("/mnt/c/Users/Prekzursil/.claude/event-ledger"),
    Path("/mnt/c/Users/Prekzursil/source/ast-integrate/.claude/event-ledger"),
]
MEMORY_CANDIDATES = [
    Path.home() / "basic-memory",
    Path.home() / ".basic-memory",
    Path.home() / ".memory" / "basic-memory",
    Path("/root/basic-memory"),
    Path("/root/.basic-memory"),
    Path("/home/ubuntu/basic-memory"),
    Path("/mnt/c/Users/Prekzursil/basic-memory"),
    Path("/mnt/c/Users/Prekzursil/.basic-memory"),
]
LEDGER_SUFFIXES = {".jsonl", ".json", ".log", ".txt", ".md"}
NOTE_SUFFIXES = {".md", ".markdown", ".txt"}
MAX_FILE_BYTES = 2_000_000


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _existing_dirs(candidates: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_dir():
            out.append(resolved)
    return out


def live_ledger_roots() -> list[Path]:
    extra = []
    for name in ("AUD0065_LEDGER_ROOT", "CLAUDE_EVENT_LEDGER", "EVENT_LEDGER_DIR"):
        p = _env_path(name)
        if p is not None:
            extra.append(p)
    return _existing_dirs(extra + LEDGER_CANDIDATES)


def live_memory_roots() -> list[Path]:
    extra = []
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        extra.append(Path(xdg) / "basic-memory")
    for name in ("AUD0065_MEMORY_ROOT", "BASIC_MEMORY_HOME", "BASIC_MEMORY_DIR"):
        p = _env_path(name)
        if p is not None:
            extra.append(p)
    return _existing_dirs(extra + MEMORY_CANDIDATES)


def _read_text(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_pins() -> list[dict[str, Any]]:
    doc = json.loads(PINS_FIX.read_text(encoding="utf-8"))
    facts = [f for f in (doc.get("facts") or []) if isinstance(f, dict)]
    if len(facts) < 3:
        raise RuntimeError("pinned-ground-truth.json has too few facts")
    return facts


def load_ledger_events(root: Path, origin: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not root.is_dir():
        return events
    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in LEDGER_SUFFIXES
    )
    for path in files:
        text = _read_text(path)
        if text is None:
            continue
        rel = _rel(path) if origin != "live" else str(path)
        if path.suffix.lower() == ".jsonl":
            for i, line in enumerate(text.splitlines(), 1):
                raw = line.strip()
                if not raw:
                    continue
                body = raw
                eid = f"{path.name}:{i}"
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict):
                    eid = str(obj.get("id") or eid)
                    body = str(
                        obj.get("text")
                        or obj.get("body")
                        or obj.get("message")
                        or raw
                    )
                events.append(
                    {
                        "id": f"led:{origin}:{eid}",
                        "path": rel,
                        "origin": origin,
                        "line": i,
                        "text": body,
                        "raw": raw,
                    }
                )
        else:
            events.append(
                {
                    "id": f"led:{origin}:{path.name}",
                    "path": rel,
                    "origin": origin,
                    "line": 1,
                    "text": text,
                    "raw": text,
                }
            )
    return events


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2]
    return meta, body


def load_memory_notes(root: Path, origin: str) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if not root.is_dir():
        return notes
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in NOTE_SUFFIXES
    )
    for path in files:
        text = _read_text(path)
        if text is None:
            continue
        meta, body = _split_frontmatter(text)
        permalink = meta.get("permalink") or f"file://{_rel(path)}"
        title = meta.get("title") or path.stem
        rel = _rel(path) if origin != "live" else str(path)
        notes.append(
            {
                "id": f"mem:{origin}:{path.stem}",
                "path": rel,
                "origin": origin,
                "permalink": permalink,
                "title": title,
                "text": text,
                "body": body,
                "frontmatter": meta,
            }
        )
    return notes


def load_stores() -> dict[str, Any]:
    fixture_ledger = load_ledger_events(LEDGER_FIX, "fixture")
    fixture_memory = load_memory_notes(MEMORY_FIX, "fixture")
    live_led_roots = live_ledger_roots()
    live_mem_roots = live_memory_roots()
    live_ledger: list[dict[str, Any]] = []
    for root in live_led_roots:
        live_ledger.extend(load_ledger_events(root, "live"))
    live_memory: list[dict[str, Any]] = []
    for root in live_mem_roots:
        live_memory.extend(load_memory_notes(root, "live"))
    catalog_ledger = Path.home() / ".claude" / "event-ledger"
    return {
        "pins": load_pins(),
        "fixture_ledger": fixture_ledger,
        "fixture_memory": fixture_memory,
        "live_ledger": live_ledger,
        "live_memory": live_memory,
        "live_ledger_roots": [str(p) for p in live_led_roots],
        "live_memory_roots": [str(p) for p in live_mem_roots],
        "catalog_ledger_path": str(catalog_ledger),
        "catalog_ledger_exists": catalog_ledger.is_dir(),
        "ledger_all": fixture_ledger + live_ledger,
        "memory_all": fixture_memory + live_memory,
    }
