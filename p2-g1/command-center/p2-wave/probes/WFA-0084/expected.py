#!/usr/bin/env python3
"""Independent expected-set computer for WFA-0084.

Walks the four fixture files with its own loaders. Must not import query.py:
an interface that agrees with itself is not evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Import of query.py is forbidden. Probe 1 greps this file for that import.


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon_pair(a: str, b: str) -> str:
    x, y = sorted((str(a), str(b)))
    return f"{x}::{y}"


def load_records(corpus_dir: Path) -> dict[str, dict[str, Any]]:
    doc = _read(Path(corpus_dir) / "registry.json")
    table: dict[str, dict[str, Any]] = {}
    for row in doc["records"]:
        table[str(row["id"])] = row
    return table


def load_licence_map(corpus_dir: Path) -> dict[str, str]:
    nested = _read(Path(corpus_dir) / "provenance.json")["graph"]
    licence_nodes = {
        str(n["id"]): str(n["licence_class"])
        for n in nested["nodes"]
        if n.get("kind") == "licence_class"
    }
    mapping: dict[str, str] = {}
    for hop in nested["edges"]:
        if hop.get("rel") != "has_licence":
            continue
        klass = licence_nodes.get(str(hop["dst"]))
        if klass:
            mapping[str(hop["src"])] = klass
    return mapping


def load_conflict_pairs(corpus_dir: Path) -> set[str]:
    doc = _read(Path(corpus_dir) / "components.json")
    found: set[str] = set()
    for hop in doc["links"]:
        if hop.get("kind") != "conflicts-with":
            continue
        found.add(_canon_pair(str(hop["from"]), str(hop["to"])))
    return found


def load_compat_pairs(corpus_dir: Path) -> set[str]:
    doc = _read(Path(corpus_dir) / "compat.json")
    found: set[str] = set()
    for left, right in doc["declared_compat"]:
        found.add(_canon_pair(str(left), str(right)))
    return found


def ids_for(corpus_dir: Path, query_type: str, selector: str) -> list[str]:
    records = load_records(corpus_dir)
    if query_type == "disposition":
        return sorted(
            rid for rid, row in records.items() if row.get("disposition") == selector
        )
    if query_type == "family":
        return sorted(rid for rid, row in records.items() if row.get("family") == selector)
    if query_type == "mechanism":
        return sorted(
            rid
            for rid, row in records.items()
            if selector in [str(m) for m in row.get("mechanisms") or []]
        )
    if query_type == "licence_class":
        licences = load_licence_map(corpus_dir)
        return sorted(rid for rid, klass in licences.items() if klass == selector)
    if query_type == "task_class":
        return sorted(
            rid for rid, row in records.items() if row.get("task_class") == selector
        )
    if query_type == "fusibility":
        if selector == "fusible":
            return sorted(fusible_pairs(corpus_dir))
        if selector in {"incompatible", "conflicted"}:
            return sorted(incompatible_pairs(corpus_dir))
        partners = []
        for pk in fusible_pairs(corpus_dir):
            a, b = pk.split("::", 1)
            if a == selector:
                partners.append(b)
            elif b == selector:
                partners.append(a)
        return sorted(partners)
    raise ValueError(f"unknown query type {query_type!r}")


def fusible_pairs(corpus_dir: Path) -> set[str]:
    records = load_records(corpus_dir)
    conflicts = load_conflict_pairs(corpus_dir)
    out: set[str] = set()
    for pk in load_compat_pairs(corpus_dir):
        a, b = pk.split("::", 1)
        left = {str(m) for m in (records[a].get("mechanisms") or [])}
        right = {str(m) for m in (records[b].get("mechanisms") or [])}
        clash = False
        for m1 in left:
            for m2 in right:
                if m1 != m2 and _canon_pair(m1, m2) in conflicts:
                    clash = True
        if not clash:
            out.add(pk)
    return out


def incompatible_pairs(corpus_dir: Path) -> set[str]:
    return load_compat_pairs(corpus_dir) - fusible_pairs(corpus_dir)


CASES: list[tuple[str, str]] = [
    ("disposition", "ADOPT-AS-IS"),
    ("disposition", "DISTILL"),
    ("disposition", "RETIRE"),
    ("disposition", "UNKNOWN-NEEDS-PROBE"),
    ("disposition", "SUPERSEDED"),
    ("disposition", "CLEAN-ROOM-REIMPLEMENT"),
    ("family", "repair"),
    ("family", "council"),
    ("family", "adapter"),
    ("family", "scout"),
    ("family", "no-such-family"),
    ("mechanism", "M-DET-REPLAY"),
    ("mechanism", "M-NDET-SAMPLE"),
    ("mechanism", "M-FAN-IN"),
    ("mechanism", "M-DISPATCH"),
    ("mechanism", "M-SUBSTITUTE-UNSEEN"),
    ("licence_class", "MIT"),
    ("licence_class", "CC-BY"),
    ("licence_class", "GPL-3.0"),
    ("licence_class", "CC-BY-SA"),
    ("licence_class", "Apache-2.0"),
    ("licence_class", "UNOBTAINIUM"),
    ("task_class", "reliability"),
    ("task_class", "deliberation"),
    ("task_class", "translate"),
    ("task_class", "discovery"),
    ("task_class", "none"),
    ("fusibility", "fusible"),
    ("fusibility", "incompatible"),
    ("fusibility", "BP-A"),
    ("fusibility", "BP-B"),
]
