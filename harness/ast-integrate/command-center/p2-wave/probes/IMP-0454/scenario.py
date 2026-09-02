"""Sandbox experiments for IMP-0454: full writer run + direct-open bypass.

The independent walker below is intentionally a second implementation of the
set difference (not a call into registering_writer.list_disk_artifacts).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
PKG = REPO / "tools" / "command-center"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from registering_writer import RegisteringWriter, reconcile  # noqa: E402

UNIT = "IMP-0454"


def independent_setdiff(artifact_root: Path, manifest_path: Path) -> dict[str, Any]:
    """Second walker: rglob + json.load. Must not import list_disk_artifacts."""
    disk: set[str] = set()
    man_res = manifest_path.resolve()
    if artifact_root.is_dir():
        for p in artifact_root.rglob("*"):
            if not p.is_file():
                continue
            if p.resolve() == man_res:
                continue
            if p.name.endswith(".tmp") or p.name.endswith(".partial"):
                continue
            if p.name.startswith("."):
                continue
            disk.add(p.relative_to(artifact_root).as_posix())
    registered: set[str] = set()
    if manifest_path.is_file():
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in doc.get("artifacts") or []:
            if isinstance(row, dict) and isinstance(row.get("path"), str):
                registered.add(row["path"].replace("\\", "/"))
    unreg = sorted(disk - registered)
    orphans = sorted(registered - disk)
    return {
        "disk": sorted(disk),
        "registered": sorted(registered),
        "unregistered": unreg,
        "orphan_rows": orphans,
        "unregistered_count": len(unreg),
        "set_difference_empty": not unreg and not orphans,
        "method": "independent-rglob-minus-json-paths",
    }


def run_full_writer_run() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="imp0454-full-"))
    root = tmp / "out"
    man = tmp / "ARTIFACT-MANIFEST.json"
    payloads = [
        ("alpha.json", '{"n":1}\n'),
        ("beta/gamma.txt", "gamma-body\n"),
        ("delta.md", "# delta\n"),
    ]
    w = RegisteringWriter(root, man)
    per_emit: list[dict[str, Any]] = []
    for rel, body in payloads:
        w.emit(rel, body, unit_id=UNIT, role="fixture")
        # Fresh disk read immediately after emit — not a later sweep.
        fresh = json.loads(man.read_text(encoding="utf-8"))
        paths = [a["path"] for a in fresh["artifacts"]]
        per_emit.append(
            {
                "just_emitted": rel,
                "manifest_paths_on_disk": paths,
                "row_present_before_reconcile": rel in paths,
            }
        )
    lib = reconcile(root, man).as_dict()
    ind = independent_setdiff(root, man)
    man_before = man.read_bytes()
    reconcile(root, man)
    man_unchanged = man.read_bytes() == man_before
    return {
        "sandbox": str(tmp),
        "emitted": [p[0] for p in payloads],
        "writer_memory_paths": list(w.emitted_paths),
        "per_emit_disk_reads": per_emit,
        "library_reconcile": lib,
        "independent_setdiff": ind,
        "agree": lib["unregistered"] == ind["unregistered"]
        and lib["orphan_rows"] == ind["orphan_rows"],
        "unregistered_count": ind["unregistered_count"],
        "set_difference_empty": ind["set_difference_empty"] and lib["set_difference_empty"],
        "reconcile_is_read_only": man_unchanged,
        "registered_at_emit_not_sweep": all(
            step["row_present_before_reconcile"] for step in per_emit
        ),
    }


def run_bypass() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="imp0454-bypass-"))
    root = tmp / "out"
    man = tmp / "ARTIFACT-MANIFEST.json"
    w = RegisteringWriter(root, man)
    w.emit("kept.json", '{"kept":true}\n', unit_id=UNIT)
    before = independent_setdiff(root, man)
    sneak_rel = "sneak-bypass.txt"
    sneak = root / sneak_rel
    # Catalog: artifact written by a direct file open (not the writer).
    with open(sneak, "w", encoding="utf-8") as fh:
        fh.write("direct-open bypass of RegisteringWriter.emit\n")
    after_lib = reconcile(root, man).as_dict()
    after_ind = independent_setdiff(root, man)
    man_before = man.read_bytes()
    reconcile(root, man)
    sweep_did_not_register = man.read_bytes() == man_before
    memory_missed = sneak_rel not in w.emitted_paths
    return {
        "sandbox": str(tmp),
        "before_unregistered": before["unregistered"],
        "before_empty": before["set_difference_empty"],
        "bypass_path": sneak_rel,
        "library_unregistered": after_lib["unregistered"],
        "independent_unregistered": after_ind["unregistered"],
        "caught": sneak_rel in after_lib["unregistered"]
        and sneak_rel in after_ind["unregistered"],
        "unregistered_count_after": after_ind["unregistered_count"],
        "in_memory_writer_paths": list(w.emitted_paths),
        "in_memory_misses_bypass": memory_missed,
        "sweep_did_not_register": sweep_did_not_register,
        "both_states": before["set_difference_empty"]
        and sneak_rel in after_ind["unregistered"],
    }
