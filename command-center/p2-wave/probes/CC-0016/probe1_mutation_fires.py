#!/usr/bin/env python3
"""CC-0016 PROBE 1: mutation test - alter one edge in a SCRATCH copy of
command-center/PHASE-GRAPH.json and confirm the extended gate fires.

Two states are measured on the SAME scratch file:
  STATE A (unmodified copy)        -> phase_graph_gate.py must exit 0.
  STATE B (one edge type flipped)  -> phase_graph_gate.py must exit != 0,
                                       and specifically raise V-PHASEGRAPH-CRITPATH
                                       because the flipped edge (0->1) is on the
                                       recorded 11-node critical path.

Also asserts BEFORE this unit, nothing in the repo checked PHASE-GRAPH.json at
all (tools/command-center/validate.py never opens it) -- so "today it does not
fire" (the catalog's own framing) is independently confirmed by grep, not
merely asserted.

Never touches the live command-center/PHASE-GRAPH.json.
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
OUT_JSON = Path(__file__).resolve().parent / "probe1-mutation-fires.json"
OUT_RAW = Path(__file__).resolve().parent / "probe1-mutation-fires.raw.txt"


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    lines: list[str] = []
    lines.append("CC-0016 PROBE1 mutation-fires (scratch only)")
    lines.append(f"REPO={REPO}")
    lines.append(f"GATE={GATE} exists={GATE.is_file()}")
    lines.append(f"LIVE_GRAPH={LIVE_GRAPH} exists={LIVE_GRAPH.is_file()}")

    # Confirm no PRE-EXISTING *CI gate* reads PHASE-GRAPH.json. Several one-off
    # analysis probes (platform/architecture/_probe_dr_*.py,
    # command-center/_catalog_shortfall_attrib.py) DO open the file for ad-hoc
    # measurement, but none of them are wired into a CI workflow or into
    # tools/command-center/validate.py -- the two places a fail-closed gate
    # would have to live to actually block a bad commit. Check both directly.
    rc_wf, out_wf = run(["grep", "-rl", "PHASE-GRAPH", ".github/workflows/"])
    workflow_hits = [ln for ln in out_wf.splitlines() if ln.strip()]
    rc_val, out_val = run(
        [
            "grep",
            "-n",
            "PHASE-GRAPH",
            "tools/command-center/validate.py",
            "tools/command-center/catalog.py",
            "tools/command-center/render.py",
        ]
    )
    validate_hits = [ln for ln in out_val.splitlines() if ln.strip()]
    lines.append(
        f"CI_WORKFLOW_HITS rc={rc_wf} count={len(workflow_hits)} hits={workflow_hits}"
    )
    lines.append(
        f"VALIDATE_CATALOG_RENDER_HITS rc={rc_val} count={len(validate_hits)} hits={validate_hits}"
    )
    pre_existing_gate = bool(workflow_hits) or bool(validate_hits)

    live_bytes_before = LIVE_GRAPH.read_bytes()
    live_sha_before = __import__("hashlib").sha256(live_bytes_before).hexdigest()

    with tempfile.TemporaryDirectory(prefix="cc0016-probe1-") as td:
        scratch = Path(td) / "PHASE-GRAPH.json"
        shutil.copy2(LIVE_GRAPH, scratch)

        rc_a, out_a = run([sys.executable, "-B", str(GATE), "--graph", str(scratch)])
        lines.append(f"STATE_A_UNMODIFIED exit={rc_a}")
        lines.append("  | " + out_a.strip().replace("\n", "\n  | "))

        data = json.loads(scratch.read_text(encoding="utf-8"))
        target_edge = None
        for e in data["edges"]:
            if e.get("from") == "0" and e.get("to") == "1":
                target_edge = e
                break
        if target_edge is None:
            lines.append("MUTATION_TARGET_NOT_FOUND edge 0->1 missing")
            OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("\n".join(lines))
            print("PROBE1_OK=False")
            return 1
        before_type = target_edge["type"]
        target_edge["type"] = "SOFT"  # one-field mutation: HARD -> SOFT
        scratch.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        rc_b, out_b = run([sys.executable, "-B", str(GATE), "--graph", str(scratch)])
        lines.append(f"MUTATION edge 0->1 type '{before_type}' -> 'SOFT'")
        lines.append(f"STATE_B_MUTATED exit={rc_b}")
        lines.append("  | " + out_b.strip().replace("\n", "\n  | "))

        fired_v_critpath = "V-PHASEGRAPH-CRITPATH" in out_b

    live_bytes_after = LIVE_GRAPH.read_bytes()
    live_sha_after = __import__("hashlib").sha256(live_bytes_after).hexdigest()
    live_untouched = live_sha_before == live_sha_after

    both_states_ok = rc_a == 0 and rc_b != 0 and fired_v_critpath and live_untouched

    lines.append(
        f"LIVE_TREE_UNTOUCHED before={live_sha_before[:12]} after={live_sha_after[:12]} ok={live_untouched}"
    )
    lines.append(
        f"BEFORE_THIS_UNIT_NO_GATE_CHECKED_PHASE_GRAPH={pre_existing_gate} (expected False)"
    )
    lines.append(f"BOTH_STATES_OK={both_states_ok}")
    lines.append(f"PROBE1_OK={both_states_ok and not pre_existing_gate}")

    summary = {
        "unmodified_exit_code": rc_a,
        "mutated_exit_code": rc_b,
        "fired_v_phasegraph_critpath": fired_v_critpath,
        "live_graph_untouched": live_untouched,
        "pre_existing_gate_checked_phase_graph": pre_existing_gate,
        "both_states_ok": both_states_ok,
        "ok": both_states_ok and not pre_existing_gate,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
