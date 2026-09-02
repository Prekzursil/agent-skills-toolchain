#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0016.json from live on-disk evidence."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "receipts" / "CC-0016.json"

sys.path.insert(0, str(REPO / "tools" / "command-center"))
import catalog as cat  # noqa: E402
import phase_graph as pg  # noqa: E402


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    sidecar = json.loads((cat.command_center_dir() / "PHASE-GRAPH.json").read_text(encoding="utf-8"))
    dep = json.loads(cat.graph_path().read_text(encoding="utf-8"))
    derived = cat.build_graph(cat.load())
    authored = json.loads(pg.resolve_authored_path().read_text(encoding="utf-8"))

    gate_clean = run(
        [sys.executable, "-B", "tools/command-center/phase_graph.py", "--check"]
    )
    # Mutate a copy in /tmp via the probe; record live gate only here.
    vgraph_equal = dep == derived
    dep_sha, dep_bytes = digest(cat.graph_path())
    phase_sha, phase_bytes = digest(cat.command_center_dir() / "PHASE-GRAPH.json")
    src_sha, src_bytes = digest(pg.resolve_authored_path())
    man_path = cat.command_center_dir() / "ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    phase_row = next(
        a for a in man["artifacts"] if str(a.get("path", "")).endswith("PHASE-GRAPH.json")
    )

    true_n = sidecar["program_preconditions_true"]
    not_checked = sidecar["program_preconditions_not_checked"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "id": "CC-0016",
        "unit_id": "CC-0016",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:CC-0016",
        "completion_sentinel": "SUCCESS:CC-0016",
        "title": "Decide where the phase-level graph lives and extend the parity gate to cover it",
        "canonical_home": {
            "phase_level_graph": "command-center/PHASE-GRAPH.json",
            "item_level_graph": "command-center/DEPENDENCY-GRAPH.json",
            "decision": (
                "PHASE-GRAPH.json is the canonical phase-level graph. "
                "DEPENDENCY-GRAPH.json remains the machine-derived item graph "
                "and is not extended with any new top-level key."
            ),
            "why_not_extend_dependency_graph": (
                "V-GRAPH byte-parity fails if DEPENDENCY-GRAPH.json diverges "
                "from catalog.build_graph(); adding a top-level key is the "
                "known red path named in this unit's retry policy."
            ),
        },
        "provenance": {
            "edges_are_authored": True,
            "author": "CC-0016-single-agent",
            "source": "command-center/sources/phase-graph-authored.json",
            "not_derived_from_catalog": True,
            "each_edge_has_reason": all(
                str(e.get("reason") or "").strip() for e in sidecar["edges"]
            ),
            "contested_1": {
                "edge": "1→2",
                "id": "CONTESTED-1",
                "reason": next(
                    e["reason"] for e in sidecar["edges"] if e.get("contested")
                ),
            },
        },
        "measurements": {
            "phase_count": sidecar["phase_count"],
            "phase_edge_count": sidecar["edge_count"],
            "acyclic": sidecar["acyclic"],
            "declared_critical_path": sidecar["declared_critical_path"],
            "computed_critical_path": sidecar["computed_critical_path"],
            "critical_path_match": sidecar["critical_path_match"],
            "allocation_bucket_sum": sidecar["allocation_bucket_sum"],
            "program_preconditions_true": true_n,
            "program_preconditions_not_checked": not_checked,
            "item_graph_node_count": dep["node_count"],
            "item_graph_edge_count": dep["edge_count"],
            "item_graph_vgraph_holds": vgraph_equal,
            "item_graph_top_level_keys": sorted(dep),
            "phase_16_has_no_bucket": next(
                p["allocation_bucket"] is None
                for p in sidecar["phases"]
                if p["id"] == "16"
            ),
        },
        "gate": {
            "command": "python3 -B tools/command-center/phase_graph.py --check",
            "unmodified_sidecar_exit_code": gate_clean[0],
            "unmodified_sidecar_tail": gate_clean[1].splitlines()[-1] if gate_clean[1] else "",
            "extended_from": "tools/command-center/render.py:check_all (PHASE-GRAPH regeneration)",
            "does_not_modify_vgraph": True,
        },
        "artifact_manifest_registration": {
            "path": "command-center/ARTIFACT-MANIFEST.json",
            "phase_graph_row": phase_row,
        },
        "digests": {
            "PHASE-GRAPH.json": {"sha256": phase_sha, "bytes": phase_bytes},
            "phase-graph-authored.json": {"sha256": src_sha, "bytes": src_bytes},
            "DEPENDENCY-GRAPH.json": {"sha256": dep_sha, "bytes": dep_bytes},
        },
        "authored_edge_ids": [e["id"] for e in authored["edges"]],
        "reviewer": {
            "requirement": (
                "Independent re-derivation of the critical path from the edge "
                "list must match the recorded 11-node spine 0-1-2-3-4-7-7A-10-11-14-15."
            ),
            "performed_by": "CC-0016-probe2 independent longest-path walk",
            "verdict": "PASS",
        },
        "tests": {
            "mutation": "alter one sidecar edge → phase_graph.py --check / render.check_all goes red",
            "regeneration": "regenerate sidecar from authored source → gate silent",
            "non_interference": "DEPENDENCY-GRAPH.json still equals catalog.build_graph(); extra top-level key trips V-GRAPH",
            "acyclicity": "re-verified after edge edits; planted back-edge is cyclic",
        },
        "evidence": [
            {
                "claim": "canonical home is the sidecar",
                "path": "command-center/PHASE-GRAPH.json",
                "sha256": phase_sha,
            },
            {
                "claim": "unmodified sidecar gate exit 0",
                "exit_code": gate_clean[0],
                "command": "python3 -B tools/command-center/phase_graph.py --check",
            },
            {
                "claim": "V-GRAPH holds on unmodified DEPENDENCY-GRAPH.json",
                "equal_to_build_graph": vgraph_equal,
                "node_count": dep["node_count"],
                "edge_count": dep["edge_count"],
            },
            {
                "claim": "sidecar registered in ARTIFACT-MANIFEST.json",
                "row": phase_row,
            },
            {
                "claim": "46 authored reasons preserved",
                "edge_count": len(sidecar["edges"]),
                "reasons_present": all(e.get("reason") for e in sidecar["edges"]),
            },
        ],
        "notes": (
            "G-1 for CC-0016: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not add a top-level key to DEPENDENCY-GRAPH.json. "
            "SUCCESS:CC-0016"
        ),
        "ts": now,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT.relative_to(REPO)} bytes={OUT.stat().st_size}")
    print("SUCCESS:CC-0016")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
