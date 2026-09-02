"""Two-direction A2 generator-completeness gate.

Direction A (orphan registry): a registry entry whose expected output is
missing or empty. Fires when the generator is wrong, skipped a row, or stale
relative to a new registry id.

Direction B (orphan output): a file under the generated root with no registry
entry. Fires when the generator (or a human) left a leftover after a registry
delete.

The two counts are NEVER summed into a single 'consistent' number. A detector
that reports zero in a direction without a prior known-orphan hit is rejected
by the caller (detector-control precondition).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mapping import KIND_LAYOUT, expected_rel


def load_registry(path: Path) -> dict[str, Any]:
    import json

    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"registry {path} is not an object")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"registry {path} has no entries")
    return doc


def _posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def list_generated_files(repo: Path, generated_root_rel: str) -> list[str]:
    gen = repo / generated_root_rel
    if not gen.is_dir():
        return []
    out: list[str] = []
    for p in sorted(gen.rglob("*")):
        if p.is_file():
            out.append(_posix(p, repo))
    return out


def completeness(
    repo: Path,
    registry: Mapping[str, Any],
    generated_root_rel: str,
    *,
    min_bytes: int = 1,
) -> dict[str, Any]:
    """Return separate Direction A and Direction B counts. Never a combined score."""
    entries = list(registry.get("entries") or [])
    ids: list[str] = []
    expected: dict[str, str] = {}
    kind_errors: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            kind_errors.append(f"entries[{i}]-not-object")
            continue
        eid = str(entry.get("id") or "").strip()
        kind = str(entry.get("kind") or "")
        ids.append(eid)
        if kind not in KIND_LAYOUT:
            kind_errors.append(f"unknown-kind:{eid}:{kind}")
            continue
        try:
            rel = expected_rel(entry, generated_root_rel)
        except ValueError as exc:
            kind_errors.append(str(exc))
            continue
        if rel in expected and expected[rel] != eid:
            kind_errors.append(f"path-collision:{rel}:{expected[rel]}:{eid}")
        expected[rel] = eid

    dup_ids = sorted({x for x in ids if x and ids.count(x) > 1})
    on_disk = list_generated_files(repo, generated_root_rel)

    direction_a: list[dict[str, str]] = []
    for rel, eid in expected.items():
        path = repo / rel
        if not path.is_file():
            direction_a.append(
                {"id": eid, "expected_path": rel, "reason": "missing"}
            )
            continue
        try:
            size = path.stat().st_size
        except OSError:
            direction_a.append(
                {"id": eid, "expected_path": rel, "reason": "unreadable"}
            )
            continue
        if size < min_bytes:
            direction_a.append(
                {"id": eid, "expected_path": rel, "reason": "empty"}
            )

    expected_set = set(expected)
    direction_b: list[dict[str, str]] = []
    for rel in on_disk:
        if rel not in expected_set:
            direction_b.append({"path": rel, "reason": "unregistered"})

    a_count = len(direction_a)
    b_count = len(direction_b)
    return {
        "generated_root": generated_root_rel,
        "registry_entry_count": len(entries),
        "output_file_count": len(on_disk),
        "duplicate_ids": dup_ids,
        "kind_errors": kind_errors,
        "direction_a_orphan_registry_count": a_count,
        "direction_a_orphans": direction_a,
        "direction_b_orphan_output_count": b_count,
        "direction_b_orphans": direction_b,
        "direction_a_fail": a_count > 0 or bool(dup_ids) or bool(kind_errors),
        "direction_b_fail": b_count > 0,
        # boolean AND is allowed; a summed integer is not
        "both_directions_clean": a_count == 0
        and b_count == 0
        and not dup_ids
        and not kind_errors,
    }
