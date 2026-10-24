#!/usr/bin/env python3
"""CC-0016 PROBE 4: acyclicity - the phase graph must be RE-VERIFIED acyclic
after any edge edit, on a SCRATCH copy only.

Three states measured on the same scratch file:
  STATE A (unmodified)                       -> acyclic=True (no violation)
  STATE B (reason-text-only edit on an edge)  -> topology unchanged, still
                                                  acyclic=True (a non-structural
                                                  edit must not falsely flag)
  STATE C (added edge 15->0, closes a loop)   -> acyclic=False, gate raises
                                                  V-PHASEGRAPH-CYCLE

State C additionally re-derives the critical path recomputation: with the
HARD-only subgraph made cyclic, ``longest_hard_chain`` must report
``hard_subgraph_is_dag=False`` rather than silently returning a wrong path.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GATE = REPO / "command-center/p2-wave/probes/CC-0016/phase_graph_gate.py"
LIVE_GRAPH = REPO / "command-center/PHASE-GRAPH.json"
OUT_JSON = Path(__file__).resolve().parent / "probe4-acyclicity-reverify.json"
OUT_RAW = Path(__file__).resolve().parent / "probe4-acyclicity-reverify.raw.txt"


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def gate_json(scratch: Path) -> dict:
    rc, out = run([sys.executable, "-B", str(GATE), "--graph", str(scratch), "--json"])
    return rc, json.loads(out)


def main() -> int:
    lines: list[str] = []
    lines.append("CC-0016 PROBE4 acyclicity-reverify (scratch only)")
    lines.append(f"REPO={REPO}")

    with tempfile.TemporaryDirectory(prefix="cc0016-probe4-") as td:
        scratch = Path(td) / "PHASE-GRAPH.json"
        shutil.copy2(LIVE_GRAPH, scratch)

        rc_a, doc_a = gate_json(scratch)
        acyclic_a = doc_a["computed"]["acyclic"]
        lines.append(f"STATE_A_UNMODIFIED exit={rc_a} acyclic={acyclic_a}")

        data = json.loads(scratch.read_text(encoding="utf-8"))
        data["edges"][0]["reason"] = data["edges"][0]["reason"] + " [probe4-reason-only-edit]"
        scratch.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        rc_b, doc_b = gate_json(scratch)
        acyclic_b = doc_b["computed"]["acyclic"]
        lines.append(
            f"STATE_B_REASON_ONLY_EDIT exit={rc_b} acyclic={acyclic_b} "
            "(non-structural edit must not change acyclicity)"
        )

        data["edges"].append(
            {
                "from": "15",
                "to": "0",
                "type": "HARD",
                "reason": "probe4 planted cycle-closing edge (mutation control, scratch only)",
            }
        )
        data["edge_count"] = len(data["edges"])
        data["hard_edge_count"] = sum(1 for e in data["edges"] if e["type"] == "HARD")
        scratch.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        rc_c, doc_c = gate_json(scratch)
        acyclic_c = doc_c["computed"]["acyclic"]
        hard_is_dag_c = doc_c["computed"]["hard_subgraph_is_dag"]
        cycle_fired = any(v["check"] == "V-PHASEGRAPH-CYCLE" for v in doc_c["violations"])
        lines.append(
            f"STATE_C_CYCLE_EDGE_15_TO_0 exit={rc_c} acyclic={acyclic_c} "
            f"hard_subgraph_is_dag={hard_is_dag_c} v_cycle_fired={cycle_fired}"
        )
        lines.append(f"  cycle_path={doc_c['computed'].get('cycle_path')}")

    ok = (
        rc_a == 0
        and acyclic_a is True
        and rc_b == 0
        and acyclic_b is True
        and rc_c != 0
        and acyclic_c is False
        and hard_is_dag_c is False
        and cycle_fired
    )
    lines.append(f"PROBE4_OK={ok}")

    summary = {
        "state_a_unmodified": {"exit_code": rc_a, "acyclic": acyclic_a},
        "state_b_reason_only_edit": {"exit_code": rc_b, "acyclic": acyclic_b},
        "state_c_cycle_edge": {
            "exit_code": rc_c,
            "acyclic": acyclic_c,
            "hard_subgraph_is_dag": hard_is_dag_c,
            "v_phasegraph_cycle_fired": cycle_fired,
            "cycle_path": doc_c["computed"].get("cycle_path"),
        },
        "ok": ok,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
