"""AUD-0074 source-lineage instruments.

Probe 1 instrument: citation-span extraction. It does not read timestamps
or the correction register.

Probe 2 instrument: per-edge timestamp order against known corrections.
The citation graph alone cannot see staleness; a cite whose bound version
predates a recorded correction of its target is stale-downstream.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC13 = "13-ARCHITECTURE-CANDIDATES.md"
CITE_RE = re.compile(
    r"\[cite:(?P<target>[^\s\]]+)\s+version=(?P<version>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\]"
)
NAME_RE = re.compile(r"\b(\d{2}[A-Za-z0-9._-]*)\b")


def parse_iso(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_citation_edges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Citation-derived edges. Timestamps in the cite pin the *cited version*,
    but this function does not consult the correction register."""
    known = {str(r["id"]) for r in records}
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for rec in records:
        src = str(rec["id"])
        text = str(rec.get("text") or "")
        for match in CITE_RE.finditer(text):
            target = match.group("target")
            version = match.group("version")
            if target not in known or target == src:
                continue
            key = (src, target, version)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from": src,
                    "to": target,
                    "kind": "cites",
                    "cited_version": version,
                    "span": match.group(0),
                    "instrument": "citation-span",
                }
            )
    edges.sort(key=lambda e: (e["from"], e["to"], e["cited_version"]))
    return edges


def extract_filename_mention_edges(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fallback extractor for live files that lack [cite:] pins.
    Version is the citing file's mtime. Independent of CITE_RE."""
    known = {str(r["id"]) for r in records}
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rec in records:
        src = str(rec["id"])
        text = str(rec.get("text") or "")
        version = str(rec.get("mtime") or rec.get("created_at") or "")
        for name in NAME_RE.findall(text):
            if name not in known or name == src:
                continue
            key = (src, name)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from": src,
                    "to": name,
                    "kind": "cites",
                    "cited_version": version,
                    "span": name,
                    "instrument": "filename-mention",
                }
            )
    edges.sort(key=lambda e: (e["from"], e["to"], e["cited_version"]))
    return edges


def flag_stale(
    edges: list[dict[str, Any]], corrections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Timestamp ordering check per edge. Zero knowledge of document bodies."""
    by_src = {str(c["source"]): c for c in corrections}
    flags: list[dict[str, Any]] = []
    for edge in edges:
        corr = by_src.get(edge["to"])
        if not corr:
            continue
        cited = parse_iso(str(edge["cited_version"]))
        fixed = parse_iso(str(corr["corrected_at"]))
        stale = cited < fixed
        row = {
            "from": edge["from"],
            "to": edge["to"],
            "kind": "stale-downstream" if stale else "fresh-downstream",
            "cited_version": edge["cited_version"],
            "source_corrected_at": corr["corrected_at"],
            "correction_id": corr.get("id"),
            "stale": stale,
            "instrument": "timestamp-order",
        }
        if stale:
            row["reason"] = (
                f"citation bound to {edge['cited_version']} predates known "
                f"correction {corr.get('id')} at {corr['corrected_at']}"
            )
            flags.append(row)
    flags.sort(key=lambda r: (r["from"], r["to"]))
    return flags


def timestamp_blind_flags(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutant: drop the correction register. Must return no stale flags.
    Proves the timestamp/correction check is load-bearing."""
    return flag_stale(edges, corrections=[])


def doc13_stale(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in flags if f.get("to") == DOC13 and f.get("stale") is True]


def load_corrections(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or (HERE / "fixtures" / "corrections.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    rows = doc.get("corrections") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise ValueError("corrections.json must be a list or {corrections: [...]}")
    return rows


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)
