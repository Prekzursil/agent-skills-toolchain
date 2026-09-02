#!/usr/bin/env python3
"""Probe 2: independent reviewers, no vote-count, irreducible recorded."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402
import schema_offline as S  # noqa: E402

UNIT = "CNF-0068"


def main() -> int:
    src_a = (HERE / "reviewer_a.py").read_text(encoding="utf-8")
    src_b = (HERE / "reviewer_b.py").read_text(encoding="utf-8")
    if "_reviewer_b" in src_a or "reviewer_b" in src_a:
        print("FAILED:CNF-0068-probe2 reviewer A references B")
        return 1
    if "_reviewer_a" in src_b or "reviewer_a" in src_b:
        print("FAILED:CNF-0068-probe2 reviewer B references A")
        return 1

    for script in ("reviewer_a.py", "reviewer_b.py"):
        proc = subprocess.run(
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0068/{script}",
            cwd=str(REPO),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print((proc.stdout or "") + (proc.stderr or ""))
            print(f"FAILED:CNF-0068-probe2 {script} rc={proc.returncode}")
            return 1

    rev_a = json.loads((HERE / "_reviewer_a.json").read_text(encoding="utf-8"))
    rev_b = json.loads((HERE / "_reviewer_b.json").read_text(encoding="utf-8"))
    if rev_a.get("peer_verdicts_seen") is not False or rev_b.get("peer_verdicts_seen") is not False:
        print("FAILED:CNF-0068-probe2 peer seen")
        return 1
    if rev_a.get("reviewer_id") == rev_b.get("reviewer_id"):
        print("FAILED:CNF-0068-probe2 same reviewer id")
        return 1

    unit = A.catalog_unit(UNIT)
    doc = json.loads((REPO / unit["output_path"]).read_text(encoding="utf-8"))
    a_map = {r["id"]: r["outcome"] for r in rev_a["edges"]}
    b_map = {r["id"]: r["outcome"] for r in rev_b["edges"]}
    for rec in S.edges_of(doc):
        eid = rec["id"]
        if a_map.get(eid) != rec["outcome"] or b_map.get(eid) != rec["outcome"]:
            print(f"FAILED:CNF-0068-probe2 reviewer/artifact {eid}")
            return 1
        if rec["outcome"] == "IRREDUCIBLE" and len(str(rec.get("settling_evidence") or "")) < 24:
            print("FAILED:CNF-0068-probe2 irreducible evidence", eid)
            return 1

    trap = None
    for edge in A.load_fixture_edges():
        live, _ = A.run_test(edge, A.live_world())
        flipped = dict(edge)
        flipped["agent_assertions"] = (
            [{"agent": "flood", "side": "SIDE_A"}] * 50
            + [{"agent": "few", "side": "SIDE_B"}] * 1
        )
        live2, _ = A.run_test(flipped, A.live_world())
        if live != live2:
            print("FAILED:CNF-0068-probe2 vote mutation changed verdict", edge["id"])
            return 1
        maj = A.majority_side(edge)
        if edge.get("vote_count_trap"):
            trap = (edge["id"], live, maj)
            if live == maj:
                print("FAILED:CNF-0068-probe2 trap settled by majority")
                return 1
            if maj != "SIDE_A" or live != "SIDE_B":
                print("FAILED:CNF-0068-probe2 trap shape", live, maj)
                return 1
        print(f"edge {edge['id']} live={live} majority={maj} mutation_stable=True")

    if trap is None:
        print("FAILED:CNF-0068-probe2 vote-count trap missing")
        return 1
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-independent",
                "trap_id": trap[0],
                "trap_live": trap[1],
                "trap_majority": trap[2],
                "unit_id": UNIT,
            }
        )
    )
    print("SUCCESS:CNF-0068-probe2 independent reviewers and no vote-count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
