"""Repo vs live capability presence-gap detector. IMP-0401."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _collect(roots: Iterable[Path | str]) -> set[str]:
    found: set[str] = set()
    for root in roots:
        p = Path(root)
        if p.is_file():
            found.add(p.stem if p.suffix else p.name)
            continue
        if not p.is_dir():
            continue
        for child in p.rglob("*"):
            if child.is_file() and child.suffix in {".md", ".json", ".py", ".mdc"}:
                found.add(child.stem)
                found.add(child.parent.name)
    return {n for n in found if n and n not in {"__pycache__", "."}}


def detect(repo_roots, live_roots, index=None) -> dict[str, Any]:
    repo = _collect(repo_roots)
    live = _collect(live_roots)
    indexed: set[str] = set()
    if index:
        path = Path(index)
        if path.is_file():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                doc = {}
            for cap in doc.get("capabilities") or []:
                if isinstance(cap, dict) and cap.get("capability_id"):
                    indexed.add(str(cap["capability_id"]))
                elif isinstance(cap, str):
                    indexed.add(cap)
            for name in doc.get("names") or []:
                indexed.add(str(name))
    def _names(items: set[str]) -> set[str]:
        out = set(items)
        for n in list(items):
            out.add(n)
            out.add(f"skill:{n}")
        return out

    repo_n, live_n = _names(repo), _names(live)
    repo_only = sorted(n for n in (repo_n - live_n) if n.startswith("skill:") or n in repo)
    live_only = sorted(n for n in (live_n - repo_n) if n.startswith("skill:") or n in live)
    both = sorted(n for n in (repo_n & live_n) if n.startswith("skill:") or n in repo)
    overlap_illegal = sorted(set(repo_only) & set(live_only))
    selectable_but_unloadable = sorted(indexed - live)
    return {
        "repo_only": repo_only,
        "live_only": live_only,
        "both": both,
        "disjoint": not overlap_illegal,
        "overlap_illegal": overlap_illegal,
        "indexed": sorted(indexed),
        "selectable_but_unloadable": selectable_but_unloadable,
    }
