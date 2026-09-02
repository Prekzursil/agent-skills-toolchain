#!/usr/bin/env python3
"""Probe 1: both-direction set difference, independently recomputed, plus
the catalog negative control (remove one doc entry → named exactly)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.docs_parity import (  # noqa: E402
    Ident,
    compute_parity,
    drop_documented_entry,
)
from marketplace.tests.test_docs_parity import (  # noqa: E402
    test_both_direction_sets_are_empty,
    test_removed_doc_entry_is_named_exactly,
)

GOOD = REPO / "tools/marketplace/fixtures/docs-parity-good"


def _independent_declared(root: Path) -> set[tuple[str, str]]:
    data = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    out: set[tuple[str, str]] = set()
    for item in data["commands"]:
        out.add(("command", item["id"]))
    for path in data["skills"]:
        out.add(("skill", Path(path).parent.name))
    for path in data["hooks"]:
        out.add(("hook", Path(path).stem))
    return out


def _independent_documented_surface(root: Path) -> set[tuple[str, str]]:
    """Parse SURFACE.md bullets only — not the library parser."""
    text = (root / "docs" / "SURFACE.md").read_text(encoding="utf-8")
    kind = None
    out: set[tuple[str, str]] = set()
    mapping = {"commands": "command", "skills": "skill", "hooks": "hook"}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            token = stripped[3:].strip().lower()
            kind = mapping.get(token)
            continue
        if kind and stripped.startswith("- "):
            out.add((kind, stripped[2:].strip().strip("`")))
    return out


def main() -> int:
    test_both_direction_sets_are_empty()
    test_removed_doc_entry_is_named_exactly()

    report = compute_parity(GOOD)
    lib_decl = {(i.kind, i.name) for i in report.declared}
    lib_docs = {(i.kind, i.name) for i in report.documented}
    ind_decl = _independent_declared(GOOD)
    ind_docs = _independent_documented_surface(GOOD)
    if not ind_decl or not ind_docs:
        print("FAILED:IMP-0120-probe1 independent parse empty")
        return 1
    if lib_decl != ind_decl:
        print("FAILED:IMP-0120-probe1 declared mismatch", sorted(lib_decl), sorted(ind_decl))
        return 1
    if lib_docs != ind_docs:
        print("FAILED:IMP-0120-probe1 documented mismatch", sorted(lib_docs), sorted(ind_docs))
        return 1
    if lib_decl != lib_docs:
        print("FAILED:IMP-0120-probe1 set difference not empty", report.as_dict())
        return 1
    if not report.both_empty:
        print("FAILED:IMP-0120-probe1 both_empty false")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "pkg"
        shutil.copytree(GOOD, clone)
        drop_documented_entry(clone, "status", "command")
        mutated = compute_parity(clone)
        if mutated.named_commands() != ["status"]:
            print("FAILED:IMP-0120-probe1 negative control", mutated.as_dict())
            return 1
        if mutated.declared_minus_documented != {Ident("command", "status")}:
            print("FAILED:IMP-0120-probe1 negative control set", mutated.as_dict())
            return 1
        if mutated.documented_minus_declared:
            print("FAILED:IMP-0120-probe1 negative control extra", mutated.as_dict())
            return 1

    payload = {
        "pass": True,
        "probe": "probe1-set-parity",
        "unit_id": "IMP-0120",
        "declared": sorted(f"{k}:{n}" for k, n in lib_decl),
        "documented": sorted(f"{k}:{n}" for k, n in lib_docs),
        "declared_minus_documented": [],
        "documented_minus_declared": [],
        "independent_match": True,
        "negative_control_named": ["status"],
        "both_empty": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "declared="
        + ",".join(payload["declared"])
        + " independent_match=True negative_control=status"
    )
    print("SUCCESS:IMP-0120-probe1 both-direction sets empty and named negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
