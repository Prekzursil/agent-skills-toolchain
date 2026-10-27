"""Capability tombstones, redirects, and cycle detection."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

RESOLVED = "RESOLVED"
CYCLE = "CYCLE"
DEAD = "DEAD"
LIVE = "LIVE"


class DeadSelectionError(Exception):
    pass


@dataclass(frozen=True)
class Root:
    name: str
    path: Path
    kind: str


@dataclass
class Capability:
    capability_id: str
    path: Path
    kind: str


@dataclass
class Tombstone:
    old_id: str
    new_id: str | None
    path: Path


@dataclass
class ResolveResult:
    status: str
    terminal_id: str | None
    defect: str | None = None
    hops: list[str] | None = None


def default_roots(*, repo: Path, home: Path | None = None) -> list[Root]:
    home = home or Path.home()
    cands = [
        Root("repo-skills", repo / "skills", "skill"),
        Root("agents-skills", repo / ".agents" / "skills", "skill"),
        Root("claude-skills", home / ".claude" / "skills", "skill"),
    ]
    return cands


def _skill_id(path: Path) -> str:
    name = path.parent.name if path.name.upper() == "SKILL.MD" else path.stem
    if name.startswith("skill."):
        return name
    return "skill." + name


def _read_front(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, Any] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("tombstone", "redirect", "replaced-by", "superseded-by"):
        if key in meta:
            meta["new_id"] = meta[key]
    return meta


def discover(roots: Iterable[Root], *, repo: Path | None = None) -> tuple[list[Capability], list[Tombstone]]:
    live: list[Capability] = []
    tombs: list[Tombstone] = []
    for root in roots:
        base = Path(root.path)
        if not base.is_dir():
            continue
        table = base / "tombstones.json"
        if table.is_file():
            doc = json.loads(table.read_text(encoding="utf-8"))
            rows = doc if isinstance(doc, list) else doc.get("tombstones") or doc.get("redirects") or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                old = str(row.get("old_id") or row.get("from") or "")
                new = row.get("new_id") or row.get("to")
                if old:
                    tombs.append(Tombstone(old_id=old, new_id=str(new) if new else None, path=table))
        for md in base.rglob("SKILL.md"):
            meta = _read_front(md)
            cid = str(meta.get("id") or _skill_id(md))
            new_id = meta.get("new_id") or meta.get("redirect")
            if meta.get("tombstone") in {True, "true", "yes"} or new_id:
                tombs.append(Tombstone(old_id=cid, new_id=str(new_id) if new_id else None, path=md))
            else:
                live.append(Capability(capability_id=cid, path=md, kind=root.kind))
    return live, tombs


def index_from_records(live: list[Capability], tombs: list[Tombstone]) -> tuple[set[str], dict[str, str | None]]:
    live_ids = {c.capability_id for c in live}
    by_old: dict[str, str | None] = {}
    for t in tombs:
        by_old[t.old_id] = t.new_id
    return live_ids, by_old


def is_tombstone(cid: str, by_old: dict[str, str | None]) -> bool:
    return cid in by_old


def resolve(cid: str, live_ids: set[str], by_old: dict[str, str | None]) -> ResolveResult:
    hops = [cid]
    cur = cid
    seen: set[str] = set()
    while cur in by_old:
        if cur in seen:
            return ResolveResult(status=CYCLE, terminal_id=None, defect="tombstone-cycle", hops=hops)
        seen.add(cur)
        nxt = by_old[cur]
        if not nxt:
            return ResolveResult(status=DEAD, terminal_id=None, defect="missing-target", hops=hops)
        hops.append(nxt)
        cur = nxt
    if cur in live_ids:
        status = RESOLVED if cid in by_old else LIVE
        return ResolveResult(status=status, terminal_id=cur, defect=None, hops=hops)
    if cid in by_old:
        return ResolveResult(status=DEAD, terminal_id=None, defect="missing-target", hops=hops)
    return ResolveResult(status=DEAD, terminal_id=None, defect="missing-target", hops=hops)


def route_selection(cid: str, live_ids: set[str], by_old: dict[str, str | None]) -> str:
    result = resolve(cid, live_ids, by_old)
    if result.status in {CYCLE, DEAD} or not result.terminal_id:
        raise DeadSelectionError(f"{cid} {result.status} {result.defect}")
    return result.terminal_id


def tombstone_table(live: list[Capability], tombs: list[Tombstone]) -> list[dict[str, Any]]:
    live_ids, by_old = index_from_records(live, tombs)
    rows = []
    for t in tombs:
        result = resolve(t.old_id, live_ids, by_old)
        rows.append(
            {
                "old_id": t.old_id,
                "new_id": t.new_id,
                "resolution": result.status,
                "terminal_id": result.terminal_id,
                "defect": result.defect,
                "hops": result.hops,
            }
        )
    return rows


def scan_roots(*, repo: Path, home: Path | None = None) -> dict[str, Any]:
    roots = default_roots(repo=repo, home=home)
    live, tombs = discover(roots, repo=repo)
    table = tombstone_table(live, tombs)
    root_rows = [{"name": r.name, "path": str(r.path), "exists": r.path.is_dir()} for r in roots]
    return {
        "roots": root_rows,
        "live_count": len(live),
        "redirect_tombstone_count": sum(1 for r in table if r.get("new_id")),
        "tombstone_table": table,
    }
