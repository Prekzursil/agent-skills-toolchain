#!/usr/bin/env python3
"""ARC-0012 live executable: two-direction generator-completeness.

Direction A: registry row with no non-empty generated file at its mapped path.
Direction B: generated file with no registry row. The two counts are reported
separately (the catalog evidence_requirement forbids one combined number).

Executed live by probe1; also runnable standalone:
  python3 -B command-center/p2-wave/probes/ARC-0012/live.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import GENERATED_ROOT, REGISTRY, expected_rel  # noqa: E402

ROOT = GENERATED_ROOT


def load_registry() -> list[dict]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [e for e in reg.get("entries") or [] if isinstance(e, dict)]


def direction_a(root: Path, entries: list[dict]) -> list[dict]:
    """Registry rows whose mapped output is absent or zero-byte."""
    rows = []
    for e in entries:
        rel = expected_rel(e)
        p = root / rel
        if not p.is_file() or p.stat().st_size == 0:
            rows.append(
                {
                    "id": str(e.get("id")),
                    "expected_path": p.as_posix(),
                    "reason": "missing" if not p.is_file() else "empty",
                }
            )
    return rows


def direction_b(root: Path, entries: list[dict]) -> list[dict]:
    """Files under the generated root with no registry id claiming them."""
    expected = {expected_rel(e) for e in entries}
    rows = []
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                if rel not in expected:
                    rows.append({"path": rel, "reason": "no-registry-id"})
    return rows


def canonical_bytes(entry: dict, version: str = "1.0.0") -> bytes:
    """Deterministic stand-in for the generator's output for this entry."""
    body = {
        "content": {k: entry.get(k) for k in sorted(entry)},
        "generator_id": "a2-ssot-generator",
        "generator_version": version,
        "registry_id": str(entry.get("id")),
    }
    return (json.dumps(body, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_tree(root: Path, entries: list[dict], version: str = "1.0.0") -> None:
    for e in entries:
        p = root / expected_rel(e)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(canonical_bytes(e, version))


def both_states(root: Path) -> dict:
    """Both-states per direction + detector-control precondition."""
    entries = load_registry()
    write_tree(root, entries)
    res: dict = {}

    # Detector-control: Direction A must find a KNOWN-planted orphan first.
    (root / expected_rel(entries[0])).unlink()
    planted = direction_a(root, entries)
    res["a_fires_on_missing"] = len(planted) == 1 and planted[0]["id"] == entries[0]["id"]

    # A silent on complete tree.
    write_tree(root, entries)
    res["a_silent_on_complete"] = direction_a(root, entries) == []

    # Empty counts as missing (FM-EMPTY-OUTPUT).
    zero = root / expected_rel(entries[1])
    zero.write_bytes(b"")
    empties = direction_a(root, entries)
    res["a_counts_empty_as_missing"] = any(
        r["id"] == entries[1]["id"] and r["reason"] == "empty" for r in empties
    )
    write_tree(root, entries)

    # Detector-control: Direction B must find a KNOWN-planted unregistered file.
    unreg = root / "unregistered" / "orphan-output.txt"
    unreg.parent.mkdir(parents=True, exist_ok=True)
    unreg.write_bytes(b"planted\n")
    b_planted = direction_b(root, entries)
    res["b_fires_on_planted"] = any(
        r["path"] == "unregistered/orphan-output.txt" for r in b_planted
    )
    unreg.unlink()
    res["b_silent_when_none"] = direction_b(root, entries) == []

    # Restore control.
    res["restore_complete"] = (
        direction_a(root, entries) == [] and direction_b(root, entries) == []
    )
    return res


def stale_bytes_demo(root: Path) -> dict:
    """The reviewer-added failure mode, demonstrated live: a generated file sits
    at the exact mapped path, non-empty, so A and B are silent; its bytes were
    emitted from a PREVIOUS registry row (v1) while the row has since changed
    (v2). Path completeness is not freshness."""
    entries = load_registry()
    target = dict(entries[0])
    root.mkdir(parents=True, exist_ok=True)
    stale_path = root / expected_rel(target)
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_bytes(canonical_bytes(target, version="0.9.0-stale"))
    # Row changes underneath (v2 content differs).
    changed = dict(target)
    changed["description"] = str(changed.get("description") or "") + " [v2]"
    res = {
        "path_nonempty": stale_path.stat().st_size > 0,
        "a_silent": direction_a(root, [target]) == [],
        "b_silent": direction_b(root, [target]) == [],
        "bytes_stale": stale_path.read_bytes() != canonical_bytes(changed, "1.0.0"),
    }
    res["gap_real"] = bool(
        res["path_nonempty"] and res["a_silent"] and res["b_silent"] and res["bytes_stale"]
    )
    stale_path.unlink()
    return res


def measure_live() -> dict:
    entries = load_registry()
    a = direction_a(ROOT, entries)
    b = direction_b(ROOT, entries)
    return {
        "registry_entries": len(entries),
        "direction_a_orphan_registry_count": len(a),
        "direction_a_orphans": a,
        "direction_b_orphan_output_count": len(b),
        "direction_b_orphans": b,
        "design_root_present": ROOT.is_dir(),
    }


if __name__ == "__main__":
    m = measure_live()
    print(json.dumps(m, indent=1))
